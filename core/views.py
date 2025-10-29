# core/views.py
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Category, CoachAssignment, Location, Member, Session


def public_sessions(request, category_code):
    cat = get_object_or_404(Category, code=category_code)
    now = timezone.now()

    qs = (
        Session.objects.filter(category=cat, is_cancelled=False, start_at__gte=now)
        .select_related("location", "category")
        .prefetch_related("assignments__coach")
        .annotate(
            confirmed_cnt=Count(
                "assignments", filter=Q(assignments__status="confirmed")
            )
        )
        .order_by("start_at")
    )

    cat_coaches = Member.objects.filter(Q(is_head_coach=True) | Q(qualifications=cat))

    # --- Filtres ---
    loc_id = request.GET.get("loc")
    if loc_id:
        qs = qs.filter(location_id=loc_id)

    dow = request.GET.get("dow")
    if dow and dow.isdigit():
        qs = qs.filter(start_at__week_day=int(dow))

    coach_q = request.GET.get("coach")
    if coach_q:
        qs = (
            qs.filter(assignments__status="confirmed")
            .filter(
                Q(assignments__coach__first_name__icontains=coach_q)
                | Q(assignments__coach__last_name__icontains=coach_q)
            )
            .distinct()
        )

    # manque encadrants (on/off)
    if request.GET.get("needs") == "1":
        qs = qs.filter(confirmed_cnt__lt=F("min_coaches"))

    # regroupement par (année, semaine)
    weeks = {}
    available_coaches = {}
    for s in qs:
        assigned_ids = {
            a.coach_id for a in s.assignments.all() if a.status == "confirmed"  # type: ignore
        }
        available_coaches[s.pk] = [
            {"id": c.pk, "name": f"{c.first_name} {c.last_name}"}
            for c in cat_coaches
            if c.pk not in assigned_ids
        ]
        year, week, _ = s.start_at.isocalendar()
        weeks.setdefault((year, week), []).append(s)

    return render(
        request,
        "core/public_sessions.html",
        {
            "category": cat,
            "weeks": sorted(weeks.items(), key=lambda x: x[0]),
            "locations": Location.objects.all().only("id", "name"),
            "params": request.GET,
            "available_coaches": available_coaches,
        },
    )


def assign_confirm(request, category_code, session_id):
    cat = get_object_or_404(Category, code=category_code)
    ses = get_object_or_404(Session, pk=session_id, category=cat, is_cancelled=False)
    coach_id = request.GET.get("coach_id")
    coach = None
    if coach_id:
        coach = get_object_or_404(Member, pk=coach_id)
        # re-vérif qualif
        ok = coach.is_head_coach or coach.qualifications.filter(pk=cat.pk).exists()
        if not ok:  # refuse si non qualifié
            return redirect("public_sessions", category_code=category_code)
    return render(
        request,
        "core/assign_confirm.html",
        {"category": cat, "session": ses, "coach": coach},
    )


def assign_do(request, category_code, session_id):
    if request.method != "POST":
        return redirect(
            "assign_confirm", category_code=category_code, session_id=session_id
        )
    cat = get_object_or_404(Category, code=category_code)
    ses = get_object_or_404(Session, pk=session_id, category=cat, is_cancelled=False)
    coach_id = request.POST.get("coach_id")
    coach = get_object_or_404(Member, pk=coach_id)
    ok = coach.is_head_coach or coach.qualifications.filter(pk=cat.pk).exists()
    if ok:
        ca, i = CoachAssignment.objects.get_or_create(session=ses, coach=coach)
        print(ca, i)
        ca.status = "confirmed"
        ca.save()
    return redirect("public_sessions", category_code=category_code)


def unassign_confirm(request, category_code, session_id, coach_id):
    cat = get_object_or_404(Category, code=category_code)
    ses = get_object_or_404(Session, pk=session_id, category=cat)
    coach = get_object_or_404(Member, pk=coach_id)
    ca = get_object_or_404(
        CoachAssignment, session=ses, coach=coach, status="confirmed"
    )

    return render(
        request,
        "core/unassign_confirm.html",
        {
            "category": cat,
            "session": ses,
            "coach": coach,
            "ca": ca,
        },
    )


def unassign_do(request, category_code, session_id, coach_id):
    if request.method != "POST":
        return redirect("public_sessions", category_code=category_code)

    cat = get_object_or_404(Category, code=category_code)
    ses = get_object_or_404(Session, pk=session_id, category=cat)
    ca = CoachAssignment.objects.filter(
        session=ses, coach_id=coach_id, status="confirmed"
    ).first()

    if ca:
        ca.status = "withdrawn"
        ca.save(update_fields=["status"])

    return redirect("public_sessions", category_code=category_code)
