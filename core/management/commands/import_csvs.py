import csv
from datetime import datetime
from pathlib import Path

from core.models import Category, Location, Member, Session
from core.services.recurrence import generate_series
from core.utils import combine_date_time, find_next_day, split_name
from django.core.management.base import BaseCommand, CommandError

REC_TYPE_TO_MODE = {"e": "same_type", "u": "same_type", "w": "weekly"}


class Command(BaseCommand):
    help = """Importe des membres factices depuis trois CSV 
         - core/fixtures/cat_data.csv , 
         - core/fixtures/member_data.csv 
         - core/fixtures/session_data.csv
         """

    def add_arguments(self, parser):
        parser.add_argument(
            "start_date", type=str, help="Date de début (format jj/mm/aaaa)"
        )
        parser.add_argument(
            "end_date", type=str, help="Date de fin (format jj/mm/aaaa)"
        )

    def handle(self, *args, **options):
        try:
            start_date = datetime.strptime(options["start_date"], "%d/%m/%Y").date()
            end_date = datetime.strptime(options["end_date"], "%d/%m/%Y").date()
        except ValueError:
            raise CommandError(
                "Les dates doivent être au format jj/mm/aaaa (ex: 08/09/2025)"
            )

        fixtures = Path(__file__).resolve().parents[2] / "fixtures" / "cat_data.csv"
        with open(fixtures, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                print(row)
                Category.objects.get_or_create(
                    code=row["code"],
                    label=row["label"],
                )
        self.stdout.write(self.style.SUCCESS("Import des catégories terminé."))
        fixtures = Path(__file__).resolve().parents[2] / "fixtures" / "session_data.csv"
        with open(fixtures, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                start_date = datetime.strptime("08/09/2025", "%d/%m/%Y").date()
                end_date = datetime.strptime("15/07/2026", "%d/%m/%Y").date()
                attrs = {
                    "start_at": combine_date_time(
                        find_next_day(row["week_day"], start_date, row["rec_type"]),
                        row["time"],
                    ),
                    "duration_min": int(row["duration"]),
                    "group": row["group"],
                    "min_coaches": int(row["min_coaches"]),
                }
                s = Session(**attrs)
                s.category = Category.objects.get(code=row["cat"])
                loc, _ = Location.objects.get_or_create(name=row["loc"])
                s.location = loc
                s.save()
                for i in range(1, 9):
                    coach_name = row.get(f"coach{i}", "").strip()
                    if coach_name != "":
                        c, _ = Member.objects.get_or_create(**split_name(coach_name))
                        c.qualifications.add(s.category)
                        s.coach.add(c)
                sname = s.__str__()
                if REC_TYPE_TO_MODE.get(row["rec_type"], False):
                    generate_series(s, REC_TYPE_TO_MODE[row["rec_type"]], end_date)
                self.stdout.write(
                    self.style.SUCCESS(f"Import de la session {sname} terminé.")
                )
            self.stdout.write(self.style.SUCCESS(f"Import des sessions terminé."))
        fixtures = Path(__file__).resolve().parents[2] / "fixtures" / "member_data.csv"
        with open(fixtures, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                c, _ = Member.objects.get_or_create(**split_name(row["name"]))
                for cn in row["cat"].split(","):
                    cat = Category.objects.get(code=cn)
                    c.qualifications.add(cat)
                self.stdout.write(
                    self.style.SUCCESS(f"Import de l'encadrant {c} terminé.")
                )

            self.stdout.write(self.style.SUCCESS(f"Import des encadrants terminé."))
