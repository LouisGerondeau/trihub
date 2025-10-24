# core/services/recurrence.py

from datetime import datetime

from core.models import CoachAssignment, Recurrence, Session
from core.utils import PARIS_TZ, iter_weekly_occurrences, to_paris
from django.core.exceptions import ValidationError
from django.db import transaction

from ..utils import compare_model_instance


@transaction.atomic
def generate_series(session: Session, mode: str, end_date) -> Recurrence:
    """
    Crée une récurrence à partir d'une séance existante.
    - session : instance de la première séance
    - mode : 'weekly' ou 'same_type'
    - end_date : date locale (inclusive)
    """
    # --- Garde-fous ---
    if session.recurrence:
        raise ValidationError("Cette séance fait déjà partie d'une série.")
    if end_date <= session.start_at.date():
        raise ValidationError(
            "La date de fin doit être postérieure à la première séance."
        )

    # Vérif limites : max 50 séances et horizon ≤ 365 jours
    delta_days = (end_date - session.start_at.date()).days
    if delta_days > 365:
        raise ValidationError("La récurrence ne peut pas dépasser un an.")

    # --- Création de la récurrence ---
    recurrence = Recurrence.objects.create(mode=mode, end_date=end_date)
    session.recurrence = recurrence
    session.save()
    base_pk = session.pk
    base_assignments = list(
        CoachAssignment.objects.filter(session=session).select_related("coach")
    )
    # --- Génération des occurrences ---
    for occ_dt in iter_weekly_occurrences(
        session.start_at, end_date, same_type=(mode == "same_type")
    ):
        session.pk = None
        session._state.adding = True
        session.start_at = occ_dt
        session.save()
        cas = CoachAssignment.objects.filter(session=base_pk)
        for ca in cas:
            ca.pk = None
            ca._state.adding = True
            ca.session = session
            ca.save()

    return recurrence


def _same_iso_week(a: datetime, b: datetime) -> bool:
    a_iso = to_paris(a).isocalendar()
    b_iso = to_paris(b).isocalendar()
    return (a_iso[0], a_iso[1]) == (b_iso[0], b_iso[1])  # (year, week)


def change_time(dt: datetime, new_t: datetime) -> datetime:
    local = to_paris(dt)
    return local.replace(
        hour=new_t.hour,
        minute=new_t.minute,
        second=new_t.second,
        microsecond=new_t.microsecond,
    )


@transaction.atomic
def propagate_form_fields(source: Session, formchange: list):
    """
    Propage des modifications ciblées à partir de `source` vers les occurrences de la même série
    dont start_at >= source.start_at (heure locale Paris).

    Paramètres
    ----------
    source : Session
        Séance d'où part la propagation (doit avoir `recurrence`).
    formchange : list
        La liste des champs simples modifiés dans le formulaire
    Règles
    ------
    - Inclut séances passées/verrouillées tant qu'elles sont postérieure a séance source.
    - Atomicité: tout ou rien.
    - N'affecte que les champs modifiés
    """
    if not source.recurrence:
        raise ValidationError("Cette séance n'appartient pas à une série.")

    if "start_at" in formchange:
        cur_s = Session.objects.filter(pk=source.pk)[0]
        new_dt = to_paris(cur_s.start_at)
        old_dt = to_paris(source.start_at)
        # Si jour différent, erreur
        if new_dt.date() != old_dt.date():
            raise ValidationError(
                "Vous ne pouvez pas changer le jour d'une séance récurrente."
            )

    ses_rec = (
        Session.objects.filter(recurrence=source.recurrence)
        .filter(start_at__gte=source.start_at)
        .exclude(pk=source.pk)
    )
    for ses in ses_rec:
        for c in formchange:
            if c == "start_at":
                setattr(ses, c, change_time(ses.start_at, source.start_at))
            else:
                setattr(ses, c, getattr(source, c))
        ses.save()


@transaction.atomic
def propagate_coach_assignments(cas_old, cas_saved):
    """
    Propage des modifications m2m à partir de `source` vers les occurrences de la même série
    dont start_at >= source.start_at (heure locale Paris).
    Paramètres
    ----------
    cas_old : liste des deep copys des instances CoachAssingment associées a une session avant sauvegarde
        Séance d'où part la propagation (doit avoir `recurrence`).
    cas_saved : liste des instances CoachAssingment associées a une session après sauvegarde
    """
    if not cas_saved and not cas_old:
        return

    # Référence : même série + pivot temporel
    source = (cas_saved or cas_old)[0]
    rec = source.session.recurrence
    pivot = source.session.start_at  # stocké UTC si USE_TZ=True

    saved_by_coach = {c.coach_id: c for c in cas_saved}
    old_by_coach = {c.coach_id: c for c in cas_old}

    old_ids = set(old_by_coach.keys())
    new_ids = set(saved_by_coach.keys())

    removed = old_ids - new_ids
    kept = old_ids & new_ids
    added = new_ids - old_ids

    # 1) Suppressions : retirer le coach des occurrences suivantes de la même série
    if removed:
        (
            CoachAssignment.objects.filter(
                coach_id__in=removed,
                session__recurrence=rec,
                session__start_at__gte=pivot,
            )
            .exclude(pk__in=[old_by_coach[cid].pk for cid in removed])
            .delete()
        )

    # 2) Mises à jour : si des champs diffèrent, propager
    for cid in kept:
        before = old_by_coach[cid]
        after = saved_by_coach[cid]
        diff = compare_model_instance(after, before)  # dict champ->valeur
        if diff:
            (
                CoachAssignment.objects.filter(
                    coach_id=cid, session__recurrence=rec, session__start_at__gte=pivot
                )
                .exclude(pk=before.pk)
                .update(**diff)
            )

    # 3) Ajouts : répliquer sur toutes les occurrences suivantes
    if added:
        target_sessions = (
            Session.objects.filter(recurrence=rec, start_at__gte=pivot)
            .exclude(pk=source.session.pk)
            .only("id")
        )  # optimisation

        to_create = []
        for cid in added:
            src = saved_by_coach[cid]
            CoachAssignment.objects.filter(
                coach_id=cid, session__recurrence=rec, session__start_at__gte=pivot
            ).exclude(pk=saved_by_coach[cid].pk).delete()
            for s in target_sessions:
                src.pk = None
                src._state.adding = True
                src.session = s
                src.save()
