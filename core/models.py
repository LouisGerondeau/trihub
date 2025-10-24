# pyright: reportAttributeAccessIssue=false
import uuid

from core.utils import PARIS_TZ
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

User = get_user_model()

# -----------------------------------------------------------
# Core Models
# -----------------------------------------------------------


class Category(models.Model):
    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=150)

    def __str__(self):
        return self.label

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"


class Location(models.Model):
    name = models.CharField("Nom", max_length=100, unique=True)
    address = models.CharField("Adresse", max_length=200, blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Member(models.Model):
    first_name = models.CharField("Prénom", max_length=100)
    last_name = models.CharField("Nom", max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(
        "Numéro de téléphone", max_length=50, blank=True, null=True
    )
    birth_date = models.DateField("Date de naissance", blank=True, null=True)

    is_active = models.BooleanField("actif", default=True)
    is_head_coach = models.BooleanField("Coach Principal", default=False)

    qualifications = models.ManyToManyField(
        Category, verbose_name="Peut encadrer", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "Licencié"
        verbose_name_plural = "Licenciés"

    def __str__(self):
        return self.first_name + " " + self.last_name


class Recurrence(models.Model):
    MODE_CHOICES = [
        ("none", "Aucune"),
        ("weekly", "Hebdomadaire"),
        ("same_type", "Semaines du même type que la première"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    end_date = models.DateField(
        help_text="Date de fin (incluse), en heure locale Paris"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Récurrence"
        verbose_name_plural = "Récurrences"

    def __str__(self):
        return f"{self.get_mode_display()} → jusqu’au {self.end_date.isoformat()}"


class Session(models.Model):

    CONSTRAINT_CHOICES = [
        ("all", "Tous"),
        ("youth", "Jeunes"),
        ("adult", "Adultes"),
        ("team", "Équipe D2/D3"),
    ]
    category = models.ForeignKey(
        Category,
        verbose_name="Categorie",
        on_delete=models.PROTECT,  # empêche la suppression d’une categorie utilisée
        related_name="sessions",
        null=True,
        blank=True,  # temporaire si tu as déjà des données
    )
    start_at = models.DateTimeField("Jour et Horaire")
    duration_min = models.PositiveIntegerField("Durée", default=60)
    location = models.ForeignKey(
        Location,
        verbose_name="Lieu",
        on_delete=models.PROTECT,  # empêche la suppression d’un lieu utilisé
        related_name="sessions",
        null=True,
        blank=True,  # temporaire si tu as déjà des données
    )
    notes = models.TextField(blank=True, null=True)
    min_coaches = models.PositiveIntegerField("Encadrants minimum", default=1)
    constraint = models.CharField(
        "Groupes", max_length=10, choices=CONSTRAINT_CHOICES, default="all"
    )
    recurrence = models.ForeignKey(
        Recurrence,
        on_delete=models.PROTECT,  # empêche la suppression d'une récurrence liée
        null=True,
        blank=True,
        related_name="sessions",
        verbose_name="Récurrence",
    )

    coach = models.ManyToManyField(
        Member,
        through="CoachAssignment",
        verbose_name="coach encadrant",
        blank=True,
        related_name="sessions",
    )

    is_cancelled = models.BooleanField("Annulée", default=False)
    is_locked = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    week_iso = models.PositiveSmallIntegerField(
        "Numéro de Semaine", db_index=True, editable=False
    )

    # -------------------------------------------------------
    # Properties & Computed fields
    # -------------------------------------------------------

    @property
    def title_auto(self) -> str:
        local_dt = self.start_at.astimezone(PARIS_TZ)
        jour = local_dt.strftime("%a %-d %b %H:%M")
        loc = self.location.name if self.location else None
        if loc:
            return f"{self.category} — {jour} — {loc}"
        return f"{self.category} — {jour}"

    # -------------------------------------------------------
    # Validation
    # -------------------------------------------------------

    def clean(self):
        super().clean()

        # Cohérence durée
        if self.duration_min <= 0:
            raise ValidationError({"duration_min": "Durée invalide."})

    def __str__(self):
        return self.title_auto

    class Meta:
        verbose_name = "Séance"
        verbose_name_plural = "Séances"
        ordering = ["-start_at"]

    def save(self, *args, **kwargs):
        self.week_iso = self.start_at.astimezone(PARIS_TZ).isocalendar()[1]
        # met à jour le numéro de semaine avant sauvegarde
        super().save(*args, **kwargs)


class CoachAssignment(models.Model):
    STATUS_CHOICES = [("confirmed", "Confirmé"), ("withdrawn", "Désinscrit")]

    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="assignments"
    )
    coach = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="assignments"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="confirmed"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "coach"], name="unique_coach_per_session"
            )
        ]
        verbose_name = "Séance×Coach"
        verbose_name_plural = "Séance×Coach"

    def __str__(self):
        return f"{self.coach} → {self.session} ({self.status})"


# class AuditLog(models.Model):
#     ACTION_CHOICES = [
#         ("create_session", "Création séance"),
#         ("update_session", "Mise à jour séance"),
#         ("cancel_session", "Annulation séance"),
#         ("reactivate_session", "Réactivation séance"),
#         ("assign_coach", "Assignation encadrant"),
#         ("unassign_coach", "Désinscription encadrant"),
#         ("generate_recurrences", "Génération récurrence"),
#         ("bulk_update", "Modification en masse"),
#     ]

#     when = models.DateTimeField(auto_now_add=True)
#     actor_user = models.ForeignKey(
#         User, on_delete=models.SET_NULL, blank=True, null=True, related_name="logs"
#     )
#     actor_public_name = models.CharField(max_length=100, blank=True, null=True)
#     ip = models.GenericIPAddressField(blank=True, null=True)
#     action = models.CharField(max_length=50, choices=ACTION_CHOICES)
#     session = models.ForeignKey(
#         Session, on_delete=models.SET_NULL, blank=True, null=True, related_name="logs"
#     )
#     coach = models.ForeignKey(
#         Member, on_delete=models.SET_NULL, blank=True, null=True, related_name="logs"
#     )
#     details = models.JSONField(blank=True, null=True)
#     by_public = models.BooleanField(default=False)

#     class Meta:
#         ordering = ["-when"]

#     def __str__(self):
#         return f"[{self.when:%Y-%m-%d %H:%M}] {self.action}"
