from django import forms
from django.core.exceptions import ValidationError
from django.forms import CheckboxSelectMultiple
from django.utils import timezone

from .models import Race, RaceType, SportEvent


class RaceTypeForm(forms.ModelForm):
    class Meta:
        model = RaceType
        fields = "__all__"
        widgets = {
            # forcer un input "text" au lieu de "number"
            "distance_swim": forms.TextInput(attrs={"placeholder": "0.00"}),
            "distance_bike": forms.TextInput(attrs={"placeholder": "0.00"}),
            "distance_run": forms.TextInput(attrs={"placeholder": "0.00"}),
            "distance_other": forms.TextInput(attrs={"placeholder": "0.00"}),
            "elevation_bike": forms.TextInput(),
            "elevation_run": forms.TextInput(),
            "elevation_other": forms.TextInput(),
        }


class SportEventAdminForm(forms.ModelForm):
    race_types = forms.ModelMultipleChoiceField(
        queryset=RaceType.objects.all().order_by("category__name", "name"),
        widget=CheckboxSelectMultiple,
        required=False,
        label="Courses proposées",
    )

    class Meta:
        model = SportEvent
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # précocher les types déjà liés via Race
            existing_types = Race.objects.filter(sport_event=self.instance).values_list(
                "race_type_id", flat=True
            )
            self.fields["race_types"].initial = existing_types

    def save(self, commit=True):
        obj = super().save(commit=False)
        if commit:
            obj.save()
            selected = self.cleaned_data["race_types"]

            # supprimer les relations obsolètes
            Race.objects.filter(sport_event=obj).exclude(
                race_type__in=selected
            ).delete()

            # ajouter les nouvelles
            for rt in selected:
                Race.objects.get_or_create(
                    sport_event=obj, race_type=rt, defaults={"date": obj.date}
                )

        return obj
