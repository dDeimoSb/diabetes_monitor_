from django.core.management.base import BaseCommand

from monitoring.models import PatientDoctorAttachments


class Command(BaseCommand):
    help = "Помечает просроченные запросы на прикрепление."

    def handle(self, *args, **options):
        updated = PatientDoctorAttachments.expire_pending()
        self.stdout.write(self.style.SUCCESS(f"Обновлено запросов: {updated}"))
