from core.models import Category, Member, Session
from django.db.models import Count, F, Q
from django.utils import timezone


def get_public_sessions(category_code: str, params: dict):
    now = timezone.now()

    qs = Session.objects.filter(is_cancelled=False, start_at__gte=now)

    if category_code != "all":
        qs = qs.filter(category__code=category_code)

    qs = (
        qs.select_related("location", "category")
        .prefetch_related("assignments__coach")
        .annotate(
            confirmed_cnt=Count(
                "assignments", filter=Q(assignments__status="confirmed")
            )
        )
        .order_by("start_at", "pk")
    )

    # Filtres GET
    if loc_id := params.get("loc"):
        qs = qs.filter(location_id=loc_id)

    if dow := params.get("dow"):
        if dow.isdigit():
            qs = qs.filter(start_at__week_day=int(dow))

    if coach_q := params.get("coach"):
        qs = (
            qs.filter(assignments__status="confirmed")
            .filter(
                Q(assignments__coach__first_name__icontains=coach_q)
                | Q(assignments__coach__last_name__icontains=coach_q)
            )
            .distinct()
        )

    if params.get("needs") == "1":
        qs = qs.filter(confirmed_cnt__lt=F("min_coaches"))

    return qs


def get_cat_coaches(category_code: str):
    if category_code == "all":
        return Member.objects.all().prefetch_related("qualifications")

    try:
        cat = Category.objects.get(code=category_code)
    except Category.DoesNotExist:
        return Member.objects.none()

    return Member.objects.filter(
        Q(is_head_coach=True) | Q(qualifications=cat)
    ).prefetch_related("qualifications")


def build_available_coaches(qs, cat_coaches):
    available_coaches = {}
    qualif_map = {c.pk: {q.pk for q in c.qualifications.all()} for c in cat_coaches}
    for s in qs:
        assigned_ids = {
            a.coach_id for a in s.assignments.all() if a.status == "confirmed"
        }

        available_coaches[s.pk] = [
            {"id": c.pk, "name": f"{c.first_name} {c.last_name}"}
            for c in cat_coaches
            if c.pk not in assigned_ids
            and (s.category is None or s.category.pk in qualif_map[c.pk])
        ]

    return available_coaches
