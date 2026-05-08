from decimal import Decimal

from django.db import transaction

from monitoring.models import (
    AttachmentRequestStatus,
    CriticalEventStatus,
    CriticalEventType,
    CriticalEvents,
    MonitoringEntries,
    NotificationType,
    Notifications,
    PatientDoctorAttachments,
    Severity,
    WellbeingType,
)


def _format_decimal(value):
    return str(value)


def _format_bp(systolic, diastolic):
    if systolic and diastolic:
        return f"{systolic}/{diastolic}"
    if systolic:
        return f"систолическое {systolic}"
    return f"диастолическое {diastolic}"


def _entry_with_details(entry):
    return (
        MonitoringEntries.objects.select_related(
            "patient__user",
            "glucose_entry",
            "vital_signs_entry",
            "wellbeing_entry",
        )
        .get(pk=entry.pk)
    )


def _confirmed_doctor_users(patient):
    attachments = (
        PatientDoctorAttachments.objects.select_related("doctor__user")
        .filter(
            patient=patient,
            status=AttachmentRequestStatus.CONFIRMED,
        )
        .order_by("doctor_id")
    )
    return [attachment.doctor.user for attachment in attachments]


# Правила критических событий
def _event_specs_for_entry(entry):
    specs = []

    if hasattr(entry, "glucose_entry"):
        glucose_value = entry.glucose_entry.glucose_value_mmol
        if glucose_value < Decimal("3.9"):
            severity = Severity.CRITICAL if glucose_value < Decimal("3.0") else Severity.HIGH
            specs.append(
                {
                    "event_type": CriticalEventType.LOW_GLUCOSE,
                    "severity": severity,
                    "message": (
                        f"Низкий уровень глюкозы: {_format_decimal(glucose_value)} ммоль/л."
                    ),
                }
            )
        elif glucose_value > Decimal("13.9"):
            severity = Severity.CRITICAL if glucose_value > Decimal("16.7") else Severity.HIGH
            specs.append(
                {
                    "event_type": CriticalEventType.HIGH_GLUCOSE,
                    "severity": severity,
                    "message": (
                        f"Высокий уровень глюкозы: {_format_decimal(glucose_value)} ммоль/л."
                    ),
                }
            )

    if hasattr(entry, "vital_signs_entry"):
        vital = entry.vital_signs_entry
        systolic = vital.systolic_bp
        diastolic = vital.diastolic_bp
        pulse = vital.pulse_bpm

        if (systolic and systolic >= 160) or (diastolic and diastolic >= 100):
            severity = (
                Severity.CRITICAL
                if (systolic and systolic >= 180) or (diastolic and diastolic >= 110)
                else Severity.HIGH
            )
            specs.append(
                {
                    "event_type": CriticalEventType.HIGH_BP,
                    "severity": severity,
                    "message": f"Высокое артериальное давление: {_format_bp(systolic, diastolic)}.",
                }
            )
        elif (systolic and systolic <= 90) or (diastolic and diastolic <= 55):
            severity = (
                Severity.HIGH
                if (systolic and systolic <= 80) or (diastolic and diastolic <= 50)
                else Severity.MODERATE
            )
            specs.append(
                {
                    "event_type": CriticalEventType.LOW_BP,
                    "severity": severity,
                    "message": f"Низкое артериальное давление: {_format_bp(systolic, diastolic)}.",
                }
            )

        if pulse and pulse >= 115:
            severity = Severity.CRITICAL if pulse >= 130 else Severity.HIGH
            specs.append(
                {
                    "event_type": CriticalEventType.TACHYCARDIA,
                    "severity": severity,
                    "message": f"Высокий пульс: {pulse} уд/мин.",
                }
            )
        elif pulse and pulse <= 50:
            severity = Severity.HIGH if pulse <= 40 else Severity.MODERATE
            specs.append(
                {
                    "event_type": CriticalEventType.BRADYCARDIA,
                    "severity": severity,
                    "message": f"Низкий пульс: {pulse} уд/мин.",
                }
            )

    if hasattr(entry, "wellbeing_entry"):
        wellbeing = entry.wellbeing_entry
        if wellbeing.severity in {Severity.HIGH, Severity.CRITICAL}:
            if wellbeing.wellbeing_type == WellbeingType.HYPOGLYCEMIA:
                event_type = CriticalEventType.LOW_GLUCOSE
            elif wellbeing.wellbeing_type == WellbeingType.HYPERGLYCEMIA:
                event_type = CriticalEventType.HIGH_GLUCOSE
            else:
                event_type = CriticalEventType.OTHER
            specs.append(
                {
                    "event_type": event_type,
                    "severity": wellbeing.severity,
                    "message": "Жалоба на выраженное ухудшение самочувствия.",
                }
            )

    for spec in specs:
        spec["message"] = (
            f"{spec['message']} При выраженных симптомах обратитесь к врачу "
            "или за неотложной помощью."
        )
    return specs


# Уведомления участникам
def _create_notifications(event, doctor_users):
    recipients = [
        (
            event.entry.patient.user,
            NotificationType.WARNING,
            "Критический показатель",
        )
    ]
    recipients.extend(
        (
            doctor_user,
            NotificationType.DOCTOR_ALERT,
            f"Оповещение по пациенту: {event.entry.patient.user.display_name}",
        )
        for doctor_user in doctor_users
    )

    notifications = [
        Notifications(
            recipient_user=recipient_user,
            critical_event=event,
            notification_type=notification_type,
            title=title,
            message=event.message,
            created_at=event.detected_at,
        )
        for recipient_user, notification_type, title in recipients
    ]
    Notifications.objects.bulk_create(notifications)


def delete_critical_events_for_entry(entry):
    events = CriticalEvents.objects.filter(entry=entry)
    Notifications.objects.filter(critical_event__in=events).delete()
    return events.delete()


@transaction.atomic
def sync_critical_events_for_entry(entry):
    entry = _entry_with_details(entry)
    delete_critical_events_for_entry(entry)

    doctor_users = _confirmed_doctor_users(entry.patient)
    created_events = []
    for spec in _event_specs_for_entry(entry):
        event = CriticalEvents.objects.create(
            entry=entry,
            event_type=spec["event_type"],
            severity=spec["severity"],
            message=spec["message"],
            status=CriticalEventStatus.NEW,
            detected_at=entry.entry_datetime,
        )
        _create_notifications(event, doctor_users)
        created_events.append(event)

    return created_events
