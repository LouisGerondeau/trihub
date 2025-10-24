# core/admin_filters.py
from django.contrib import admin
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class InputFilter(admin.SimpleListFilter):
    # doc : https://hakibenita.com/how-to-add-a-text-filter-to-django-admin

    template = "admin/filters/input_filter.html"

    def lookups(self, request, model_admin):
        # Dummy, required to show the filter.
        return ((),)

    def choices(self, changelist):
        # Grab only the "all" option.
        all_choice = next(super().choices(changelist))  # type: ignore
        all_choice["query_parts"] = (
            (k, v)
            for k, v in changelist.get_filters_params().items()
            if k != self.parameter_name
        )
        yield all_choice


class WeekIsoFilter(InputFilter):
    parameter_name = "week_iso"
    title = _("Semaine ISO")

    def queryset(self, request, queryset):
        if self.value() is not None:
            week_iso = self.value()
            if not week_iso:  # None ou chaîne vide
                return
            try:
                week = int(week_iso)
            except ValueError:
                return queryset.none()

            return queryset.filter(Q(week_iso=week_iso))


class LocationFilter(InputFilter):
    parameter_name = "location_name"
    title = _("Lieu d'entrainement")

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        return queryset.filter(Q(location__name__icontains=term))


class MemberFilter(InputFilter):
    parameter_name = "member_name"
    title = _("Nom du licencié")

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        any_name = Q()
        for bit in term.split():
            any_name &= Q(first_name__icontains=bit) | Q(last_name__icontains=bit)

        return queryset.filter(any_name)


class CoachNameFilter(InputFilter):
    parameter_name = "coach_name"
    title = _("Nom de l'encadrant")

    def queryset(self, request, queryset):
        term = self.value()
        if term is None:
            return

        any_name = Q()
        for bit in term.split():
            any_name &= Q(coach__first_name__icontains=bit) | Q(
                coach__last_name__icontains=bit
            )

        return queryset.filter(any_name)


class LockedCancelledFilter(admin.SimpleListFilter):
    title = "État des séances"
    parameter_name = "locked_cancelled"

    def lookups(self, request, model_admin):
        # Deux options seulement
        return [("active", "Actives uniquement"), ("all", "Toutes les séances")]

    def queryset(self, request, queryset):
        v = self.value()
        if v in (None, "active"):
            return queryset.filter(is_locked=False, is_cancelled=False)
        if v == "all":
            return queryset
        return queryset

    # Supprime l’option "Tout" de l’UI et force "active" par défaut
    def choices(self, changelist):
        # Actives uniquement (sélectionnée si valeur absente ou 'active')
        yield {
            "selected": self.value() in (None, "active"),
            "query_string": changelist.get_query_string(
                {self.parameter_name: "active"}
            ),
            "display": "Actives uniquement",
        }
        # Toutes les séances
        yield {
            "selected": self.value() == "all",
            "query_string": changelist.get_query_string({self.parameter_name: "all"}),
            "display": "Toutes les séances",
        }
