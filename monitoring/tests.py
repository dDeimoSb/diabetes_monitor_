from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from monitoring.models import (
    AttachmentRequestStatus,
    CriticalEventType,
    CriticalEvents,
    Doctors,
    MonitoringEntries,
    Notifications,
    PatientDoctorAttachments,
    Patients,
)


User = get_user_model()


class PatientDoctorAttachmentsFlowTests(TestCase):
    def setUp(self):
        self.doctor_user = User.objects.create_user(
            email="doctor@test.local",
            password="StrongPass123!",
            first_name="Ivan",
            last_name="Ivanov",
            is_active=True,
        )
        self.doctor = Doctors.objects.create(
            user=self.doctor_user,
            specialty="Endocrinologist",
        )

        self.patient_user = User.objects.create_user(
            email="patient@test.local",
            password="StrongPass123!",
            first_name="Petr",
            last_name="Petrov",
            is_active=True,
        )
        self.patient = Patients.objects.create(
            user=self.patient_user,
            diabetes_type="СД 1 типа",
        )

    def test_doctor_searches_and_creates_attachment_request(self):
        self.client.force_login(self.doctor_user)

        search_response = self.client.get(
            reverse("doctor_attach_patient"),
            {"patient_query": self.patient_user.email},
        )

        self.assertContains(search_response, self.patient_user.email)

        create_response = self.client.post(
            reverse("doctor_attach_patient"),
            {
                "action": "create_request",
                "search_query": self.patient_user.email,
                "patient_id": self.patient.patient_id,
            },
            follow=True,
        )

        attachment = PatientDoctorAttachments.objects.get(
            patient=self.patient,
            doctor=self.doctor,
        )
        self.assertEqual(attachment.status, AttachmentRequestStatus.PENDING)
        self.assertGreater(attachment.expires_at, attachment.created_at)
        self.assertContains(create_response, "Запрос на прикрепление пациента")

    def test_attach_patient_search_results_are_paginated(self):
        last_patient = None
        for index in range(1, 52):
            patient_user = User.objects.create(
                email=f"attach-search-{index:03d}@test.local",
                first_name=f"First{index:03d}",
                last_name=f"AttachSearchLast{index:03d}",
                is_active=True,
            )
            patient = Patients.objects.create(
                user=patient_user,
                diabetes_type="СД 1 типа",
            )
            last_patient = patient

        self.client.force_login(self.doctor_user)

        first_page_response = self.client.get(
            reverse("doctor_attach_patient"),
            {"patient_query": "AttachSearchLast"},
        )

        self.assertContains(first_page_response, "Показано 1-50 из 51")
        self.assertContains(first_page_response, "?patient_query=AttachSearchLast&amp;page=2")
        self.assertEqual(len(first_page_response.context["search_results"]), 50)
        self.assertNotIn(
            last_patient,
            [item["patient"] for item in first_page_response.context["search_results"]],
        )

        second_page_response = self.client.get(
            reverse("doctor_attach_patient"),
            {"patient_query": "AttachSearchLast", "page": 2},
        )

        self.assertContains(second_page_response, "Показано 51-51 из 51")
        self.assertContains(second_page_response, "?patient_query=AttachSearchLast&amp;page=1")
        self.assertEqual(len(second_page_response.context["search_results"]), 1)
        self.assertIn(
            last_patient,
            [item["patient"] for item in second_page_response.context["search_results"]],
        )

    def test_patient_can_confirm_attachment_request_from_attachments_page(self):
        attachment = PatientDoctorAttachments.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            status=AttachmentRequestStatus.PENDING,
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.client.force_login(self.patient_user)

        self.client.post(
            reverse("patient_attachments"),
            {
                "attachment_id": attachment.attachment_id,
                "action": "confirm",
            },
            follow=True,
        )

        attachment.refresh_from_db()
        self.assertEqual(attachment.status, AttachmentRequestStatus.CONFIRMED)
        self.assertIsNotNone(attachment.resolved_at)

    def test_confirmed_attachment_makes_patient_visible_in_doctor_dashboard(self):
        PatientDoctorAttachments.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            status=AttachmentRequestStatus.CONFIRMED,
            resolved_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.client.force_login(self.doctor_user)

        response = self.client.get(reverse("doctor_dashboard"))

        self.assertContains(response, self.patient.user.display_name)

    def test_doctor_dashboard_paginates_confirmed_patients(self):
        now = timezone.now()
        last_patient = None
        for index in range(1, 52):
            patient_user = User.objects.create_user(
                email=f"patient-{index:03d}@test.local",
                password="StrongPass123!",
                first_name=f"First{index:03d}",
                last_name=f"Last{index:03d}",
                is_active=True,
            )
            patient = Patients.objects.create(
                user=patient_user,
                diabetes_type="СД 1 типа",
            )
            PatientDoctorAttachments.objects.create(
                patient=patient,
                doctor=self.doctor,
                status=AttachmentRequestStatus.CONFIRMED,
                resolved_at=now,
                expires_at=now + timedelta(days=7),
            )
            last_patient = patient

        self.client.force_login(self.doctor_user)

        first_page_response = self.client.get(reverse("doctor_dashboard"))

        self.assertContains(first_page_response, "Показано 1-50 из 51")
        self.assertContains(first_page_response, "?page=2")
        self.assertEqual(len(first_page_response.context["patients"]), 50)
        self.assertNotIn(last_patient, first_page_response.context["patients"])

        searched_response = self.client.get(reverse("doctor_dashboard"), {"q": "Last"})

        self.assertContains(searched_response, "Показано 1-50 из 51")
        self.assertContains(searched_response, "?q=Last&amp;page=2")

        second_page_response = self.client.get(reverse("doctor_dashboard"), {"page": 2})

        self.assertContains(second_page_response, "Показано 51-51 из 51")
        self.assertEqual(len(second_page_response.context["patients"]), 1)
        self.assertIn(last_patient, second_page_response.context["patients"])

    def test_expired_request_cannot_be_confirmed_by_button(self):
        attachment = PatientDoctorAttachments.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            status=AttachmentRequestStatus.PENDING,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.client.force_login(self.patient_user)

        self.client.post(
            reverse("patient_attachments"),
            {
                "attachment_id": attachment.attachment_id,
                "action": "confirm",
            },
            follow=True,
        )

        attachment.refresh_from_db()
        self.assertEqual(attachment.status, AttachmentRequestStatus.EXPIRED)


