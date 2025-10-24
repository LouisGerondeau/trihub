# core/admin.py
# pyright: reportAttributeAccessIssue=false

from django.contrib import admin, messages
from django import forms
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .models import (
    Member,
    Qualification,
    Session,
    SessionQualification,
    CoachAssignment,
    AuditLog,
)

# ---------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = "__all__"
        widgets = {
            "qualifications": forms.CheckboxSelectMultiple,  # <-- checkboxes au lieu du widget admin standard
        }

    class Media:
        css = {"all": ("admin_pills.css",)}
        js = ("admin_pills.js",)


class SessionForm(forms.ModelForm):
    # Champ virtuel pour pilotage via checkboxes
    required_quals = forms.ModelMultipleChoiceField(
        queryset=Qualification.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Qualifications requises",
    )

    class Meta:
        model = Session
        fields = "__all__"
        widgets = {
            "start_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local", "step": 60},
            ),
            "recurrence_until": forms.DateInput(
                format="%Y-%m-%d", attrs={"type": "date"}
            ),
            "constraint": forms.Select(),
            "recurrence_freq": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # initialiser le champ virtuel depuis Requirement
        if self.instance and self.instance.pk:
            self.fields["required_quals"].initial = list(
                self.instance.requirements.values_list("qualification_id", flat=True)
            )

    def save(self, commit=True):
        instance: Session = super().save(commit)
        # Sync des Requirement depuis required_quals
        selected = set(
            self.cleaned_data.get("required_quals", []).values_list("id", flat=True)
        )
        current = set(instance.requirements.values_list("qualification_id", flat=True))

        # Ajouts
        for qid in selected - current:
            SessionQualification.objects.create(session=instance, qualification_id=qid)

        # Suppressions
        for qid in current - selected:
            instance.requirements.filter(qualification_id=qid).delete()

        return instance

    class Media:
        css = {"all": ("admin_pills.css",)}
        js = ("admin_pills.js",)


# ---------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------


class RequirementInline(admin.TabularInline):
    model = SessionQualification
    extra = 1
    verbose_name = "Qualification requise"
    verbose_name_plural = "Qualifications requises"


class CoachAssignmentInline(admin.TabularInline):
    model = CoachAssignment
    extra = 1
    autocomplete_fields = ["coach"]
    verbose_name = "Encadrant assigné"
    verbose_name_plural = "Encadrants assignés"
    readonly_fields = ["created_at", "withdrawn_at", "status"]
    fields = ["coach", "role", "status", "created_at", "withdrawn_at"]


# ---------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------


class WeekParityFilter(admin.SimpleListFilter):
    title = "Parité semaine"
    parameter_name = "week_parity"

    def lookups(self, request, model_admin):
        return [("even", "Semaines paires"), ("odd", "Semaines impaires")]

    def queryset(self, request, queryset):
        if self.value() == "even":
            return [s for s in queryset if s.week_parity == "even"]
        if self.value() == "odd":
            return [s for s in queryset if s.week_parity == "odd"]
        return queryset


class MissingCoachesFilter(admin.SimpleListFilter):
    title = "Manque d'encadrants"
    parameter_name = "missing_coaches"

    def lookups(self, request, model_admin):
        return [("yes", "Oui"), ("no", "Non")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            ids = [
                s.id
                for s in queryset
                if s.assignments.filter(status="confirmed").count() < s.min_coaches
            ]
            return queryset.filter(id__in=ids)
        if self.value() == "no":
            ids = [
                s.id
                for s in queryset
                if s.assignments.filter(status="confirmed").count() >= s.min_coaches
            ]
            return queryset.filter(id__in=ids)
        return queryset


# ---------------------------------------------------------------------
# Admin classes
# ---------------------------------------------------------------------


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    form = MemberForm
    list_display = ["first_name", "last_name", "email", "is_head_coach", "is_active"]
    list_filter = ["is_head_coach", "is_active"]
    search_fields = ["first_name", "last_name", "email"]

    class Media:
        css = {"all": ("admin_pills.css",)}
        js = ("admin_pills.js",)


@admin.register(Qualification)
class QualificationAdmin(admin.ModelAdmin):
    list_display = ["code", "label"]
    search_fields = ["code", "label"]


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    # form = SessionForm

    list_display = [
        "title_auto",
        "start_at",
        "location",
        "kind",
        "week_iso",
        "is_cancelled",
        "min_coaches",
    ]
    list_filter = [
        "kind",
        "location",
        "constraint",
        "is_cancelled",
        WeekParityFilter,
        MissingCoachesFilter,
    ]
    search_fields = ["location", "notes"]
    exclude = ("parent_session",)
    readonly_fields = ["created_by", "created_at", "updated_at"]
    inlines = [CoachAssignmentInline, RequirementInline]

    # formfield_overrides = {
    #     models.TimeField: {
    #         "widget": forms.TimeInput(
    #             format="%H:%M", attrs={"type": "time", "step": 60}
    #         )
    #     },
    #     models.DateField: {"widget": forms.DateInput(attrs={"type": "date"})},
    # }

    # -------------------------------------------------------------
    # Hooks
    # -------------------------------------------------------------

    def save_model(self, request, obj, form, change):
        """Auto-assign creator on creation"""
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # -------------------------------------------------------------
    # Actions customisées
    # -------------------------------------------------------------

    @admin.action(description="Générer les séances récurrentes")
    def generate_recurrences_action(self, request, queryset):
        total_created = 0
        for session in queryset:
            if session.recurrence_freq != "none":
                created = session.generate_recurrences(copy_assignments=True)
                total_created += len(created)
        messages.success(
            request,
            f"✅ {total_created} séances générées à partir des récurrences sélectionnées.",
        )

    @admin.action(description="Annuler les séances sélectionnées")
    def cancel_sessions(self, request, queryset):
        count = queryset.update(is_cancelled=True)
        messages.warning(request, f"🚫 {count} séance(s) annulée(s).")

    @admin.action(description="Réactiver les séances sélectionnées")
    def reactivate_sessions(self, request, queryset):
        count = queryset.update(is_cancelled=False)
        messages.success(request, f"♻️ {count} séance(s) réactivée(s).")

    actions = [
        "generate_recurrences_action",
        "cancel_sessions",
        "reactivate_sessions",
    ]


@admin.register(SessionQualification)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ["session", "qualification"]
    list_filter = ["qualification"]
    search_fields = ["session__location", "qualification__label"]


@admin.register(CoachAssignment)
class CoachAssignmentAdmin(admin.ModelAdmin):
    list_display = ["session", "coach", "status", "role", "created_at"]
    list_filter = ["status", "role"]
    search_fields = ["coach__first_name", "coach__last_name", "session__location"]
    autocomplete_fields = ["session", "coach"]
    readonly_fields = ["created_at", "withdrawn_at"]

    def save_model(self, request, obj, form, change):
        # validation éligibilité faite dans .clean()
        super().save_model(request, obj, form, change)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["when", "action", "actor_user", "session", "coach", "by_public"]
    list_filter = ["action", "by_public"]
    search_fields = ["actor_user__username", "session__location", "coach__last_name"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    ordering = ["-when"]
