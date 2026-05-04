from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Gender(models.TextChoices):
    MALE = "Мужской", "Мужской"
    FEMALE = "Женский", "Женский"


class DiabetesType(models.TextChoices):
    TYPE_1 = "СД 1 типа", "СД 1 типа"
    TYPE_2 = "СД 2 типа", "СД 2 типа"
    GESTATIONAL = "Гестационный диабет", "Гестационный диабет"
    PREDIABETES = "Предиабет", "Предиабет"
    OTHER = "Другое", "Другое"


class MonitoringEntryType(models.TextChoices):
    GLUCOSE = "Глюкоза", "Глюкоза"
    THERAPY = "Терапия", "Терапия"
    MEAL = "Питание", "Питание"
    ACTIVITY = "Физическая активность", "Физическая активность"
    WELLBEING = "Самочувствие", "Самочувствие"
    VITAL_SIGNS = "Дополнительные показатели", "Дополнительные показатели"


class GlucoseContext(models.TextChoices):
    FASTING = "Натощак", "Натощак"
    BEFORE_MEAL = "До еды", "До еды"
    AFTER_MEAL = "После еды", "После еды"
    BEFORE_SLEEP = "Перед сном", "Перед сном"
    NIGHT = "Ночью", "Ночью"
    OTHER = "Другое", "Другое"


class MedicationCategory(models.TextChoices):
    INSULIN = "Инсулин", "Инсулин"
    GLUCOSE_LOWERING = "Сахароснижающий препарат", "Сахароснижающий препарат"
    OTHER = "Другое", "Другое"


class DoseUnit(models.TextChoices):
    UNIT = "ЕД", "ЕД"
    MILLIGRAM = "мг", "мг"
    MILLILITER = "мл", "мл"
    TABLET = "Таблетка", "Таблетка"
    CAPSULE = "Капсула", "Капсула"
    OTHER = "Другое", "Другое"


class MealType(models.TextChoices):
    BREAKFAST = "Завтрак", "Завтрак"
    LUNCH = "Обед", "Обед"
    DINNER = "Ужин", "Ужин"
    SNACK = "Перекус", "Перекус"
    OTHER = "Другое", "Другое"


class ActivityIntensity(models.TextChoices):
    LOW = "Низкая", "Низкая"
    MODERATE = "Умеренная", "Умеренная"
    HIGH = "Высокая", "Высокая"


class WellbeingType(models.TextChoices):
    HYPOGLYCEMIA = "Гипогликемия", "Гипогликемия"
    HYPERGLYCEMIA = "Гипергликемия", "Гипергликемия"
    STRESS = "Стресс", "Стресс"
    INFECTION = "Инфекция", "Инфекция"
    SLEEP_DISORDER = "Нарушение сна", "Нарушение сна"
    COMPLAINT = "Жалоба", "Жалоба"
    OTHER = "Другое", "Другое"


class Severity(models.TextChoices):
    LOW = "Лёгкая", "Лёгкая"
    MODERATE = "Умеренная", "Умеренная"
    HIGH = "Высокая", "Высокая"
    CRITICAL = "Критическая", "Критическая"


class CriticalEventType(models.TextChoices):
    LOW_GLUCOSE = "Низкая глюкоза", "Низкая глюкоза"
    HIGH_GLUCOSE = "Высокая глюкоза", "Высокая глюкоза"
    HIGH_BP = "Высокое АД", "Высокое АД"
    LOW_BP = "Низкое АД", "Низкое АД"
    TACHYCARDIA = "Тахикардия", "Тахикардия"
    BRADYCARDIA = "Брадикардия", "Брадикардия"
    OTHER = "Другое", "Другое"


class CriticalEventStatus(models.TextChoices):
    NEW = "Новое", "Новое"
    ACKNOWLEDGED = "Подтверждено", "Подтверждено"
    CLOSED = "Закрыто", "Закрыто"


class NotificationType(models.TextChoices):
    WARNING = "Предупреждение", "Предупреждение"
    DOCTOR_ALERT = "Оповещение врачу", "Оповещение врачу"
    SYSTEM = "Системное", "Системное"

class AttachmentRequestStatus(models.TextChoices):
    PENDING = "В обработке", "В обработке"
    CONFIRMED = "Подтвержденный", "Подтвержденный"
    REJECTED = "Отклоненный", "Отклоненный"
    CANCELED = "Отмененный", "Отмененный"
    EXPIRED = "Срок действия истек", "Срок действия истек"


