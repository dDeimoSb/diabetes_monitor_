from datetime import timedelta

from django import forms
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from monitoring.models import AttachmentRequestStatus, PatientDoctorAttachments, Patients


INPUT_ATTRS = {"class": "input-text"}
ATTACHMENT_REQUEST_LIFETIME = timedelta(days=7)


class PatientAttachmentSearchForm(forms.Form):
    patient_query = forms.CharField(
        label="Email или ФИО пациента",
        max_length=255,
        widget=forms.TextInput(
            attrs={
                **INPUT_ATTRS,
                "placeholder": "patient@example.com или Иванов Иван Иванович",
            }
        ),
    )

    def clean_patient_query(self):
        return (self.cleaned_data["patient_query"] or "").strip()

    def get_patient_queryset(self):
        query = self.cleaned_data["patient_query"]
        queryset = Patients.objects.select_related("user")

        if "@" in query:
            queryset = queryset.filter(user__email__icontains=query)
        else:
            for term in [item for item in query.split() if item]:
                queryset = queryset.filter(
                    Q(user__last_name__icontains=term)
                    | Q(user__first_name__icontains=term)
                    | Q(user__middle_name__icontains=term)
                )

        queryset = queryset.order_by(
            "user__last_name",
            "user__first_name",
            "patient_id",
        )
        return queryset

    def get_results(self, doctor_profile, patients=None):
        if patients is None:
            patients = self.get_patient_queryset()[:50]
        patients = list(patients)

        active_attachments = {}
        for attachment in PatientDoctorAttachments.objects.select_related("patient").filter(
            doctor=doctor_profile,
            patient__in=patients,
            status__in=(
                AttachmentRequestStatus.CONFIRMED,
                AttachmentRequestStatus.PENDING,
            ),
        ).order_by("-created_at", "-attachment_id"):
            current = active_attachments.get(attachment.patient_id)
            if current is None or attachment.status == AttachmentRequestStatus.CONFIRMED:
                active_attachments[attachment.patient_id] = attachment

        results = []
        for patient in patients:
            active_attachment = active_attachments.get(patient.patient_id)
            results.append(
                {
                    "patient": patient,
                    "attachment": active_attachment,
                    "can_request": active_attachment is None,
                }
            )
        return results


class CreateAttachmentRequestForm(forms.Form):
    patient_id = forms.IntegerField(widget=forms.HiddenInput())
    search_query = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, doctor_profile, **kwargs):
        self.doctor_profile = doctor_profile
        self.patient = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        patient_id = cleaned_data.get("patient_id")
        if patient_id in (None, ""):
            return cleaned_data

        patient = Patients.objects.select_related("user").filter(patient_id=patient_id).first()
        if patient is None:
            self.add_error("patient_id", "Выберите пациента из списка найденных.")
            return cleaned_data

        if PatientDoctorAttachments.objects.filter(
            patient=patient,
            doctor=self.doctor_profile,
            status=AttachmentRequestStatus.CONFIRMED,
        ).exists():
            self.add_error(
                "patient_id",
                "Этот пациент уже подтвержденно прикреплен к вам.",
            )
            return cleaned_data

        if PatientDoctorAttachments.objects.filter(
            patient=patient,
            doctor=self.doctor_profile,
            status=AttachmentRequestStatus.PENDING,
        ).exists():
            self.add_error(
                "patient_id",
                "Для этого пациента уже есть активный запрос на прикрепление.",
            )
            return cleaned_data

        self.patient = patient
        return cleaned_data

    def save(self):
        if self.patient is None:
            raise ValueError("CreateAttachmentRequestForm.save() called before validation.")

        now = timezone.now()
        with transaction.atomic():
            return PatientDoctorAttachments.objects.create(
                patient=self.patient,
                doctor=self.doctor_profile,
                status=AttachmentRequestStatus.PENDING,
                created_at=now,
                expires_at=now + ATTACHMENT_REQUEST_LIFETIME,
            )
