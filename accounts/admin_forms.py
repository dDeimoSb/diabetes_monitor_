from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.core.exceptions import ValidationError

from monitoring.models import DiabetesType, Doctors, Patients

from .models import User


class BaseAdminUserFormMixin:
    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        queryset = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise ValidationError("A user with this email already exists.")
        return email


class AdminUserChangeForm(BaseAdminUserFormMixin, UserChangeForm):
    PROFILE_ROLE_CHOICES = (
        ("", "---------"),
        ("patient", "Patient"),
        ("doctor", "Doctor"),
    )

    profile_role = forms.ChoiceField(
        label="Profile type",
        choices=PROFILE_ROLE_CHOICES,
        required=False,
    )
    specialty = forms.CharField(label="Specialty", max_length=150, required=False)
    diabetes_type = forms.ChoiceField(
        label="Diabetes type",
        choices=[("", "---------"), *DiabetesType.choices],
        required=False,
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            return

        if hasattr(self.instance, "doctor_profile"):
            self.initial["profile_role"] = "doctor"
            self.initial["specialty"] = self.instance.doctor_profile.specialty
            return

        if hasattr(self.instance, "patient_profile"):
            self.initial["profile_role"] = "patient"
            self.initial["diabetes_type"] = self.instance.patient_profile.diabetes_type

    def clean(self):
        cleaned_data = super().clean()
        profile_role = cleaned_data.get("profile_role")
        specialty = (cleaned_data.get("specialty") or "").strip()
        diabetes_type = cleaned_data.get("diabetes_type")
        has_doctor_profile = (
            self.instance.pk
            and Doctors.objects.filter(user=self.instance).exists()
        )
        has_patient_profile = (
            self.instance.pk
            and Patients.objects.filter(user=self.instance).exists()
        )

        if has_doctor_profile and has_patient_profile:
            self.add_error(
                "profile_role",
                "У пользователя одновременно есть профиль врача и пациента. "
                "Сначала исправьте конфликт профилей вручную.",
            )
            return cleaned_data

        if profile_role == "doctor" and has_patient_profile:
            self.add_error(
                "profile_role",
                "Нельзя переключить пациента во врача без отдельного переноса "
                "или удаления связанных медицинских данных.",
            )

        if profile_role == "patient" and has_doctor_profile:
            self.add_error(
                "profile_role",
                "Нельзя переключить врача в пациента без отдельного переноса "
                "или удаления связанных данных врача.",
            )

        if profile_role == "doctor" and not specialty:
            self.add_error("specialty", "Specify the doctor's specialty.")

        if profile_role == "patient" and not diabetes_type:
            self.add_error("diabetes_type", "Specify the diabetes type.")

        return cleaned_data


class AdminUserCreationForm(BaseAdminUserFormMixin, UserCreationForm):
    PROFILE_ROLE_CHOICES = (
        ("", "---------"),
        ("patient", "Patient"),
        ("doctor", "Doctor"),
    )

    profile_role = forms.ChoiceField(
        label="Profile type",
        choices=PROFILE_ROLE_CHOICES,
        required=False,
    )
    specialty = forms.CharField(label="Specialty", max_length=150, required=False)
    diabetes_type = forms.ChoiceField(
        label="Diabetes type",
        choices=[("", "---------"), *DiabetesType.choices],
        required=False,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "email",
            "last_name",
            "first_name",
            "middle_name",
            "phone",
            "gender",
            "birth_date",
            "is_staff",
            "is_active",
        )

    def clean(self):
        cleaned_data = super().clean()
        profile_role = cleaned_data.get("profile_role")
        specialty = (cleaned_data.get("specialty") or "").strip()
        diabetes_type = cleaned_data.get("diabetes_type")
        is_staff = cleaned_data.get("is_staff")
        is_superuser = cleaned_data.get("is_superuser")

        if not profile_role and not (is_staff or is_superuser):
            self.add_error(
                "profile_role",
                "Выберите профиль пациента/врача или включите доступ к админке.",
            )

        if profile_role == "doctor" and not specialty:
            self.add_error("specialty", "Specify the doctor's specialty.")

        if profile_role == "patient" and not diabetes_type:
            self.add_error("diabetes_type", "Specify the diabetes type.")

        return cleaned_data
