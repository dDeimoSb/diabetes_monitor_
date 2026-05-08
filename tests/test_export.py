from datetime import timedelta
from io import BytesIO
from zipfile import ZipFile

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .factories import (
    attach_patient_to_doctor,
    create_doctor,
    create_glucose_entry,
    create_patient,
)


class DataExportTests(TestCase):
    def setUp(self):
        self.doctor_user, self.doctor = create_doctor(email="export-doctor@example.com")
        self.patient_user, self.patient = create_patient(
            email="export-patient@example.com",
            first_name="Export",
            last_name="Patient",
        )
        attach_patient_to_doctor(self.patient, self.doctor)
        self.entry = create_glucose_entry(
            self.patient,
            value="5.50",
            # Опасная формула в комментарии
            comment='=HYPERLINK("https://example.com","open")',
        )

    def _date_range(self):
        return {
            "start_date": timezone.localdate() - timedelta(days=1),
            "end_date": timezone.localdate() + timedelta(days=1),
        }

    def test_patient_can_export_own_entries_as_csv(self):
        self.client.force_login(self.patient_user)

        response = self.client.post(
            reverse("export"),
            {**self._date_range(), "export_format": "csv"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("'=HYPERLINK", response.content.decode("utf-8-sig"))

    def test_doctor_can_export_confirmed_patient_as_csv(self):
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("export"),
            {
                **self._date_range(),
                "export_format": "csv",
                "patient_id": self.patient.patient_id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(self.patient.user.display_name, response.content.decode("utf-8-sig"))

    def test_doctor_cannot_export_unattached_patient(self):
        _other_user, other_patient = create_patient(email="unattached@example.com")
        create_glucose_entry(other_patient, value="6.20")
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("export"),
            {
                **self._date_range(),
                "export_format": "csv",
                "patient_id": other_patient.patient_id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.has_header("Content-Disposition"))
        self.assertIn("patient_id", response.context["form"].errors)

    def test_excel_export_returns_xlsx_archive(self):
        self.client.force_login(self.patient_user)

        response = self.client.post(
            reverse("export"),
            {**self._date_range(), "export_format": "excel"},
        )

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertTrue(response.content.startswith(b"PK"))

        with ZipFile(BytesIO(response.content)) as archive:
            worksheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("'=HYPERLINK", worksheet)
