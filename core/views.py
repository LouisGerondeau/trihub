# core/views.py
from core.services.public_view_utils import (
    build_available_coaches,
    get_cat_coaches,
    get_public_sessions,
)
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Category, CoachAssignment, Location, Member, Session


def coach_page(request, coach_slug):
    qs = Member.objects.all()


def public_sessions_by_category(request, category_code):

    # extraire les paramètres GET
    filters = {
        "loc_id": request.GET.get("loc"),
        "dow": request.GET.get("dow"),
        "coach_q": request.GET.get("coach"),
        "needs": request.GET.get("needs") == "1",  # bool
    }

    qs = get_public_sessions(category_code, filters)
    # Pagination : 100 séances par page
    paginator = Paginator(qs, 100)
    page = request.GET.get("page")

    try:
        sessions_page = paginator.page(page)
    except PageNotAnInteger:
        sessions_page = paginator.page(1)
    except EmptyPage:
        sessions_page = paginator.page(paginator.num_pages)

    if category_code == "all":
        page_title = "Toutes les séances"
    else:
        cat = get_object_or_404(Category, code=category_code)
        page_title = f"Séances de {cat.label}"

    cat_coaches = get_cat_coaches(category_code)

    # regroupement par (année, semaine)
    weeks = {}
    available_coaches = build_available_coaches(qs, cat_coaches)
    for s in sessions_page:
        year, week, _ = s.start_at.isocalendar()
        weeks.setdefault((year, week), []).append(s)

    return render(
        request,
        "core/public_sessions.html",
        {
            "origin": request.get_full_path(),
            "weeks": sorted(weeks.items(), key=lambda x: x[0]),
            "page_obj": sessions_page,  # 👈 important
            "paginator": paginator,
            "locations": Location.objects.all().only("id", "name"),
            "params": request.GET,
            "available_coaches": available_coaches,
            "page_title": page_title,
        },
    )


def assign_confirm(request):
    session_id = request.GET.get("session_id")
    coach_id = request.GET.get("coach_id")
    origin = request.GET.get("origin", "/public/category/all")
    ses = get_object_or_404(Session, pk=session_id)
    coach = get_object_or_404(Member, pk=coach_id)
    cat = ses.category
    return render(
        request,
        "core/assign_confirm.html",
        {"session": ses, "coach": coach, "origin": origin},
    )


def assign_do(request):
    if request.method != "POST":
        return redirect(request.GET.get("origin", "/public/category/all"))
    session_id = request.POST.get("session_id")
    coach_id = request.POST.get("coach_id")
    origin = request.POST.get("origin", "/public/category/all")
    ses = get_object_or_404(Session, pk=session_id)
    coach = get_object_or_404(Member, pk=coach_id)
    cat = ses.category
    # Vérifie la qualification du coach
    ok = coach.is_head_coach or (
        cat and coach.qualifications.filter(pk=cat.pk).exists()
    )
    # si coach non qualifié, on dit que c'est pas possible
    if not ok:
        return render(
            request,
            "core/assign_issue.html",
            {"session": ses, "coach": coach, "origin": origin},
        )  # implement later : redirect to special page for more explanation
    if ok:
        ca, i = CoachAssignment.objects.get_or_create(session=ses, coach=coach)
        print(ca, i)
        ca.status = "confirmed"
        ca.save()
    return redirect(origin)


def unassign_confirm(request):
    session_id = request.GET.get("session_id")
    coach_id = request.GET.get("coach_id")
    origin = request.GET.get("origin", "/public/category/all")
    ses = get_object_or_404(Session, pk=session_id)
    coach = get_object_or_404(Member, pk=coach_id)
    ca = get_object_or_404(
        CoachAssignment, session=ses, coach=coach, status="confirmed"
    )

    return render(
        request,
        "core/unassign_confirm.html",
        {"session": ses, "coach": coach, "origin": origin},
    )


def unassign_do(request):
    if request.method != "POST":
        return redirect(request.GET.get("origin", "/public/category/all"))
    session_id = request.POST.get("session_id")
    coach_id = request.POST.get("coach_id")
    origin = request.POST.get("origin", "/public/category/all")
    ca = CoachAssignment.objects.filter(
        session_id=session_id, coach_id=coach_id, status="confirmed"
    ).first()

    if ca:
        ca.status = "withdrawn"
        ca.save(update_fields=["status"])

    return redirect(origin)
