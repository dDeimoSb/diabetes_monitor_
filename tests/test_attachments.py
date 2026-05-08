from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from monitoring.models import AttachmentRequestStatus, PatientDoctorAttachments

from .factories import (
    attach_patient_to_doctor,
    create_doctor,
    create_patient,
)


class PatientDoctorAttachmentTests(TestCase):
    def setUp(self):
        self.doctor_user, self.doctor = create_doctor(email="doctor@example.com")
        self.patient_user, self.patient = create_patient(email="patient@example.com")

    def test_doctor_can_search_patient_and_create_attachment_request(self):
        self.client.force_login(self.doctor_user)

        search_response = self.client.get(
            reverse("doctor_attach_patient"),
            {"patient_query": self.patient_user.email},
        )
        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(search_response.context["search_results"][0]["patient"], self.patient)
        self.assertTrue(search_response.context["search_results"][0]["can_request"])

        create_response = self.client.post(
            reverse("doctor_attach_patient"),
            {
                "action": "create_request",
                "search_query": self.patient_user.email,
                "patient_id": self.patient.patient_id,
            },
        )

        self.assertRedirects(
            create_response,
            reverse("doctor_attach_patient"),
            fetch_redirect_response=False,
        )
        attachment = PatientDoctorAttachments.objects.get(patient=self.patient, doctor=self.doctor)
        self.assertEqual(attachment.status, AttachmentRequestStatus.PENDING)
        self.assertGreater(attachment.expires_at, attachment.created_at)

    def test_patient_can_confirm_pending_attachment_request(self):
        attachment = attach_patient_to_doctor(
            self.patient,
            self.doctor,
            status=AttachmentRequestStatus.PENDING,
        )
        self.client.force_login(self.patient_user)

        response = self.client.post(
            reverse("patient_attachments"),
            {
                "attachment_id": attachment.attachment_id,
                "action": "confirm",
            },
        )

        self.assertRedirects(response, reverse("patient_attachments"), fetch_redirect_response=False)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, AttachmentRequestStatus.CONFIRMED)
        self.assertIsNotNone(attachment.resolved_at)

    def test_expired_attachment_request_cannot_be_confirmed(self):
        attachment = attach_patient_to_doctor(
            self.patient,
            self.doctor,
            status=AttachmentRequestStatus.PENDING,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.client.force_login(self.patient_user)

        response = self.client.post(
            reverse("patient_attachments"),
            {
                "attachment_id": attachment.attachment_id,
                "action": "confirm",
            },
        )

        self.assertEqual(response.status_code, 200)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, AttachmentRequestStatus.EXPIRED)

    def test_confirmed_patient_is_visible_on_doctor_dashboard(self):
        attach_patient_to_doctor(self.patient, self.doctor)
        self.client.force_login(self.doctor_user)

        response = self.client.get(reverse("doctor_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.patient, response.context["patients"])

    def test_unconfirmed_patient_is_not_visible_on_doctor_dashboard(self):
        attach_patient_to_doctor(
            self.patient,
            self.doctor,
            status=AttachmentRequestStatus.PENDING,
        )
        self.client.force_login(self.doctor_user)

        response = self.client.get(reverse("doctor_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.patient, response.context["patients"])
