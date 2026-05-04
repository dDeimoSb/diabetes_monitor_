from datetime import date, datetime, time, timedelta
from decimal import Decimal
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from monitoring.models import (
    ActivityEntries,
    ActivityIntensity,
    AttachmentRequestStatus,
    CriticalEventStatus,
    CriticalEventType,
    CriticalEvents,
    DiabetesType,
    Doctors,
    DoseUnit,
    GlucoseContext,
    GlucoseEntries,
    MealEntries,
    MealType,
    MedicationCategory,
    MonitoringEntries,
    MonitoringEntryType,
    NotificationType,
    Notifications,
    PatientDoctorAttachments,
    Patients,
    Severity,
    TherapyEntries,
    VitalSignsEntries,
    WellbeingEntries,
    WellbeingType,
)


class Command(BaseCommand):
    help = "Создает воспроизводимые тестовые данные на русском языке."

    DEFAULT_DOMAIN = "seed.test"
    DEFAULT_PASSWORD = "TestPass123!"
    DEFAULT_SEED = 20260424

    FIRST_NAMES = (
        "Иван",
        "Петр",
        "Сергей",
        "Дмитрий",
        "Николай",
        "Алексей",
        "Олег",
        "Андрей",
        "Даниил"
    )
    LAST_NAMES = (
        "Иванов",
        "Петров",
        "Сидоров",
        "Смирнов",
        "Кузнецов",
        "Попов",
        "Соколов",
        "Волков",
        "Романов",
        "Орлов",
        "Лебедев",
        "Морозов",
    )
    MIDDLE_NAMES = (
        "Иванович",
        "Петрович",
        "Сергеевич",
        "Дмитриевич",
        "Андреевич",
        "Павлович"
    )
    SPECIALTIES = (
        "Эндокринолог",
        "Терапевт",
        "Диетолог",
        "Кардиолог",
    )
    MEALS = (
        "Овсяная каша, яблоко, чай",
        "Куриный суп и хлеб",
        "Гречка с рыбой",
        "Овощной салат и индейка",
        "Творог на перекус",
        "Рис с овощами",
    )
    ACTIVITIES = (
        "Прогулка",
        "Велотренировка",
        "Плавание",
        "Домашняя тренировка",
        "Скандинавская ходьба",
        "Лечебная физкультура",
    )
    MEDICATIONS = (
        "Инсулин аспарт",
        "Инсулин гларгин",
        "Метформин",
        "Гликлазид",
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--patients",
            type=int,
            default=12,
            help="Количество профилей пациентов.",
        )
        parser.add_argument(
            "--doctors",
            type=int,
            default=3,
            help="Количество профилей врачей.",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=45,
            help="Количество прошлых дней с записями мониторинга.",
        )
        parser.add_argument(
            "--password",
            default=self.DEFAULT_PASSWORD,
            help="Пароль для всех сгенерированных пользователей.",
        )
        parser.add_argument(
            "--domain",
            default=self.DEFAULT_DOMAIN,
            help="Email-домен для сгенерированных пользователей.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=self.DEFAULT_SEED,
            help="Seed для воспроизводимой генерации случайных значений.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Удалить ранее сгенерированные данные домена перед новой генерацией.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Удалить ранее сгенерированные данные домена и завершить работу.",
        )

    def handle(self, *args, **options):
        patients_count = options["patients"]
        doctors_count = options["doctors"]
        days_count = options["days"]
        password = options["password"]
        self.domain = options["domain"].strip().lower().lstrip("@")

        if patients_count < 1:
            raise CommandError("--patients должен быть не меньше 1.")
        if doctors_count < 1:
            raise CommandError("--doctors должен быть не меньше 1.")
        if days_count < 1:
            raise CommandError("--days должен быть не меньше 1.")
        if not self.domain or "." not in self.domain:
            raise CommandError("--domain должен быть похож на email-домен.")
        if options["clear"] and options["reset"]:
            raise CommandError("Используйте либо --clear, либо --reset, но не оба флага сразу.")

        rng = random.Random(options["seed"])
        User = get_user_model()
        user_filter = {"email__iendswith": f"@{self.domain}"}

        if options["clear"]:
            with transaction.atomic():
                removed = self._clear_seed_data(User)
            if removed:
                self.stdout.write(self.style.SUCCESS("Тестовые seed-данные удалены."))
                self.stdout.write(
                    "Удалено: "
                    + ", ".join(f"{key}={value}" for key, value in removed.items())
                )
            else:
                self.stdout.write(f"Seed-пользователи для @{self.domain} не найдены.")
            return

        if User.objects.filter(**user_filter).exists() and not options["reset"]:
            raise CommandError(
                f"Seed-пользователи для @{self.domain} уже существуют. "
                "Запустите команду с --reset, чтобы заменить тестовые данные."
            )

        with transaction.atomic():
            removed = {}
            if options["reset"]:
                removed = self._clear_seed_data(User)

            admin_user = self._create_admin_user(User, password)
            doctors = self._create_doctors(User, doctors_count, password)
            patients = self._create_patients(User, patients_count, password, rng)
            attachments_by_patient = self._create_attachments(doctors, patients, rng)
            counters = self._create_monitoring_data(
                patients,
                attachments_by_patient,
                days_count,
                rng,
            )

        self.stdout.write(self.style.SUCCESS("Тестовые данные сгенерированы."))
        if removed:
            self.stdout.write(
                "Удалены старые seed-данные: "
                + ", ".join(f"{key}={value}" for key, value in removed.items())
            )
        self.stdout.write(f"Администратор: {admin_user.email} / {password}")
        self.stdout.write(f"Врачи: {len(doctors)}")
        self.stdout.write(f"Пациенты: {len(patients)}")
        self.stdout.write(f"Записи мониторинга: {counters['entries']}")
        self.stdout.write(f"Критические события: {counters['critical_events']}")
        self.stdout.write(f"Уведомления: {counters['notifications']}")

    def _clear_seed_data(self, User):
        seed_user_ids = list(
            User.objects.filter(email__iendswith=f"@{self.domain}").values_list(
                "pk",
                flat=True,
            )
        )
        if not seed_user_ids:
            return {}

        seed_patient_ids = list(
            Patients.objects.filter(user_id__in=seed_user_ids).values_list(
                "patient_id",
                flat=True,
            )
        )
        seed_doctor_ids = list(
            Doctors.objects.filter(user_id__in=seed_user_ids).values_list(
                "doctor_id",
                flat=True,
            )
        )
        seed_entry_ids = list(
            MonitoringEntries.objects.filter(patient_id__in=seed_patient_ids).values_list(
                "entry_id",
                flat=True,
            )
        )
        seed_event_ids = list(
            CriticalEvents.objects.filter(entry_id__in=seed_entry_ids).values_list(
                "critical_event_id",
                flat=True,
            )
        )

        notifications_deleted, _ = Notifications.objects.filter(
            Q(recipient_user_id__in=seed_user_ids)
            | Q(critical_event_id__in=seed_event_ids)
        ).delete()
        critical_events_deleted, _ = CriticalEvents.objects.filter(
            critical_event_id__in=seed_event_ids
        ).delete()
        entries_deleted, _ = MonitoringEntries.objects.filter(
            entry_id__in=seed_entry_ids
        ).delete()
        attachments_deleted, _ = PatientDoctorAttachments.objects.filter(
            Q(patient_id__in=seed_patient_ids) | Q(doctor_id__in=seed_doctor_ids)
        ).delete()
        patients_deleted, _ = Patients.objects.filter(
            patient_id__in=seed_patient_ids
        ).delete()
        doctors_deleted, _ = Doctors.objects.filter(
            doctor_id__in=seed_doctor_ids
        ).delete()
        users_deleted, _ = User.objects.filter(pk__in=seed_user_ids).delete()

        return {
            "users": users_deleted,
            "doctors": doctors_deleted,
            "patients": patients_deleted,
            "attachments": attachments_deleted,
            "entries": entries_deleted,
            "critical_events": critical_events_deleted,
            "notifications": notifications_deleted,
        }

    def _create_admin_user(self, User, password):
        return User.objects.create_superuser(
            email=f"admin@{self.domain}",
            password=password,
            first_name="Администратор",
            last_name="Тестовый",
            is_active=True,
        )

    def _create_doctors(self, User, doctors_count, password):
        doctors = []
        for index in range(doctors_count):
            user = User.objects.create_user(
                email=f"doctor{index + 1}@{self.domain}",
                password=password,
                first_name=self.FIRST_NAMES[index % len(self.FIRST_NAMES)],
                last_name=self.LAST_NAMES[index % len(self.LAST_NAMES)],
                middle_name=self.MIDDLE_NAMES[index % len(self.MIDDLE_NAMES)],
                phone=f"+7900100{index + 1:04d}",
                is_active=True,
            )
            doctors.append(
                Doctors.objects.create(
                    user=user,
                    specialty=self.SPECIALTIES[index % len(self.SPECIALTIES)],
                )
            )
        return doctors

    def _create_patients(self, User, patients_count, password, rng):
        diabetes_types = (
            DiabetesType.TYPE_1,
            DiabetesType.TYPE_2,
            DiabetesType.PREDIABETES,
            DiabetesType.OTHER,
        )
        patients = []
        for index in range(patients_count):
            birth_year = rng.randint(1955, 2006)
            birth_date = date(
                birth_year,
                rng.randint(1, 12),
                rng.randint(1, 28),
            )
            user = User.objects.create_user(
                email=f"patient{index + 1:02d}@{self.domain}",
                password=password,
                first_name=self.FIRST_NAMES[(index + 2) % len(self.FIRST_NAMES)],
                last_name=self.LAST_NAMES[(index + 3) % len(self.LAST_NAMES)],
                middle_name=self.MIDDLE_NAMES[(index + 4) % len(self.MIDDLE_NAMES)],
                phone=f"+7900200{index + 1:04d}",
                gender=self._gender_for_index(User, index),
                birth_date=birth_date,
                is_active=True,
            )
            patients.append(
                Patients.objects.create(
                    user=user,
                    diabetes_type=diabetes_types[index % len(diabetes_types)],
                )
            )
        return patients

    def _gender_for_index(self, User, index):
        if index % 2 == 0:
            return User.Gender.MALE
        return User.Gender.FEMALE

    def _create_attachments(self, doctors, patients, rng):
        now = timezone.now()
        attachments_by_patient = {}
        for index, patient in enumerate(patients):
            primary_doctor = doctors[index % len(doctors)]
            PatientDoctorAttachments.objects.create(
                patient=patient,
                doctor=primary_doctor,
                status=AttachmentRequestStatus.CONFIRMED,
                created_at=now - timedelta(days=rng.randint(20, 90)),
                resolved_at=now - timedelta(days=rng.randint(1, 19)),
                expires_at=now + timedelta(days=365),
            )
            attachments_by_patient[patient.patient_id] = [primary_doctor]

            if len(doctors) > 1 and index % 3 == 0:
                PatientDoctorAttachments.objects.create(
                    patient=patient,
                    doctor=doctors[(index + 1) % len(doctors)],
                    status=AttachmentRequestStatus.PENDING,
                    created_at=now - timedelta(days=1),
                    expires_at=now + timedelta(days=6),
                )

            if len(doctors) > 2 and index % 4 == 0:
                PatientDoctorAttachments.objects.create(
                    patient=patient,
                    doctor=doctors[(index + 2) % len(doctors)],
                    status=AttachmentRequestStatus.REJECTED,
                    created_at=now - timedelta(days=18),
                    resolved_at=now - timedelta(days=17),
                    expires_at=now - timedelta(days=11),
                )

        return attachments_by_patient

    def _create_monitoring_data(self, patients, attachments_by_patient, days_count, rng):
        counters = {"entries": 0, "critical_events": 0, "notifications": 0}
        today = timezone.localdate()
        now = timezone.now()

        for patient_index, patient in enumerate(patients):
            for day_offset in range(days_count):
                current_date = today - timedelta(days=day_offset)
                daily_datetimes = [
                    self._aware_at(current_date, 7, rng.randint(10, 50)),
                    self._aware_at(current_date, 13, rng.randint(0, 45)),
                    self._aware_at(current_date, 19, rng.randint(0, 45)),
                    self._aware_at(current_date, 21, rng.randint(0, 30)),
                ]
                daily_datetimes = [item for item in daily_datetimes if item <= now]
                if not daily_datetimes:
                    continue

                self._create_glucose_entry(
                    patient,
                    daily_datetimes[0],
                    GlucoseContext.FASTING,
                    self._glucose_value(patient_index, day_offset, rng, fasting=True),
                    attachments_by_patient,
                    rng,
                    counters,
                )

                self._create_therapy_entry(patient, daily_datetimes[0], rng, counters)

                if len(daily_datetimes) > 1:
                    self._create_meal_entry(patient, daily_datetimes[1], rng, counters)

                if len(daily_datetimes) > 2:
                    self._create_glucose_entry(
                        patient,
                        daily_datetimes[2],
                        GlucoseContext.AFTER_MEAL,
                        self._glucose_value(
                            patient_index,
                            day_offset,
                            rng,
                            fasting=False,
                        ),
                        attachments_by_patient,
                        rng,
                        counters,
                    )

                if day_offset % 3 == patient_index % 3:
                    self._create_vital_signs_entry(
                        patient,
                        daily_datetimes[-1],
                        day_offset,
                        attachments_by_patient,
                        rng,
                        counters,
                    )

                if day_offset % 4 == patient_index % 4:
                    self._create_activity_entry(patient, daily_datetimes[-1], rng, counters)

                if day_offset % 11 == patient_index % 11:
                    self._create_wellbeing_entry(
                        patient,
                        daily_datetimes[-1],
                        attachments_by_patient,
                        rng,
                        counters,
                    )

        return counters

    def _aware_at(self, current_date, hour, minute):
        value = datetime.combine(current_date, time(hour, minute))
        return timezone.make_aware(value, timezone.get_current_timezone())

    def _create_base_entry(self, patient, entry_type, entry_datetime, comment=""):
        return MonitoringEntries.objects.create(
            patient=patient,
            entered_by_user=patient.user,
            entry_type=entry_type,
            entry_datetime=entry_datetime,
            comment=comment,
            created_at=entry_datetime,
            updated_at=entry_datetime,
        )

    def _create_glucose_entry(
        self,
        patient,
        entry_datetime,
        glucose_context,
        glucose_value,
        attachments_by_patient,
        rng,
        counters,
    ):
        entry = self._create_base_entry(
            patient,
            MonitoringEntryType.GLUCOSE,
            entry_datetime,
        )
        GlucoseEntries.objects.create(
            entry=entry,
            glucose_value_mmol=glucose_value,
            glucose_context=glucose_context,
        )
        counters["entries"] += 1
        self._maybe_create_glucose_event(
            entry,
            glucose_value,
            attachments_by_patient,
            rng,
            counters,
        )

    def _glucose_value(self, patient_index, day_offset, rng, fasting):
        mean = 6.2 if fasting else 8.4
        value = rng.normalvariate(mean + (patient_index % 4) * 0.25, 1.15)

        if day_offset % 17 == patient_index % 7:
            value = rng.choice((2.7, 3.3, 14.8, 17.1))
        elif day_offset % 13 == patient_index % 5:
            value += rng.choice((-2.2, 3.7))

        return self._decimal_between(value, "2.3", "19.5")

    def _create_therapy_entry(self, patient, entry_datetime, rng, counters):
        medication = rng.choice(self.MEDICATIONS)
        entry = self._create_base_entry(
            patient,
            MonitoringEntryType.THERAPY,
            entry_datetime + timedelta(minutes=10),
        )
        if medication.startswith("Инсулин"):
            category = MedicationCategory.INSULIN
            dose_unit = DoseUnit.UNIT
            dose_amount = self._decimal_between(rng.uniform(4, 18), "1.0", "30.0")
            method = "Подкожно"
        else:
            category = MedicationCategory.GLUCOSE_LOWERING
            dose_unit = DoseUnit.MILLIGRAM
            dose_amount = self._decimal_between(rng.uniform(500, 1500), "250", "2000")
            method = "Перорально"

        TherapyEntries.objects.create(
            entry=entry,
            medication_name=medication,
            medication_category=category,
            dose_amount=dose_amount,
            dose_unit=dose_unit,
            administration_method=method,
        )
        counters["entries"] += 1

    def _create_meal_entry(self, patient, entry_datetime, rng, counters):
        carbohydrates = self._decimal_between(rng.uniform(25, 95), "5", "120")
        entry = self._create_base_entry(
            patient,
            MonitoringEntryType.MEAL,
            entry_datetime,
        )
        MealEntries.objects.create(
            entry=entry,
            meal_type=rng.choice(
                (MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER, MealType.SNACK)
            ),
            meal_description=rng.choice(self.MEALS),
            carbohydrates_g=carbohydrates,
            bread_units=(carbohydrates / Decimal("12")).quantize(Decimal("0.01")),
        )
        counters["entries"] += 1

    def _create_activity_entry(self, patient, entry_datetime, rng, counters):
        entry = self._create_base_entry(
            patient,
            MonitoringEntryType.ACTIVITY,
            entry_datetime + timedelta(minutes=25),
        )
        ActivityEntries.objects.create(
            entry=entry,
            activity_type=rng.choice(self.ACTIVITIES),
            activity_duration_min=rng.randint(20, 80),
            activity_intensity=rng.choice(
                (
                    ActivityIntensity.LOW,
                    ActivityIntensity.MODERATE,
                    ActivityIntensity.HIGH,
                )
            ),
        )
        counters["entries"] += 1

    def _create_wellbeing_entry(
        self,
        patient,
        entry_datetime,
        attachments_by_patient,
        rng,
        counters,
    ):
        wellbeing_type = rng.choice(
            (
                WellbeingType.STRESS,
                WellbeingType.COMPLAINT,
                WellbeingType.SLEEP_DISORDER,
                WellbeingType.HYPERGLYCEMIA,
                WellbeingType.HYPOGLYCEMIA,
            )
        )
        severity = rng.choice((Severity.LOW, Severity.MODERATE, Severity.HIGH))
        entry = self._create_base_entry(
            patient,
            MonitoringEntryType.WELLBEING,
            entry_datetime + timedelta(minutes=40),
            "Тестовая запись о самочувствии.",
        )
        WellbeingEntries.objects.create(
            entry=entry,
            wellbeing_type=wellbeing_type,
            symptom_description="Усталость, жажда или головная боль.",
            severity=severity,
        )
        counters["entries"] += 1

        if severity == Severity.HIGH:
            self._create_critical_event(
                entry,
                CriticalEventType.OTHER,
                Severity.HIGH,
                "Жалоба на выраженное ухудшение самочувствия.",
                attachments_by_patient,
                rng,
                counters,
            )

    def _create_vital_signs_entry(
        self,
        patient,
        entry_datetime,
        day_offset,
        attachments_by_patient,
        rng,
        counters,
    ):
        systolic = int(rng.normalvariate(126, 14))
        diastolic = int(rng.normalvariate(80, 8))
        pulse = int(rng.normalvariate(76, 10))

        if day_offset % 19 == 0:
            systolic = rng.choice((88, 166, 178))
            diastolic = rng.choice((55, 98, 108))
            pulse = rng.choice((48, 112, 128))

        entry = self._create_base_entry(
            patient,
            MonitoringEntryType.VITAL_SIGNS,
            entry_datetime + timedelta(minutes=15),
        )
        VitalSignsEntries.objects.create(
            entry=entry,
            weight_kg=self._decimal_between(rng.uniform(58, 112), "45", "150"),
            systolic_bp=systolic,
            diastolic_bp=diastolic,
            pulse_bpm=pulse,
        )
        counters["entries"] += 1

        if systolic >= 160 or diastolic >= 100:
            self._create_critical_event(
                entry,
                CriticalEventType.HIGH_BP,
                Severity.HIGH,
                f"Высокое артериальное давление: {systolic}/{diastolic}.",
                attachments_by_patient,
                rng,
                counters,
            )
        elif systolic <= 90 or diastolic <= 55:
            self._create_critical_event(
                entry,
                CriticalEventType.LOW_BP,
                Severity.MODERATE,
                f"Низкое артериальное давление: {systolic}/{diastolic}.",
                attachments_by_patient,
                rng,
                counters,
            )

        if pulse >= 115:
            self._create_critical_event(
                entry,
                CriticalEventType.TACHYCARDIA,
                Severity.HIGH,
                f"Высокий пульс: {pulse} уд/мин.",
                attachments_by_patient,
                rng,
                counters,
            )
        elif pulse <= 50:
            self._create_critical_event(
                entry,
                CriticalEventType.BRADYCARDIA,
                Severity.MODERATE,
                f"Низкий пульс: {pulse} уд/мин.",
                attachments_by_patient,
                rng,
                counters,
            )

    def _maybe_create_glucose_event(
        self,
        entry,
        glucose_value,
        attachments_by_patient,
        rng,
        counters,
    ):
        if glucose_value < Decimal("3.9"):
            severity = Severity.CRITICAL if glucose_value < Decimal("3.0") else Severity.HIGH
            self._create_critical_event(
                entry,
                CriticalEventType.LOW_GLUCOSE,
                severity,
                f"Низкий уровень глюкозы: {glucose_value} ммоль/л.",
                attachments_by_patient,
                rng,
                counters,
            )
        elif glucose_value > Decimal("13.9"):
            severity = Severity.CRITICAL if glucose_value > Decimal("16.7") else Severity.HIGH
            self._create_critical_event(
                entry,
                CriticalEventType.HIGH_GLUCOSE,
                severity,
                f"Высокий уровень глюкозы: {glucose_value} ммоль/л.",
                attachments_by_patient,
                rng,
                counters,
            )

    def _create_critical_event(
        self,
        entry,
        event_type,
        severity,
        message,
        attachments_by_patient,
        rng,
        counters,
    ):
        doctors = attachments_by_patient.get(entry.patient_id, [])
        doctor_users = [doctor.user for doctor in doctors]
        status = rng.choice(
            (
                CriticalEventStatus.NEW,
                CriticalEventStatus.NEW,
                CriticalEventStatus.ACKNOWLEDGED,
                CriticalEventStatus.CLOSED,
            )
        )
        acknowledged_by_user = None
        acknowledged_at = None
        if status != CriticalEventStatus.NEW and doctor_users:
            acknowledged_by_user = rng.choice(doctor_users)
            acknowledged_at = entry.entry_datetime + timedelta(hours=rng.randint(1, 12))

        event = CriticalEvents.objects.create(
            entry=entry,
            event_type=event_type,
            severity=severity,
            message=message,
            status=status,
            detected_at=entry.entry_datetime,
            acknowledged_by_user=acknowledged_by_user,
            acknowledged_at=acknowledged_at,
        )
        counters["critical_events"] += 1
        counters["notifications"] += self._create_notifications(
            event,
            doctor_users,
            rng,
        )

    def _create_notifications(self, event, doctor_users, rng):
        recipients = [
            (
                event.entry.patient.user,
                NotificationType.WARNING,
                "Критический показатель",
            )
        ]
        for doctor_user in doctor_users:
            recipients.append(
                (
                    doctor_user,
                    NotificationType.DOCTOR_ALERT,
                    f"Оповещение по пациенту: {event.entry.patient.user.display_name}",
                )
            )

        created = 0
        for recipient_user, notification_type, title in recipients:
            is_read = rng.random() < 0.45
            Notifications.objects.create(
                recipient_user=recipient_user,
                critical_event=event,
                notification_type=notification_type,
                title=title,
                message=event.message,
                is_read=is_read,
                created_at=event.detected_at,
                read_at=(
                    event.detected_at + timedelta(hours=rng.randint(1, 24))
                    if is_read
                    else None
                ),
            )
            created += 1
        return created

    def _decimal_between(self, value, minimum, maximum):
        value = max(float(minimum), min(float(maximum), float(value)))
        return Decimal(str(round(value, 2))).quantize(Decimal("0.01"))