class CriticalEventsLifecycleTests(TestCase):
    def setUp(self):
        self.doctor_user = User.objects.create_user(
            email="critical-doctor@test.local",
            password="StrongPass123!",
            first_name="Doctor",
            last_name="Critical",
            is_active=True,
        )
        self.doctor = Doctors.objects.create(
            user=self.doctor_user,
            specialty="Endocrinologist",
        )

        self.patient_user = User.objects.create_user(
            email="critical-patient@test.local",
            password="StrongPass123!",
            first_name="Patient",
            last_name="Critical",
            is_active=True,
        )
        self.patient = Patients.objects.create(
            user=self.patient_user,
            diabetes_type="СД 1 типа",
        )
        PatientDoctorAttachments.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            status=AttachmentRequestStatus.CONFIRMED,
            resolved_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=7),
        )

    def _entry_datetime_value(self):
        return timezone.localtime(timezone.now()).strftime("%Y-%m-%dT%H:%M")

    def _create_glucose_entry(self, value):
        self.client.force_login(self.patient_user)
        response = self.client.post(
            reverse("patient_add_entry"),
            {
                "entry_type": "Глюкоза",
                "entry_datetime": self._entry_datetime_value(),
                "glucose_value_mmol": value,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        return MonitoringEntries.objects.get(patient=self.patient)

    def test_low_glucose_entry_creates_event_and_notifications(self):
        entry = self._create_glucose_entry("2.70")

        event = CriticalEvents.objects.get(entry=entry)
        self.assertEqual(event.event_type, CriticalEventType.LOW_GLUCOSE)
        self.assertEqual(
            set(
                Notifications.objects.filter(critical_event=event).values_list(
                    "recipient_user",
                    flat=True,
                )
            ),
            {self.patient_user.pk, self.doctor_user.pk},
        )

    def test_editing_critical_entry_to_normal_removes_event_notifications(self):
        entry = self._create_glucose_entry("2.70")
        self.assertEqual(CriticalEvents.objects.filter(entry=entry).count(), 1)

        response = self.client.post(
            reverse("patient_edit_entry", args=[entry.entry_id]),
            {
                "entry_type": "Глюкоза",
                "entry_datetime": self._entry_datetime_value(),
                "glucose_value_mmol": "5.50",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CriticalEvents.objects.filter(entry=entry).exists())
        self.assertFalse(Notifications.objects.exists())

    def test_deleting_entry_removes_related_event_notifications(self):
        entry = self._create_glucose_entry("2.70")
        self.assertEqual(Notifications.objects.count(), 2)

        response = self.client.post(
            reverse("patient_delete_entry", args=[entry.entry_id]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(MonitoringEntries.objects.filter(entry_id=entry.entry_id).exists())
        self.assertFalse(CriticalEvents.objects.exists())
        self.assertFalse(Notifications.objects.exists())
