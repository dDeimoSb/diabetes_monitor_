from django.contrib import admin

from .models import (
    ActivityEntries,
    AttachmentRequestStatus,
    CriticalEvents,
    Doctors,
    GlucoseEntries,
    MealEntries,
    MonitoringEntries,
    Notifications,
    PatientDoctorAttachments,
    Patients,
    TherapyEntries,
    VitalSignsEntries,
    WellbeingEntries,
)


class SingleEntryInlineMixin:
    extra = 0
    max_num = 1
    autocomplete_fields = ("entry",)


class GlucoseEntriesInline(SingleEntryInlineMixin, admin.StackedInline):
    model = GlucoseEntries


class TherapyEntriesInline(SingleEntryInlineMixin, admin.StackedInline):
    model = TherapyEntries


class MealEntriesInline(SingleEntryInlineMixin, admin.StackedInline):
    model = MealEntries


class ActivityEntriesInline(SingleEntryInlineMixin, admin.StackedInline):
    model = ActivityEntries


class WellbeingEntriesInline(SingleEntryInlineMixin, admin.StackedInline):
    model = WellbeingEntries


class VitalSignsEntriesInline(SingleEntryInlineMixin, admin.StackedInline):
    model = VitalSignsEntries


@admin.register(Doctors)
class DoctorsAdmin(admin.ModelAdmin):
    list_display = ("doctor_id", "user", "user_email", "specialty", "updated_at")
    list_filter = ("specialty", "updated_at")
    search_fields = (
        "doctor_id",
        "specialty",
        "user__email",
        "user__last_name",
        "user__first_name",
        "user__middle_name",
    )
    autocomplete_fields = ("user",)
    ordering = ("doctor_id",)

    @admin.display(ordering="user__email", description="Email")
    def user_email(self, obj):
        return obj.user.email


@admin.register(Patients)
class PatientsAdmin(admin.ModelAdmin):
    list_display = (
        "patient_id",
        "user",
        "user_email",
        "diabetes_type",
        "confirmed_doctors_count",
        "updated_at",
    )
    list_filter = ("diabetes_type", "updated_at")
    search_fields = (
        "patient_id",
        "user__email",
        "user__last_name",
        "user__first_name",
        "user__middle_name",
    )
    autocomplete_fields = ("user",)
    ordering = ("patient_id",)

    @admin.display(ordering="user__email", description="Email")
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description="Подтвержденные врачи")
    def confirmed_doctors_count(self, obj):
        return obj.doctor_attachments.filter(status=AttachmentRequestStatus.CONFIRMED).count()


@admin.register(PatientDoctorAttachments)
class PatientDoctorAttachmentsAdmin(admin.ModelAdmin):
    list_display = (
        "attachment_id",
        "patient",
        "patient_email",
        "doctor",
        "doctor_email",
        "status",
        "created_at",
        "resolved_at",
        "expires_at",
    )
    list_filter = ("status", "created_at", "resolved_at", "expires_at")
    search_fields = (
        "attachment_id",
        "patient__user__email",
        "patient__user__last_name",
        "patient__user__first_name",
        "doctor__user__email",
        "doctor__user__last_name",
        "doctor__user__first_name",
    )
    autocomplete_fields = ("patient", "doctor")
    ordering = ("-created_at", "-attachment_id")

    @admin.display(ordering="patient__user__email", description="Email пациента")
    def patient_email(self, obj):
        return obj.patient.user.email

    @admin.display(ordering="doctor__user__email", description="Email врача")
    def doctor_email(self, obj):
        return obj.doctor.user.email


@admin.register(MonitoringEntries)
class MonitoringEntriesAdmin(admin.ModelAdmin):
    list_display = (
        "entry_id",
        "entry_type",
        "patient",
        "patient_email",
        "entered_by_user",
        "entry_datetime",
        "created_at",
    )
    list_filter = ("entry_type", "entry_datetime", "created_at", "updated_at")
    search_fields = (
        "entry_id",
        "comment",
        "patient__user__email",
        "patient__user__last_name",
        "patient__user__first_name",
        "entered_by_user__email",
        "entered_by_user__last_name",
        "entered_by_user__first_name",
    )
    autocomplete_fields = ("patient", "entered_by_user")
    inlines = [
        GlucoseEntriesInline,
        TherapyEntriesInline,
        MealEntriesInline,
        ActivityEntriesInline,
        WellbeingEntriesInline,
        VitalSignsEntriesInline,
    ]
    ordering = ("-entry_datetime",)

    @admin.display(ordering="patient__user__email", description="Email пациента")
    def patient_email(self, obj):
        return obj.patient.user.email


@admin.register(CriticalEvents)
class CriticalEventsAdmin(admin.ModelAdmin):
    list_display = (
        "critical_event_id",
        "event_type",
        "severity",
        "status",
        "entry",
        "patient",
        "acknowledged_by_user",
        "detected_at",
    )
    list_filter = ("event_type", "severity", "status", "detected_at", "acknowledged_at")
    search_fields = (
        "critical_event_id",
        "message",
        "entry__entry_id",
        "entry__patient__user__email",
        "entry__patient__user__last_name",
        "entry__patient__user__first_name",
        "acknowledged_by_user__email",
    )
    autocomplete_fields = ("entry", "acknowledged_by_user")
    ordering = ("-detected_at",)

    @admin.display(ordering="entry__patient__user__email", description="Пациент")
    def patient(self, obj):
        return obj.entry.patient


@admin.register(Notifications)
class NotificationsAdmin(admin.ModelAdmin):
    list_display = (
        "notification_id",
        "notification_type",
        "title",
        "recipient_user",
        "is_read",
        "created_at",
        "read_at",
    )
    list_filter = ("notification_type", "is_read", "created_at", "read_at")
    search_fields = (
        "notification_id",
        "title",
        "message",
        "recipient_user__email",
        "recipient_user__last_name",
        "recipient_user__first_name",
    )
    autocomplete_fields = ("recipient_user", "critical_event")
    ordering = ("-created_at",)
