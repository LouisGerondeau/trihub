from core.utils import PARIS_TZ, normalize_string
from django.contrib.auth import get_user_model
from django.db import models

# Create your models here.


class RaceTypeCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Catégorie de type de course"
        verbose_name_plural = "Catégories de types de course"

    def __str__(self):
        return self.name


class RaceType(models.Model):
    category = models.ForeignKey(
        "RaceTypeCategory",
        on_delete=models.CASCADE,
        verbose_name="Catégorie",
    )
    name = models.CharField("Nom du format", max_length=100)
    description = models.TextField(blank=True)

    # distances (en km)
    distance_swim = models.FloatField(
        "Distance en natation (km)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )
    distance_bike = models.FloatField(
        "Distance en vélo (km)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )
    distance_run = models.FloatField(
        "Distance en course à pied (km)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )
    distance_other = models.FloatField(
        "Distance autre (km)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )

    # dénivelés (en mètres)
    elevation_bike = models.FloatField(
        "Dénivelé vélo (m)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )
    elevation_run = models.FloatField(
        "Dénivelé course à pied (m)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )
    elevation_other = models.FloatField(
        "Dénivelé autre (m)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )

    class Meta:
        verbose_name = "Type de course"
        verbose_name_plural = "Types de course"

    def __str__(self):
        return f"{self.category.name} – {self.name}"


class SportEvent(models.Model):
    name = models.CharField("Nom de l'événement", max_length=200)
    description = models.TextField("Description", blank=True)
    city = models.CharField("Ville", max_length=100, blank=True)
    postal_code = models.CharField("Code postal", max_length=20, blank=True)
    country = models.CharField("Pays", max_length=100, blank=True)
    latitude = models.FloatField("Latitude", null=True, blank=True)
    longitude = models.FloatField("Longitude", null=True, blank=True)
    start_date = models.DateField("Date de début", null=True, blank=True)
    race_types = models.ManyToManyField(
        "RaceType",
        through="Race",
        blank=True,
        verbose_name="Courses proposées",
    )

    class Meta:
        verbose_name = "Événement sportif"
        verbose_name_plural = "Événements sportifs"
        ordering = ["-start_date", "name"]

    def __str__(self):
        return self.name


class Race(models.Model):
    sport_event = models.ForeignKey(
        SportEvent,
        on_delete=models.CASCADE,
        related_name="races",
        verbose_name="Événement sportif",
    )
    race_type = models.ForeignKey(
        RaceType,
        on_delete=models.PROTECT,
        related_name="races",
        verbose_name="Type de course",
    )
    start_date = models.DateField("Date de la course", null=True, blank=True)
    custom_name = models.CharField("Nom optionnel", max_length=150, blank=True)
    description = models.TextField("Description", blank=True)

    # distances (en km)
    distance_swim = models.FloatField(
        "Distance en natation (km)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable ou si ",
    )
    distance_bike = models.FloatField(
        "Distance en vélo (km)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )
    distance_run = models.FloatField(
        "Distance en course à pied (km)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )
    distance_other = models.FloatField(
        "Distance autre (km)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )

    # dénivelés (en mètres)
    elevation_bike = models.FloatField(
        "Dénivelé vélo (m)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )
    elevation_run = models.FloatField(
        "Dénivelé course à pied (m)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )
    elevation_other = models.FloatField(
        "Dénivelé autre (m)",
        null=True,
        blank=True,
        help_text="Laisser vide si non applicable",
    )

    class Meta:
        unique_together = ("sport_event", "race_type")
        verbose_name = "Course"
        verbose_name_plural = "Courses"
        ordering = ["start_date"]

    def __str__(self):
        label = self.custom_name or str(self.race_type)
        return f"{str(self.sport_event)} - {label}"

    def save(self, *args, **kwargs):
        if not self.date:
            self.date = self.sport_event.start_date
        super().save(*args, **kwargs)

    @property
    def effective_date(self):
        """Retourne la date propre à la course, ou celle de l’événement si non renseignée."""
        return self.date or self.sport_event.start_date
