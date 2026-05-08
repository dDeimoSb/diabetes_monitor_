from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from monitoring.models import (
    CriticalEvents,
    CriticalEventType,
    GlucoseEntries,
    MonitoringEntries,
    MonitoringEntryType,
    Notifications,
)
from patient.forms import MonitoringEntryForm

from .factories import (
    attach_patient_to_doctor,
    create_doctor,
    create_patient,
)


def entry_datetime_value():
    # Формат поля datetime-local
    return timezone.localtime(timezone.now()).strftime("%Y-%m-%dT%H:%M")


class MonitoringEntryFormTests(TestCase):
    def test_glucose_entry_requires_glucose_value(self):
        form = MonitoringEntryForm(
            data={
                "entry_type": MonitoringEntryType.GLUCOSE,
                "entry_datetime": entry_datetime_value(),
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("glucose_value_mmol", form.errors)

    def test_valid_glucose_entry_creates_base_and_detail_records(self):
        user, patient = create_patient(email="form-patient@example.com")
        form = MonitoringEntryForm(
            data={
                "entry_type": MonitoringEntryType.GLUCOSE,
                "entry_datetime": entry_datetime_value(),
                "glucose_value_mmol": "5.80",
                "comment": "after breakfast",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        entry = form.save(patient=patient, user=user)

        self.assertEqual(entry.entry_type, MonitoringEntryType.GLUCOSE)
        self.assertEqual(entry.comment, "after breakfast")
        self.assertEqual(entry.glucose_entry.glucose_value_mmol, Decimal("5.80"))


class PatientEntryViewsTests(TestCase):
    def setUp(self):
        self.patient_user, self.patient = create_patient(email="entry-patient@example.com")

    def test_patient_can_add_glucose_entry(self):
        self.client.force_login(self.patient_user)

        response = self.client.post(
            reverse("patient_add_entry"),
            {
                "entry_type": MonitoringEntryType.GLUCOSE,
                "entry_datetime": entry_datetime_value(),
                "glucose_value_mmol": "6.10",
            },
        )

        entry = MonitoringEntries.objects.get(patient=self.patient)
        self.assertRedirects(
            response,
            f"{reverse('patient_history')}?entry_id={entry.entry_id}",
            fetch_redirect_response=False,
        )
        self.assertTrue(GlucoseEntries.objects.filter(entry=entry, glucose_value_mmol="6.10").exists())

    def test_doctor_cannot_add_patient_entry(self):
        doctor_user, _doctor = create_doctor(email="entry-doctor@example.com")
        self.client.force_login(doctor_user)

        response = self.client.get(reverse("patient_add_entry"))

        self.assertRedirects(response, reverse("role_redirect"), fetch_redirect_response=False)


class CriticalEventLifecycleTests(TestCase):
    def setUp(self):
        self.doctor_user, self.doctor = create_doctor(email="critical-doctor@example.com")
        self.patient_user, self.patient = create_patient(email="critical-patient@example.com")
        # Получатели уведомлений
        attach_patient_to_doctor(self.patient, self.doctor)
        self.client.force_login(self.patient_user)

    def _post_glucose(self, value):
        response = self.client.post(
            reverse("patient_add_entry"),
            {
                "entry_type": MonitoringEntryType.GLUCOSE,
                "entry_datetime": entry_datetime_value(),
                "glucose_value_mmol": value,
            },
        )
        self.assertEqual(response.status_code, 302)
        return MonitoringEntries.objects.get(patient=self.patient)

    def test_low_glucose_entry_creates_event_and_notifications(self):
        entry = self._post_glucose("2.70")

        event = CriticalEvents.objects.get(entry=entry)
        self.assertEqual(event.event_type, CriticalEventType.LOW_GLUCOSE)
        self.assertEqual(
            set(Notifications.objects.values_list("recipient_user", flat=True)),
            {self.patient_user.pk, self.doctor_user.pk},
        )

    def test_editing_critical_entry_to_normal_removes_event_and_notifications(self):
        entry = self._post_glucose("2.70")
        self.assertEqual(CriticalEvents.objects.filter(entry=entry).count(), 1)

        # Нормализация показателя
        response = self.client.post(
            reverse("patient_edit_entry", args=[entry.entry_id]),
            {
                "entry_type": MonitoringEntryType.GLUCOSE,
                "entry_datetime": entry_datetime_value(),
                "glucose_value_mmol": "5.50",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('patient_history')}?entry_id={entry.entry_id}",
            fetch_redirect_response=False,
        )
        self.assertFalse(CriticalEvents.objects.filter(entry=entry).exists())
        self.assertFalse(Notifications.objects.exists())
