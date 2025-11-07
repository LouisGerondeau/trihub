import csv
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from trouvetacourse.models import RaceType, RaceTypeCategory

REC_TYPE_TO_MODE = {"e": "same_type", "u": "same_type", "w": "weekly"}


class Command(BaseCommand):
    help = """Importe les race_type et race_type_category de 
         trouvetacourse/fixtures/race_type_data.csv , 
         """

    def handle(self, *args, **options):

        fixtures = (
            Path(__file__).resolve().parents[2] / "fixtures" / "race_type_data.csv"
        )
        with open(fixtures, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                print(row)
                rtc, _ = RaceTypeCategory.objects.get_or_create(name=row["category"])
                s = RaceType(
                    name=row["race_type"],
                    category=rtc,
                    distance_swim=row["distance_swim"].strip() or None,
                    distance_bike=row["distance_bike"].strip() or None,
                    distance_run=row["distance_run"].strip() or None,
                )
                s.save()
        self.stdout.write(self.style.SUCCESS("Import des race types terminé."))
