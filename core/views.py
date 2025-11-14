# core/views.py
from core.services.public_view_utils import (
    add_filters_to_qs,
    build_available_coaches,
    get_cat_coaches,
    get_public_sessions,
)
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Category, CoachAssignment, Location, Member, Session


def public_homepage(request):
    cats = Category.objects.all()
    ms = Member.objects.all()
    dictslug = {str(m): m.slug for m in ms}
    return render(request, "core/homepage.html", {"cats": cats, "dictslug": dictslug})


def public_sessions_by_coach(request, coach_slug):
    filters = {
        "loc_id": request.GET.get("loc"),
        "dow": request.GET.get("dow"),
        "coach_q": request.GET.get("coach"),
        "needs": request.GET.get("needs") == "1",  # bool
    }
    ms = Member.objects.all()
    coach = next((m for m in ms if m.slug == coach_slug), None)
    if not coach:
        raise Http404("Coach non trouvé")
    if coach.is_head_coach:
        categories = Category.objects.all()
    else:
        categories = Category.objects.filter(Q(coaches=coach))
    now = timezone.now()
    qs = (
        Session.objects.filter(
            category__in=categories, is_cancelled=False, start_at__gte=now
        )
        .select_related("location", "category")
        .prefetch_related("assignments__coach", "coach")
        .annotate(
            confirmed_cnt=Count(
                "assignments", filter=Q(assignments__status="confirmed")
            )
        )
        .order_by("start_at", "pk")
    )
    qs = add_filters_to_qs(qs, filters)
    # Pagination : 50 séances par page
    paginator = Paginator(qs, 50)
    page = request.GET.get("page")

    try:
        sessions_page = paginator.page(page)
    except PageNotAnInteger:
        sessions_page = paginator.page(1)
    except EmptyPage:
        sessions_page = paginator.page(paginator.num_pages)
    weeks = {}
    for s in sessions_page:
        cids = [a.coach_id for a in s.assignments.all() if a.status == "confirmed"]
        year, week, _ = s.start_at.isocalendar()
        weeks.setdefault((year, week), []).append([s, coach.pk in cids])
    return render(
        request,
        "core/public_sessions_by_coach.html",
        {
            "origin": request.get_full_path(),
            "coach": coach,
            "weeks": sorted(weeks.items(), key=lambda x: x[0]),
            "page_obj": sessions_page,
            "paginator": paginator,
            "locations": Location.objects.all().only("id", "name"),
            "params": request.GET,
        },
    )


def public_sessions_by_category(request, category_code):

    # extraire les paramètres GET
    filters = {
        "loc_id": request.GET.get("loc"),
        "dow": request.GET.get("dow"),
        "coach_q": request.GET.get("coach"),
        "needs": request.GET.get("needs") == "1",  # bool
    }

    qs = get_public_sessions(category_code, filters)
    # Pagination : 50 séances par page
    paginator = Paginator(qs, 50)
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
    available_coaches = build_available_coaches(sessions_page, cat_coaches)
    for s in sessions_page:
        year, week, _ = s.start_at.isocalendar()
        weeks.setdefault((year, week), []).append(s)

    return render(
        request,
        "core/public_sessions_by_cat.html",
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
        )
    if ok:
        ca, i = CoachAssignment.objects.get_or_create(session=ses, coach=coach)
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
