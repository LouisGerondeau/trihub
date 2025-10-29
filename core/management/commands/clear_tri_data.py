from core.models import Category, CoachAssignment, Location, Member, Recurrence, Session
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Supprime toutes les données métiers"

    def handle(self, *args, **kwargs):
        for model in [Session, Category, Member, Location, Recurrence, CoachAssignment]:
            deleted, _ = model.objects.all().delete()
            self.stdout.write(f"{model.__name__}: {deleted} objets supprimés")
