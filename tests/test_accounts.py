from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from monitoring.models import DiabetesType, Doctors, Patients

from .factories import create_doctor, create_patient, create_user


User = get_user_model()


class RegistrationTests(TestCase):
    def test_registration_creates_active_patient_profile(self):
        response = self.client.post(
            reverse("register"),
            {
                "last_name": "Ivanov",
                "first_name": "Ivan",
                "email": "new-patient@example.com",
                "phone": "+79991234567",
                "diabetes_type": DiabetesType.TYPE_1,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("role_redirect"), fetch_redirect_response=False)
        user = User.objects.get(email="new-patient@example.com")
        self.assertTrue(user.is_active)
        self.assertTrue(Patients.objects.filter(user=user, diabetes_type=DiabetesType.TYPE_1).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_registration_rejects_numeric_password(self):
        response = self.client.post(
            reverse("register"),
            {
                "last_name": "Ivanov",
                "first_name": "Ivan",
                "email": "numeric-password@example.com",
                "diabetes_type": DiabetesType.TYPE_1,
                "password1": "12345678",
                "password2": "12345678",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="numeric-password@example.com").exists())


class AuthenticationTests(TestCase):
    def test_login_accepts_email_case_insensitively(self):
        user, _patient = create_patient(
            email="patient-login@example.com",
            password="StrongPass123!",
        )

        response = self.client.post(
            reverse("login"),
            {
                "email": "PATIENT-LOGIN@EXAMPLE.COM",
                "password": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("role_redirect"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_logout_requires_post(self):
        user = create_user(email="logout@example.com")
        self.client.force_login(user)

        get_response = self.client.get(reverse("logout"))
        self.assertEqual(get_response.status_code, 405)

        post_response = self.client.post(reverse("logout"))
        self.assertRedirects(post_response, reverse("home"), fetch_redirect_response=False)


class RoleRedirectTests(TestCase):
    def test_patient_redirects_to_patient_dashboard(self):
        user, _patient = create_patient(email="patient-redirect@example.com")
        self.client.force_login(user)

        response = self.client.get(reverse("role_redirect"))

        self.assertRedirects(response, reverse("patient_dashboard"), fetch_redirect_response=False)

    def test_doctor_redirects_to_doctor_dashboard(self):
        user, _doctor = create_doctor(email="doctor-redirect@example.com")
        self.client.force_login(user)

        response = self.client.get(reverse("role_redirect"))

        self.assertRedirects(response, reverse("doctor_dashboard"), fetch_redirect_response=False)

    def test_roleless_user_redirects_home(self):
        user = create_user(email="roleless@example.com")
        self.client.force_login(user)

        response = self.client.get(reverse("role_redirect"))

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertFalse(Doctors.objects.filter(user=user).exists())
        self.assertFalse(Patients.objects.filter(user=user).exists())