class Doctors(models.Model):
    doctor_id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name="doctor_profile",
    )
    specialty = models.CharField(max_length=150)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "doctors"
        verbose_name = "Doctor"
        verbose_name_plural = "Doctors"
        indexes = [
            models.Index(fields=["user"], name="idx_doctors_user"),
        ]

    def __str__(self):
        return f"{self.user} ({self.specialty})"


class Patients(models.Model):
    patient_id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name="patient_profile",
    )
    diabetes_type = models.CharField(max_length=30, choices=DiabetesType.choices)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "patients"
        verbose_name = "Patient"
        verbose_name_plural = "Patients"
        indexes = [
            models.Index(fields=["user"], name="idx_patients_user"),
        ]

    def __str__(self):
        return f"{self.user} ({self.diabetes_type})"


class PatientDoctorAttachments(models.Model):
    attachment_id = models.BigAutoField(primary_key=True)
    patient = models.ForeignKey(
        "Patients",
        on_delete=models.CASCADE,
        related_name="doctor_attachments",
    )
    doctor = models.ForeignKey(
        "Doctors",
        on_delete=models.CASCADE,
        related_name="patient_attachments",
    )
    status = models.CharField(max_length=30, choices=AttachmentRequestStatus.choices)
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "patient_doctor_attachments"
        verbose_name = "Patient-doctor attachment"
        verbose_name_plural = "Patient-doctor attachments"
        indexes = [
            models.Index(fields=["doctor", "status"], name="idx_pda_doctor_status"),
            models.Index(fields=["patient", "status"], name="idx_pda_patient_status"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "doctor"],
                condition=models.Q(status=AttachmentRequestStatus.PENDING),
                name="uniq_pda_patient_doctor_pending",
            ),
            models.UniqueConstraint(
                fields=["patient", "doctor"],
                condition=models.Q(status=AttachmentRequestStatus.CONFIRMED),
                name="uniq_pda_patient_doctor_confirmed",
            ),
        ]

    def __str__(self):
        return f"{self.patient} - {self.doctor} ({self.status})"

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    @property
    def is_pending(self):
        return self.status == AttachmentRequestStatus.PENDING

    @property
    def status_badge_class(self):
        return {
            AttachmentRequestStatus.PENDING: "status-warning",
            AttachmentRequestStatus.CONFIRMED: "status-success",
            AttachmentRequestStatus.REJECTED: "status-danger",
            AttachmentRequestStatus.CANCELED: "status-neutral",
            AttachmentRequestStatus.EXPIRED: "status-neutral",
        }.get(self.status, "status-neutral")

    @classmethod
    def expire_pending(cls):
        now = timezone.now()
        return cls.objects.filter(
            status=AttachmentRequestStatus.PENDING,
            expires_at__lte=now,
        ).update(
            status=AttachmentRequestStatus.EXPIRED,
            resolved_at=now,
        )


class MonitoringEntries(models.Model):
    entry_id = models.BigAutoField(primary_key=True)
    patient = models.ForeignKey(
        "Patients",
        on_delete=models.RESTRICT,
        related_name="monitoring_entries",
    )
    entered_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="entered_monitoring_entries",
    )
    entry_type = models.CharField(max_length=40, choices=MonitoringEntryType.choices)
    entry_datetime = models.DateTimeField()
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "monitoring_entries"
        verbose_name = "Monitoring entry"
        verbose_name_plural = "Monitoring entries"
        indexes = [
            models.Index(
                fields=["patient", "-entry_datetime"],
                name="idx_me_patient_dt",
            ),
            models.Index(
                fields=["entry_type", "-entry_datetime"],
                name="idx_me_type_dt",
            ),
            models.Index(fields=["entered_by_user"], name="idx_me_entered_by"),
        ]

    def __str__(self):
        return f"{self.get_entry_type_display()} #{self.entry_id}"


class GlucoseEntries(models.Model):
    entry = models.OneToOneField(
        "MonitoringEntries",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="glucose_entry",
    )
    glucose_value_mmol = models.DecimalField(max_digits=5, decimal_places=2)
    glucose_context = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=GlucoseContext.choices,
    )

    class Meta:
        db_table = "glucose_entries"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    glucose_value_mmol__gte=Decimal("0.1"),
                    glucose_value_mmol__lte=Decimal("40"),
                ),
                name="chk_glucose_value_range",
            ),
        ]


