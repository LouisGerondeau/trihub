from ast import Delete
from copy import deepcopy

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import MultipleObjectsReturned
from django.db import transaction
from django.forms import CheckboxSelectMultiple
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.translation import ngettext

from .admin_filters import (
    CoachNameFilter,
    LocationFilter,
    LockedCancelledFilter,
    MemberFilter,
    WeekIsoFilter,
)
from .forms import SessionAdminForm
from .models import Category, CoachAssignment, Location, Member, Recurrence, Session
from .services.recurrence import (
    generate_series,
    propagate_coach_assignments,
    propagate_form_fields,
)
from .utils import compare_model_instance

### INLINES ###


class CoachAssignmentInline(admin.StackedInline):
    model = CoachAssignment
    extra = 1
    autocomplete_fields = ["coach"]
    verbose_name = "Encadrant assigné"
    verbose_name_plural = "Encadrants assignés"
    fields = ["coach", "status"]


class MemberAdminForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = "__all__"
        widgets = {
            "qualifications": CheckboxSelectMultiple,
        }


### Register files ###


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["code", "label"]  # utile pour l'autocomplete


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    search_fields = ["name", "address"]


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    form = MemberAdminForm
    search_fields = ["first_name", "last_name"]
    list_filter = [MemberFilter, "qualifications"]


@admin.register(Recurrence)
class RecurrenceAdmin(admin.ModelAdmin):
    list_display = ("id", "mode", "end_date", "created_at")
    readonly_fields = ("id", "mode", "end_date", "created_at")
    ordering = ["-created_at"]
    search_fields = ["id"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("title_auto", "week_iso")
    list_filter = [
        WeekIsoFilter,
        CoachNameFilter,
        LocationFilter,
        "category",
        LockedCancelledFilter,
    ]
    form = SessionAdminForm
    autocomplete_fields = ["location"]
    readonly_fields = ["week_iso", "created_at"]
    exclude = ["recurrence", "created_by", "is_locked"]
    ordering = ["start_at"]
    inlines = [CoachAssignmentInline]
    actions = ["cancel_session"]
    list_select_related = ("location", "category")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("assignments__coach").select_related(
            "category", "location"
        )

    ## Change actions

    @admin.action(description="Annuler les sessions sélectionnées")
    def cancel_session(self, request, queryset):
        cancelled = queryset.update(is_cancelled=True)
        self.message_user(
            request,
            ngettext(
                "%d séance a été annulée.",
                "%d séances ont été annulées.",
                cancelled,
            )
            % cancelled,
            messages.SUCCESS,
        )

    def get_actions(self, request):
        actions = super().get_actions(request)
        # if "delete_selected" in actions:
        #     del actions["delete_selected"]
        return actions

    # ------------------------------------------------------------
    # Gestion dynamique des champs à afficher
    # ------------------------------------------------------------

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if obj and obj.recurrence:
            for name in ("recurrence_mode", "recurrence_end_date"):
                if name in fields:
                    fields.remove(name)
        else:
            fields.remove("recurrence_info")
        return fields

    def save_model(self, request, obj, form, change):

        if "_propagate_following" in request.POST:
            propagate_form_fields(obj, form.changed_data)
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        """
        si click sur modifier cette séance et les suivantes
        on sauve l'état de la relation m2m avant le save related
        """
        if "_propagate_following" in request.POST:
            obj = form.instance
            cas = CoachAssignment.objects.filter(session=obj)
            cas_old = [deepcopy(c) for c in cas]
        super().save_related(request, form, formsets, change)

        if "_propagate_following" in request.POST:
            cas_saved = CoachAssignment.objects.filter(session=obj)
            propagate_coach_assignments(cas_old, cas_saved)

        """ cas d'une création de série : recurrence_request est présent en attribut du form
        on génère la série après le save related puisqu'on a besoin d'avoir les entités coachassignments en base.
        """

        if hasattr(form, "_recurrence_request"):
            mode, end_date = form._recurrence_request  # type: ignore
            source = form.instance
            generate_series(session=source, mode=mode, end_date=end_date)


@admin.register(CoachAssignment)
class CoachAssignmentAdmin(admin.ModelAdmin):
    pass
