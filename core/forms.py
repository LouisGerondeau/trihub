# core/forms.py


from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Member, Session
from .utils import next_july_31

RECURRENCE_CHOICES = [
    ("none", "Aucune"),
    ("weekly", "Hebdomadaire"),
    ("same_type", "Semaines du même type (pair/impair)"),
]


class SessionAdminForm(forms.ModelForm):
    """
    Création :
      - Peut rester ponctuelle OU créer une série (mode + end_date).
    Édition :
      - Si la séance est ponctuelle (pas de recurrence) → possibilité de créer une série.
      - Si la séance a une recurrence → on affiche une info read-only et on interdit le changement de jour.
    """

    # Champs d'entrée pour créer une série (montrés seulement si pas encore en série)
    recurrence_mode = forms.ChoiceField(required=False)
    recurrence_end_date = forms.DateField(required=False)
    recurrence_info = forms.CharField(required=False)
    start_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )

    class Meta:
        model = Session
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        has_recurrence = bool(
            self.instance and self.instance.pk and self.instance.recurrence
        )

        # Par défaut, proposer le 31/07 de la saison courante si on peut créer une série
        if not has_recurrence:
            self.fields.pop("recurrence_end_date")
            # Tente de prendre la date du start_at du form (initial ou instance), sinon None
            start_date = None
            try:
                start_date = (
                    (self.data.get("start_at") and self.instance.start_at)
                    or self.initial.get("start_at")
                    or self.instance.start_at
                )
                if start_date:
                    start_date = getattr(start_date, "date", lambda: None)() or None
            except Exception:
                start_date = None
            self.fields["recurrence_mode"] = forms.ChoiceField(
                required=False,
                label="Récurrence",
                help_text="Choisissez 'Aucune' pour une séance ponctuelle.",
                choices=RECURRENCE_CHOICES,
            )
            self.fields["recurrence_end_date"] = forms.DateField(
                label="Date de fin (incluse)",
                help_text="Date de fin de la séance récurrente si le champ du dessus n'est pas 'Aucun'",
                widget=forms.DateInput(attrs={"type": "date"}),
                required=False,
                initial=next_july_31(start_date).isoformat(),
            )
        else:
            # Si déjà en série : masquer les champs d'entrée et afficher une info read-only
            self.fields.pop("recurrence_mode")
            self.fields.pop("recurrence_end_date")

            rec = self.instance.recurrence
            msg = (
                f"Cette séance fait partie d’une série "
                f"de type « {rec.get_mode_display()} » "
                f"(fin prévue le {rec.end_date:%d/%m/%Y})."
            )
            self.fields["recurrence_info"] = forms.CharField(
                label="Récurrence",
                initial=msg,
                widget=forms.Textarea(
                    attrs={
                        "readonly": "readonly",
                        "rows": 3,
                        "style": "border:none;  font-style:italic; resize:none;",
                        "size": 2000,
                    }
                ),
            )

        # Mémorise la date initiale (pour contrôle de changement de jour si déjà en série)

        self._initial_start_date = None
        if self.instance and self.instance.pk and self.instance.start_at:
            self._initial_start_date = self.instance.start_at.date()
            local_dt = timezone.localtime(self.instance.start_at)
            self.initial["start_at"] = local_dt.strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned = super().clean()
        is_create = self.instance.pk is None
        has_recurrence = bool(self.instance and self.instance.recurrence)

        # Interdire changement de JOUR si déjà en série
        if not is_create and has_recurrence and self._initial_start_date:
            new_start = cleaned.get("start_at")
            if new_start and new_start.date() != self._initial_start_date:
                raise ValidationError(
                    "Impossible de modifier le jour d’une séance récurrente. "
                    "Supprimez la série et recréez-la si nécessaire."
                )

        # Validation des champs de création/transformation de série (seulement si pas encore en série)
        if not has_recurrence:
            mode = cleaned.get("recurrence_mode") or "none"
            if mode != "none":
                start_at = cleaned.get("start_at")
                end_date = cleaned.get("recurrence_end_date")
                if not start_at:
                    raise ValidationError("La date/heure de début est requise.")
                if not end_date:
                    raise ValidationError(
                        "La date de fin (incluse) est requise pour une récurrence."
                    )
                if end_date <= start_at.date():
                    raise ValidationError(
                        "La date de fin doit être postérieure à la première séance."
                    )
                if (end_date - start_at.date()).days > 365:
                    raise ValidationError("La récurrence ne peut pas dépasser un an.")
        return cleaned

    def save(self, commit=True):
        session = super().save(commit=commit)
        # Marque l’intention de créer une série (l’admin s’en chargera après les inlines)
        has_recurrence = bool(session.recurrence)
        if not has_recurrence:
            mode = self.cleaned_data.get("recurrence_mode") or "none"
            end_date = self.cleaned_data.get("recurrence_end_date")
            if mode != "none":
                # flag lu par l'admin après sauvegarde des inlines
                self._recurrence_request = (mode, end_date)
        return session


class CoachSelectForm(forms.Form):
    coach = forms.ModelChoiceField(
        queryset=Member.objects.none(),  # important : ModelChoiceField
        label="Encadrant",
    )
