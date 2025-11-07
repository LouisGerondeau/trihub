from ast import Delete
from copy import deepcopy

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import MultipleObjectsReturned
from django.db import transaction
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.translation import ngettext

from .forms import RaceTypeForm, SportEventAdminForm
from .models import Race, RaceType, RaceTypeCategory, SportEvent


@admin.register(RaceTypeCategory)
class RaceTypeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(RaceType)
class RaceTypeAdmin(admin.ModelAdmin):
    form = RaceTypeForm
    list_display = (
        "name",
        "category",
        "distance_swim",
        "distance_bike",
        "distance_run",
    )
    list_filter = ("category",)
    search_fields = ("name", "category__name")


@admin.register(SportEvent)
class SportEventAdmin(admin.ModelAdmin):
    form = SportEventAdminForm
    list_display = ("name", "city", "country", "start_date")
    list_filter = ("country", "start_date")
    search_fields = ("name", "city", "country")
    date_hierarchy = "start_date"
    ordering = ("-start_date", "name")


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = (
        "custom_name",
        "sport_event",
        "race_type",
        "effective_date",
        "distance_swim",
        "distance_bike",
        "distance_run",
    )
    list_filter = ("race_type__category", "race_type", "sport_event__start_date")
    search_fields = ("custom_name", "sport_event__name", "race_type__name")
    list_select_related = ("race_type", "race_type__category", "sport_event")
    autocomplete_fields = ("sport_event", "race_type")
    # ordering = ("effective_date",)

    # lecture seule (utile pour le champ calculé)
    readonly_fields = ("effective_date",)
