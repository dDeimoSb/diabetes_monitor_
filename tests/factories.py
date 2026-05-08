from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from monitoring.models import (
    AttachmentRequestStatus,
    DiabetesType,
    Doctors,
    GlucoseEntries,
    MonitoringEntries,
    MonitoringEntryType,
    PatientDoctorAttachments,
    Patients,
)


User = get_user_model()


# Подготовка данных в одном месте
def create_user(email, password="StrongPass123!", **extra_fields):
    defaults = {
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
    }
    defaults.update(extra_fields)
    return User.objects.create_user(email=email, password=password, **defaults)


def create_patient(email="patient@example.com", password="StrongPass123!", **user_fields):
    diabetes_type = user_fields.pop("diabetes_type", DiabetesType.TYPE_1)
    user = create_user(email=email, password=password, **user_fields)
    patient = Patients.objects.create(user=user, diabetes_type=diabetes_type)
    return user, patient


def create_doctor(email="doctor@example.com", password="StrongPass123!", **user_fields):
    specialty = user_fields.pop("specialty", "Endocrinologist")
    user = create_user(email=email, password=password, **user_fields)
    doctor = Doctors.objects.create(user=user, specialty=specialty)
    return user, doctor


def attach_patient_to_doctor(
    patient,
    doctor,
    status=AttachmentRequestStatus.CONFIRMED,
    expires_at=None,
):
    now = timezone.now()
    # Подтвержденная связь врача и пациента
    return PatientDoctorAttachments.objects.create(
        patient=patient,
        doctor=doctor,
        status=status,
        resolved_at=now if status == AttachmentRequestStatus.CONFIRMED else None,
        expires_at=expires_at or now + timedelta(days=7),
    )


def create_glucose_entry(
    patient,
    user=None,
    value="5.50",
    entry_datetime=None,
    comment="",
):
    # Базовая запись и показатель глюкозы
    entry = MonitoringEntries.objects.create(
        patient=patient,
        entered_by_user=user or patient.user,
        entry_type=MonitoringEntryType.GLUCOSE,
        entry_datetime=entry_datetime or timezone.now(),
        comment=comment,
    )
    GlucoseEntries.objects.create(entry=entry, glucose_value_mmol=value)
    return entry
