from datetime import timedelta
from io import BytesIO
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from monitoring.models import (
    AttachmentRequestStatus,
    CriticalEvents,
    CriticalEventStatus,
    CriticalEventType,
    Doctors,
    GlucoseEntries,
    MonitoringEntries,
    Notifications,
    NotificationType,
    PatientDoctorAttachments,
    Patients,
    Severity,
)


User = get_user_model()


class PublicEducationPagesTests(TestCase):
    def test_doctor_sees_public_template_on_materials_and_test_pages(self):
        user = User.objects.create_user(
            email="doctor@test.local",
            password="StrongPass123!",
            first_name="Doctor",
            last_name="User",
            is_active=True,
        )
        Doctors.objects.create(user=user, specialty="Endocrinologist")
        self.client.force_login(user)

        materials_response = self.client.get(reverse("materials"))
        test_response = self.client.get(reverse("prediabetes_test"))

        self.assertTemplateUsed(materials_response, "base_public.html")
        self.assertContains(materials_response, "layout.js")
        self.assertContains(materials_response, "materials_tables.js")
        self.assertTemplateUsed(test_response, "base_public.html")
        self.assertContains(test_response, "Анкета без авторизации")

    def test_patient_keeps_patient_template_on_materials_and_test_pages(self):
        user = User.objects.create_user(
            email="patient@test.local",
            password="StrongPass123!",
            first_name="Patient",
            last_name="User",
            is_active=True,
        )
        Patients.objects.create(
            user=user,
            diabetes_type="СД 1 типа",
        )
        self.client.force_login(user)

        materials_response = self.client.get(reverse("materials"))
        test_response = self.client.get(reverse("prediabetes_test"))

        self.assertTemplateUsed(materials_response, "base_patient_app.html")
        self.assertContains(materials_response, "layout.js")
        self.assertContains(materials_response, "materials_tables.js")
        self.assertTemplateUsed(test_response, "base_patient_app.html")
        self.assertContains(test_response, "Оценка факторов риска")


class ProfileScriptsTests(TestCase):
    def test_patient_profile_keeps_layout_and_password_scripts(self):
        user = User.objects.create_user(
            email="profile-patient@test.local",
            password="StrongPass123!",
            first_name="Profile",
            last_name="Patient",
            is_active=True,
        )
        Patients.objects.create(
            user=user,
            diabetes_type="СД 1 типа",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("profile"))

        self.assertContains(response, "layout.js")
        self.assertContains(response, "password_toggle.js")


class HomePageCabinetLinkTests(TestCase):
    def test_home_page_topbar_shows_doctor_name_as_link_to_doctor_dashboard(self):
        user = User.objects.create_user(
            email="doctor-home@test.local",
            password="StrongPass123!",
            first_name="Ivan",
            last_name="Ivanov",
            middle_name="Ivanovich",
            is_active=True,
        )
        Doctors.objects.create(user=user, specialty="Endocrinologist")
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertContains(
            response,
            f'<a href="{reverse("doctor_dashboard")}" class="nav-greeting">Ivanov Ivan Ivanovich</a>',
            html=True,
        )

    def test_home_page_topbar_shows_patient_name_as_link_to_patient_dashboard(self):
        user = User.objects.create_user(
            email="patient-home@test.local",
            password="StrongPass123!",
            first_name="Petr",
            last_name="Petrov",
            middle_name="Petrovich",
            is_active=True,
        )
        Patients.objects.create(
            user=user,
            diabetes_type="СД 1 типа",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertContains(
            response,
            f'<a href="{reverse("patient_dashboard")}" class="nav-greeting">Petrov Petr Petrovich</a>',
            html=True,
        )


class CabinetPagesAccessTests(TestCase):
    def test_roleless_user_cannot_open_export_profile_or_notifications(self):
        user = User.objects.create_user(
            email="norole@test.local",
            password="StrongPass123!",
            first_name="No",
            last_name="Role",
            is_active=True,
        )
        self.client.force_login(user)

        for url_name in ("export", "profile", "notifications"):
            response = self.client.get(reverse(url_name), follow=True)
            self.assertRedirects(response, reverse("home"))


class ExportPageTests(TestCase):
    def setUp(self):
        self.doctor_user = User.objects.create_user(
            email="export-doctor@test.local",
            password="StrongPass123!",
            first_name="Export",
            last_name="Doctor",
            is_active=True,
        )
        self.doctor = Doctors.objects.create(
            user=self.doctor_user,
            specialty="Endocrinologist",
        )
        self.patient_user = User.objects.create_user(
            email="export-patient@test.local",
            password="StrongPass123!",
            first_name="Patient",
            last_name="Exportable",
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
        self.entry = MonitoringEntries.objects.create(
            patient=self.patient,
            entered_by_user=self.patient_user,
            entry_type="Глюкоза",
            entry_datetime=timezone.now(),
            comment='=HYPERLINK("https://example.com","open")',
        )
        GlucoseEntries.objects.create(
            entry=self.entry,
            glucose_value_mmol="5.50",
        )

    def test_doctor_export_uses_patient_search_instead_of_select(self):
        self.client.force_login(self.doctor_user)

        response = self.client.get(
            reverse("export"),
            {"patient_query": "Exportable"},
        )

        self.assertContains(response, "Результаты поиска")
        self.assertContains(response, self.patient.user.display_name)
        self.assertContains(response, f'value="{self.patient.patient_id}"')
        self.assertNotContains(response, 'name="patient"')

    def test_doctor_can_export_for_selected_patient_id(self):
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("export"),
            {
                "patient_query": "Exportable",
                "patient_id": self.patient.patient_id,
                "start_date": timezone.localdate() - timedelta(days=30),
                "end_date": timezone.localdate(),
                "export_format": "csv",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])

    def test_csv_export_escapes_formula_cells(self):
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("export"),
            {
                "patient_query": "Exportable",
                "patient_id": self.patient.patient_id,
                "start_date": timezone.localdate() - timedelta(days=30),
                "end_date": timezone.localdate(),
                "export_format": "csv",
            },
        )

        self.assertIn("'=HYPERLINK", response.content.decode("utf-8-sig"))

    def test_excel_export_returns_real_xlsx(self):
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("export"),
            {
                "patient_query": "Exportable",
                "patient_id": self.patient.patient_id,
                "start_date": timezone.localdate() - timedelta(days=30),
                "end_date": timezone.localdate(),
                "export_format": "excel",
            },
        )

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn(".xlsx", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"PK"))

        with ZipFile(BytesIO(response.content)) as archive:
            worksheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("'=HYPERLINK", worksheet)


class SafeRedirectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="redirect-patient@test.local",
            password="StrongPass123!",
            first_name="Redirect",
            last_name="Patient",
            is_active=True,
        )
        self.patient = Patients.objects.create(
            user=self.user,
            diabetes_type="СД 1 типа",
        )
        entry = MonitoringEntries.objects.create(
            patient=self.patient,
            entered_by_user=self.user,
            entry_type="Глюкоза",
            entry_datetime=timezone.now(),
        )
        GlucoseEntries.objects.create(
            entry=entry,
            glucose_value_mmol="2.70",
        )
        event = CriticalEvents.objects.create(
            entry=entry,
            event_type=CriticalEventType.LOW_GLUCOSE,
            severity=Severity.HIGH,
            message="Низкий уровень глюкозы.",
            status=CriticalEventStatus.NEW,
        )
        self.notification = Notifications.objects.create(
            recipient_user=self.user,
            critical_event=event,
            notification_type=NotificationType.WARNING,
            title="Критический показатель",
            message=event.message,
        )

    def test_mark_notification_read_rejects_external_next_url(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("mark_notification_read", args=[self.notification.notification_id]),
            {"next": "https://evil.example/steal"},
        )

        self.assertRedirects(response, reverse("notifications"), fetch_redirect_response=False)


class InteractiveScriptsRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="scripts-patient@test.local",
            password="StrongPass123!",
            first_name="Scripts",
            last_name="Patient",
            is_active=True,
        )
        Patients.objects.create(
            user=self.user,
            diabetes_type="СД 1 типа",
        )

    def _content(self, url_name):
        self.client.force_login(self.user)
        return self.client.get(reverse(url_name)).content.decode("utf-8")

    def test_profile_scripts_are_rendered_once(self):
        content = self._content("profile")

        self.assertEqual(content.count("js/layout.js"), 1)
        self.assertEqual(content.count("js/password_toggle.js"), 1)

    def test_materials_scripts_are_rendered_once(self):
        content = self._content("materials")

        self.assertEqual(content.count("js/layout.js"), 1)
        self.assertEqual(content.count("js/materials_tables.js"), 1)

    def test_patient_entry_and_charts_scripts_are_rendered_once(self):
        add_entry_content = self._content("patient_add_entry")
        charts_content = self._content("patient_charts")

        self.assertEqual(add_entry_content.count("js/layout.js"), 1)
        self.assertEqual(add_entry_content.count("js/monitoring_entry_form.js"), 1)
        self.assertEqual(charts_content.count("js/layout.js"), 1)
        self.assertEqual(charts_content.count("js/chart.umd.min.js"), 1)
        self.assertEqual(charts_content.count("js/monitoring_charts.js"), 1)
