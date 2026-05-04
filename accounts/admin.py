from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db import transaction

from monitoring.models import Doctors, Patients

from .admin_forms import AdminUserChangeForm, AdminUserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    form = AdminUserChangeForm
    add_form = AdminUserCreationForm
    ordering = ("email",)
    list_display = (
        "email",
        "last_name",
        "first_name",
        "profile_role_label",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "gender")
    search_fields = ("email", "last_name", "first_name", "middle_name", "phone")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("last_name", "first_name", "middle_name", "phone", "gender", "birth_date")}),
        ("Profile", {"fields": ("profile_role", "specialty", "diabetes_type")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    readonly_fields = ("last_login", "date_joined")
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "last_name",
                    "first_name",
                    "middle_name",
                    "phone",
                    "gender",
                    "birth_date",
                    "profile_role",
                    "specialty",
                    "diabetes_type",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )

    @admin.display(description="Role")
    def profile_role_label(self, obj):
        return obj.profile_role or "-"

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            super().save_model(request, obj, form, change)

            profile_role = form.cleaned_data.get("profile_role")
            if profile_role == "doctor":
                doctor_profile, created = Doctors.objects.get_or_create(
                    user=obj,
                    defaults={"specialty": form.cleaned_data["specialty"].strip()},
                )
                if not created:
                    specialty = form.cleaned_data["specialty"].strip()
                    if doctor_profile.specialty != specialty:
                        doctor_profile.specialty = specialty
                        doctor_profile.save(update_fields=["specialty", "updated_at"])
                return

            if profile_role == "patient":
                patient_profile, created = Patients.objects.get_or_create(
                    user=obj,
                    defaults={"diabetes_type": form.cleaned_data["diabetes_type"]},
                )
                if not created:
                    diabetes_type = form.cleaned_data["diabetes_type"]
                    if patient_profile.diabetes_type != diabetes_type:
                        patient_profile.diabetes_type = diabetes_type
                        patient_profile.save(update_fields=["diabetes_type", "updated_at"])

    class Media:
        js = ("admin/js/user_profile_role.js",)
