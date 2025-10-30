# core/utils.py

import unicodedata
import zoneinfo
from datetime import date, datetime, timedelta

BASE_TYPES = [str, int, float, bool, type(None)]
PARIS_TZ = zoneinfo.ZoneInfo("Europe/Paris")


# -----------------------------------------------------------
# Fonctions utilitaires de base
# -----------------------------------------------------------

JOUR_FR_TO_INT = {
    "lun": 1,
    "mar": 2,
    "mer": 3,
    "jeu": 4,
    "ven": 5,
    "sam": 6,
    "dim": 7,
}

REC_TYPE_TO_INT = {"e": 0, "u": 1}


def normalize_string(s: str):
    n = unicodedata.normalize("NFKD", s)
    res = "".join([c for c in n if not unicodedata.combining(c)])
    return res


def split_name(name: str) -> dict:
    return {"first_name": name.split(" ", 1)[0], "last_name": name.split(" ", 1)[1]}


def to_paris(dt: datetime) -> datetime:
    """Convertit un datetime vers l'heure locale Paris (heure stable)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
    return dt.astimezone(PARIS_TZ)


def find_next_day(weekday: str, start_date: date, weektype: str):
    start = start_date
    target_wd = JOUR_FR_TO_INT[weekday.lower()[:3]]
    rec_type = REC_TYPE_TO_INT.get(weektype)

    for offset in range(21):
        candidate = start + timedelta(days=offset)
        iso = candidate.isocalendar()
        if iso.weekday != target_wd:
            continue
        if rec_type is None or iso.week % 2 == rec_type:
            return candidate

    raise ValueError(f"Aucune date trouvée pour {weekday=} {start_date=} {weektype=}")


def combine_date_time(date_obj, time_str):
    time_str = time_str.strip().lower()

    if "h" in time_str:
        parts = time_str.split("h")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    else:
        raise ValueError(
            f"Format horaire invalide : {time_str}. Un h doit etre utilisé. Exemple 7h30 ou 12h ou 08h15."
        )

    return datetime.combine(
        date_obj, datetime.min.replace(hour=hour, minute=minute).time()
    ).astimezone(PARIS_TZ)


def next_july_31(from_date: date | None = None) -> date:
    """Renvoie le 31 juillet de la saison courante ou suivante."""
    d = from_date or date.today()
    cutoff = date(d.year, 7, 31)
    return cutoff if d <= cutoff else date(d.year + 1, 7, 31)


def get_week_parity(dt: datetime) -> str:
    """Renvoie 'even' ou 'odd' selon la semaine ISO (locale Paris)."""
    local_dt = to_paris(dt)
    return "even" if local_dt.isocalendar()[1] % 2 == 0 else "odd"


# -----------------------------------------------------------
# Génération d'occurrences récurrentes
# -----------------------------------------------------------


def iter_weekly_occurrences(
    start_at: datetime, end_date: date, same_type: bool = False
):
    """
    Génère les datetime des séances suivantes jusqu'à end_date incluse.
    - start_at : datetime de la première occurrence (tz Paris)
    - end_date : date locale (inclusive)
    - same_type : True → saute les semaines de parité différente
    """
    start_parity = get_week_parity(to_paris(start_at))
    current = to_paris(start_at) + timedelta(days=7)

    while current.date() <= end_date:

        if same_type:
            # saute une semaine tant qu'on ne retombe pas sur la meme parité ISO
            next_parity = get_week_parity(current)
            while next_parity != start_parity:
                current += timedelta(days=7)
                next_parity = get_week_parity(current)
        yield current
        current += timedelta(days=7)


def compare_model_instance(inst_new, inst_old):
    change_dict = {}
    for f in inst_new._meta.concrete_fields:
        name = f.name
        # évite les champs auto_now_add/auto_created (ex: created_at) et pk/id
        if (
            getattr(f, "auto_now_add", False)
            or getattr(f, "auto_created", False)
            or name in ("id", "pk")
        ):
            continue
        if getattr(inst_new, name) != getattr(inst_old, name):
            change_dict[name] = getattr(inst_new, name)

    return change_dict