class TherapyEntries(models.Model):
    entry = models.OneToOneField(
        "MonitoringEntries",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="therapy_entry",
    )
    medication_name = models.CharField(max_length=150)
    medication_category = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        choices=MedicationCategory.choices,
    )
    dose_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    dose_unit = models.CharField(max_length=20, blank=True, null=True, choices=DoseUnit.choices)
    administration_method = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = "therapy_entries"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(dose_amount__isnull=True)
                    | models.Q(
                        dose_amount__gte=Decimal("0"),
                        dose_amount__lte=Decimal("100000"),
                    )
                ),
                name="chk_therapy_dose_range",
            ),
        ]


class MealEntries(models.Model):
    entry = models.OneToOneField(
        "MonitoringEntries",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="meal_entry",
    )
    meal_type = models.CharField(max_length=20, blank=True, null=True, choices=MealType.choices)
    meal_description = models.TextField(blank=True, null=True)
    carbohydrates_g = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    bread_units = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = "meal_entries"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(carbohydrates_g__isnull=True)
                    | models.Q(
                        carbohydrates_g__gte=Decimal("0"),
                        carbohydrates_g__lte=Decimal("1000"),
                    )
                ),
                name="chk_meal_carbs_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(bread_units__isnull=True)
                    | models.Q(
                        bread_units__gte=Decimal("0"),
                        bread_units__lte=Decimal("100"),
                    )
                ),
                name="chk_meal_bu_range",
            ),
        ]


class ActivityEntries(models.Model):
    entry = models.OneToOneField(
        "MonitoringEntries",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="activity_entry",
    )
    activity_type = models.CharField(max_length=100)
    activity_duration_min = models.IntegerField(blank=True, null=True)
    activity_intensity = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=ActivityIntensity.choices,
    )

    class Meta:
        db_table = "activity_entries"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(activity_duration_min__isnull=True)
                    | models.Q(
                        activity_duration_min__gte=1,
                        activity_duration_min__lte=1440,
                    )
                ),
                name="chk_activity_duration_range",
            ),
        ]


class WellbeingEntries(models.Model):
    entry = models.OneToOneField(
        "MonitoringEntries",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="wellbeing_entry",
    )
    wellbeing_type = models.CharField(max_length=30, choices=WellbeingType.choices)
    symptom_description = models.TextField(blank=True, null=True)
    severity = models.CharField(max_length=20, blank=True, null=True, choices=Severity.choices)

    class Meta:
        db_table = "wellbeing_entries"


class VitalSignsEntries(models.Model):
    entry = models.OneToOneField(
        "MonitoringEntries",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="vital_signs_entry",
    )
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    systolic_bp = models.IntegerField(blank=True, null=True)
    diastolic_bp = models.IntegerField(blank=True, null=True)
    pulse_bpm = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = "vital_signs_entries"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(weight_kg__isnull=True)
                    | models.Q(
                        weight_kg__gte=Decimal("1"),
                        weight_kg__lte=Decimal("500"),
                    )
                ),
                name="chk_vital_weight_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(systolic_bp__isnull=True)
                    | models.Q(systolic_bp__gte=50, systolic_bp__lte=300)
                ),
                name="chk_vital_systolic_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(diastolic_bp__isnull=True)
                    | models.Q(diastolic_bp__gte=30, diastolic_bp__lte=200)
                ),
                name="chk_vital_diastolic_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(pulse_bpm__isnull=True)
                    | models.Q(pulse_bpm__gte=20, pulse_bpm__lte=250)
                ),
                name="chk_vital_pulse_range",
            ),
        ]


class CriticalEvents(models.Model):
    critical_event_id = models.BigAutoField(primary_key=True)
    entry = models.ForeignKey(
        "MonitoringEntries",
        on_delete=models.CASCADE,
        related_name="critical_events",
    )
    event_type = models.CharField(max_length=30, choices=CriticalEventType.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=CriticalEventStatus.choices,
        default=CriticalEventStatus.NEW,
    )
    detected_at = models.DateTimeField(default=timezone.now)
    acknowledged_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="acknowledged_critical_events",
    )
    acknowledged_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "critical_events"
        verbose_name = "Critical event"
        verbose_name_plural = "Critical events"
        indexes = [
            models.Index(fields=["entry"], name="idx_critical_events_entry"),
            models.Index(
                fields=["status", "-detected_at"],
                name="idx_ce_status_dt",
            ),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} ({self.get_status_display()})"


class Notifications(models.Model):
    notification_id = models.BigAutoField(primary_key=True)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="notifications",
    )
    critical_event = models.ForeignKey(
        "CriticalEvents",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "notifications"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(
                fields=["recipient_user", "is_read"],
                name="idx_notif_user_read",
            ),
        ]

    def __str__(self):
        return self.title
