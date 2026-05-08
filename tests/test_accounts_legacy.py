from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.admin_forms import AdminUserCreationForm
from monitoring.models import Doctors, Patients


User = get_user_model()


class PasswordToggleRenderTests(TestCase):
    def test_login_page_renders_password_toggle(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, 'data-password-toggle', count=1)
        self.assertContains(response, "layout.js")
        self.assertContains(response, "password_toggle.js")

    def test_register_page_renders_password_toggles_for_both_password_fields(self):
        response = self.client.get(reverse("register"))

        self.assertContains(response, 'data-password-toggle', count=2)
        self.assertContains(response, "layout.js")
        self.assertContains(response, "password_toggle.js")


class AuthenticationSecurityTests(TestCase):
    def test_registration_rejects_numeric_password(self):
        response = self.client.post(
            reverse("register"),
            {
                "last_name": "Иванов",
                "first_name": "Иван",
                "email": "numeric-password@test.local",
                "phone": "+79991234567",
                "diabetes_type": "СД 1 типа",
                "password1": "12345678",
                "password2": "12345678",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="numeric-password@test.local").exists())

    def test_logout_requires_post(self):
        user = User.objects.create_user(
            email="logout@test.local",
            password="StrongPass123!",
            is_active=True,
        )
        self.client.force_login(user)

        get_response = self.client.get(reverse("logout"))
        self.assertEqual(get_response.status_code, 405)

        post_response = self.client.post(reverse("logout"))
        self.assertEqual(post_response.status_code, 302)


class RoleRedirectTests(TestCase):
    def test_doctor_redirects_to_doctor_dashboard(self):
        user = User.objects.create_user(
            email="doctor-redirect@test.local",
            password="StrongPass123!",
            is_active=True,
        )
        Doctors.objects.create(user=user, specialty="Эндокринолог")
        self.client.force_login(user)

        response = self.client.get(reverse("role_redirect"))

        self.assertRedirects(response, reverse("doctor_dashboard"), fetch_redirect_response=False)

    def test_patient_redirects_to_patient_dashboard(self):
        user = User.objects.create_user(
            email="patient-redirect@test.local",
            password="StrongPass123!",
            is_active=True,
        )
        Patients.objects.create(user=user, diabetes_type="СД 1 типа")
        self.client.force_login(user)

        response = self.client.get(reverse("role_redirect"))

        self.assertRedirects(response, reverse("patient_dashboard"), fetch_redirect_response=False)

    def test_roleless_user_redirects_home(self):
        user = User.objects.create_user(
            email="roleless-redirect@test.local",
            password="StrongPass123!",
            is_active=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("role_redirect"))

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)


class AdminUserCreationFormTests(TestCase):
    def _base_data(self, **overrides):
        data = {
            "email": "admin-created@test.local",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
            "last_name": "Admin",
            "first_name": "Created",
            "middle_name": "",
            "phone": "",
            "gender": "",
            "birth_date": "",
            "profile_role": "",
            "specialty": "",
            "diabetes_type": "",
            "is_staff": "",
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_staff_user_can_be_created_without_profile_role(self):
        form = AdminUserCreationForm(
            data=self._base_data(
                email="staff-admin@test.local",
                is_staff="on",
            )
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_regular_user_requires_profile_role(self):
        form = AdminUserCreationForm(
            data=self._base_data(email="regular-without-role@test.local")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("profile_role", form.errors)
