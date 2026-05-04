from django import forms
from django.db import transaction
from django.utils import timezone

from monitoring.models import (
    ActivityEntries,
    ActivityIntensity,
    AttachmentRequestStatus,
    DoseUnit,
    GlucoseContext,
    GlucoseEntries,
    MealEntries,
    MealType,
    MedicationCategory,
    MonitoringEntries,
    MonitoringEntryType,
    PatientDoctorAttachments,
    TherapyEntries,
    VitalSignsEntries,
    WellbeingEntries,
    WellbeingType,
)


INPUT_ATTRS = {"class": "input-text"}
SELECT_ATTRS = {"class": "input-select"}


class AttachmentResponseForm(forms.Form):
    ACTION_CONFIRM = "confirm"
    ACTION_REJECT = "reject"
    ACTION_CHOICES = (
        (ACTION_CONFIRM, "Подтвердить"),
        (ACTION_REJECT, "Отклонить"),
    )

    attachment_id = forms.IntegerField(widget=forms.HiddenInput())
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.HiddenInput())

    def __init__(self, *args, patient_profile, **kwargs):
        self.patient_profile = patient_profile
        self.attachment = None
        self.expired_attachment = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        attachment_id = cleaned_data.get("attachment_id")
        if attachment_id in (None, ""):
            return cleaned_data

        attachment = (
            PatientDoctorAttachments.objects.select_related("doctor__user", "patient__user")
            .filter(attachment_id=attachment_id, patient=self.patient_profile)
            .first()
        )
        if attachment is None:
            raise forms.ValidationError("Запрос на прикрепление не найден.")

        if attachment.status != AttachmentRequestStatus.PENDING:
            raise forms.ValidationError("Этот запрос уже был обработан.")

        if attachment.is_expired:
            self.expired_attachment = attachment
            raise forms.ValidationError("Срок действия запроса уже истек.")

        self.attachment = attachment
        return cleaned_data


class MonitoringEntryForm(forms.Form):
    entry_type = forms.ChoiceField(
        label="Тип записи",
        choices=MonitoringEntryType.choices,
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    entry_datetime = forms.DateTimeField(
        label="Дата и время",
        input_formats=("%Y-%m-%dT%H:%M",),
        widget=forms.DateTimeInput(
            attrs={**INPUT_ATTRS, "type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(
            attrs={**INPUT_ATTRS, "placeholder": "Дополнительная информация"}
        ),
    )

    glucose_value_mmol = forms.DecimalField(
        label="Уровень глюкозы, ммоль/л",
        required=False,
        min_value=0.1,
        max_value=40,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={**INPUT_ATTRS, "step": "0.1", "placeholder": "Например, 6.4"}
        ),
    )
    glucose_context = forms.ChoiceField(
        label="Контекст измерения",
        required=False,
        choices=[("", "---------"), *GlucoseContext.choices],
        widget=forms.Select(attrs=SELECT_ATTRS),
    )

    medication_name = forms.CharField(
        label="Название препарата",
        required=False,
        max_length=150,
        widget=forms.TextInput(
            attrs={**INPUT_ATTRS, "placeholder": "Например, инсулин короткого действия"}
        ),
    )
    medication_category = forms.ChoiceField(
        label="Категория препарата",
        required=False,
        choices=[("", "---------"), *MedicationCategory.choices],
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    dose_amount = forms.DecimalField(
        label="Доза",
        required=False,
        min_value=0,
        max_value=100000,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={**INPUT_ATTRS, "step": "0.1", "placeholder": "Например, 8"}
        ),
    )
    dose_unit = forms.ChoiceField(
        label="Единица дозы",
        required=False,
        choices=[("", "---------"), *DoseUnit.choices],
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    administration_method = forms.CharField(
        label="Способ введения",
        required=False,
        max_length=50,
        widget=forms.TextInput(
            attrs={**INPUT_ATTRS, "placeholder": "Например, подкожно"}
        ),
    )

    meal_type = forms.ChoiceField(
        label="Прием пищи",
        required=False,
        choices=[("", "---------"), *MealType.choices],
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    meal_description = forms.CharField(
        label="Описание питания",
        required=False,
        widget=forms.Textarea(
            attrs={**INPUT_ATTRS, "placeholder": "Что было в приеме пищи"}
        ),
    )
    carbohydrates_g = forms.DecimalField(
        label="Углеводы, г",
        required=False,
        min_value=0,
        max_value=1000,
        max_digits=7,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={**INPUT_ATTRS, "step": "0.1", "placeholder": "Например, 45"}
        ),
    )
    bread_units = forms.DecimalField(
        label="Хлебные единицы",
        required=False,
        min_value=0,
        max_value=100,
        max_digits=6,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={**INPUT_ATTRS, "step": "0.1", "placeholder": "Например, 3.5"}
        ),
    )

    activity_type = forms.CharField(
        label="Вид активности",
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={**INPUT_ATTRS, "placeholder": "Например, прогулка"}
        ),
    )
    activity_duration_min = forms.IntegerField(
        label="Длительность, мин",
        required=False,
        min_value=1,
        max_value=1440,
        widget=forms.NumberInput(attrs={**INPUT_ATTRS, "placeholder": "30"}),
    )
    activity_intensity = forms.ChoiceField(
        label="Интенсивность",
        required=False,
        choices=[("", "---------"), *ActivityIntensity.choices],
        widget=forms.Select(attrs=SELECT_ATTRS),
    )

    wellbeing_type = forms.ChoiceField(
        label="Тип самочувствия",
        required=False,
        choices=[("", "---------"), *WellbeingType.choices],
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    symptom_description = forms.CharField(
        label="Описание симптомов",
        required=False,
        widget=forms.Textarea(
            attrs={**INPUT_ATTRS, "placeholder": "Опишите симптомы или жалобу"}
        ),
    )
    severity = forms.ChoiceField(
        label="Выраженность",
        required=False,
        choices=[("", "---------"), *WellbeingEntries._meta.get_field("severity").choices],
        widget=forms.Select(attrs=SELECT_ATTRS),
    )

    weight_kg = forms.DecimalField(
        label="Вес, кг",
        required=False,
        min_value=1,
        max_value=500,
        max_digits=6,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={**INPUT_ATTRS, "step": "0.1", "placeholder": "Например, 74.5"}
        ),
    )
    systolic_bp = forms.IntegerField(
        label="Систолическое давление",
        required=False,
        min_value=50,
        max_value=300,
        widget=forms.NumberInput(attrs={**INPUT_ATTRS, "placeholder": "120"}),
    )
    diastolic_bp = forms.IntegerField(
        label="Диастолическое давление",
        required=False,
        min_value=30,
        max_value=200,
        widget=forms.NumberInput(attrs={**INPUT_ATTRS, "placeholder": "80"}),
    )
    pulse_bpm = forms.IntegerField(
        label="Пульс, уд/мин",
        required=False,
        min_value=20,
        max_value=250,
        widget=forms.NumberInput(attrs={**INPUT_ATTRS, "placeholder": "72"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault(
                "entry_datetime",
                timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            )

    @classmethod
    def get_initial_from_entry(cls, entry):
        entry_datetime = entry.entry_datetime
        if timezone.is_aware(entry_datetime):
            entry_datetime = timezone.localtime(entry_datetime)

        initial = {
            "entry_type": entry.entry_type,
            "entry_datetime": entry_datetime.strftime("%Y-%m-%dT%H:%M"),
            "comment": entry.comment or "",
        }

        if hasattr(entry, "glucose_entry"):
            glucose = entry.glucose_entry
            initial.update(
                {
                    "glucose_value_mmol": glucose.glucose_value_mmol,
                    "glucose_context": glucose.glucose_context or "",
                }
            )

        if hasattr(entry, "therapy_entry"):
            therapy = entry.therapy_entry
            initial.update(
                {
                    "medication_name": therapy.medication_name,
                    "medication_category": therapy.medication_category or "",
                    "dose_amount": therapy.dose_amount,
                    "dose_unit": therapy.dose_unit or "",
                    "administration_method": therapy.administration_method or "",
                }
            )

        if hasattr(entry, "meal_entry"):
            meal = entry.meal_entry
            initial.update(
                {
                    "meal_type": meal.meal_type or "",
                    "meal_description": meal.meal_description or "",
                    "carbohydrates_g": meal.carbohydrates_g,
                    "bread_units": meal.bread_units,
                }
            )

        if hasattr(entry, "activity_entry"):
            activity = entry.activity_entry
            initial.update(
                {
                    "activity_type": activity.activity_type,
                    "activity_duration_min": activity.activity_duration_min,
                    "activity_intensity": activity.activity_intensity or "",
                }
            )

        if hasattr(entry, "wellbeing_entry"):
            wellbeing = entry.wellbeing_entry
            initial.update(
                {
                    "wellbeing_type": wellbeing.wellbeing_type,
                    "symptom_description": wellbeing.symptom_description or "",
                    "severity": wellbeing.severity or "",
                }
            )

        if hasattr(entry, "vital_signs_entry"):
            vital_signs = entry.vital_signs_entry
            initial.update(
                {
                    "weight_kg": vital_signs.weight_kg,
                    "systolic_bp": vital_signs.systolic_bp,
                    "diastolic_bp": vital_signs.diastolic_bp,
                    "pulse_bpm": vital_signs.pulse_bpm,
                }
            )

        return initial

    def clean(self):
        cleaned_data = super().clean()
        entry_type = cleaned_data.get("entry_type")

        if entry_type == MonitoringEntryType.GLUCOSE:
            if cleaned_data.get("glucose_value_mmol") is None:
                self.add_error("glucose_value_mmol", "Укажите уровень глюкозы.")

        if entry_type == MonitoringEntryType.THERAPY:
            if not cleaned_data.get("medication_name"):
                self.add_error("medication_name", "Укажите название препарата.")

        if entry_type == MonitoringEntryType.MEAL:
            meal_fields = (
                "meal_type",
                "meal_description",
                "carbohydrates_g",
                "bread_units",
            )
            if not any(cleaned_data.get(field_name) for field_name in meal_fields):
                raise forms.ValidationError(
                    "Для записи питания заполните хотя бы одно поле."
                )

        if entry_type == MonitoringEntryType.ACTIVITY:
            if not cleaned_data.get("activity_type"):
                self.add_error("activity_type", "Укажите вид активности.")

        if entry_type == MonitoringEntryType.WELLBEING:
            if not cleaned_data.get("wellbeing_type"):
                self.add_error("wellbeing_type", "Укажите тип самочувствия.")

        if entry_type == MonitoringEntryType.VITAL_SIGNS:
            vital_fields = ("weight_kg", "systolic_bp", "diastolic_bp", "pulse_bpm")
            if not any(cleaned_data.get(field_name) for field_name in vital_fields):
                raise forms.ValidationError(
                    "Для дополнительных показателей заполните хотя бы одно поле."
                )

        return cleaned_data

    def _delete_detail_entries(self, entry):
        for model in (
            GlucoseEntries,
            TherapyEntries,
            MealEntries,
            ActivityEntries,
            WellbeingEntries,
            VitalSignsEntries,
        ):
            model.objects.filter(entry=entry).delete()

    def _create_detail_entry(self, entry, entry_type):
        if entry_type == MonitoringEntryType.GLUCOSE:
            GlucoseEntries.objects.create(
                entry=entry,
                glucose_value_mmol=self.cleaned_data["glucose_value_mmol"],
                glucose_context=self.cleaned_data.get("glucose_context") or None,
            )

        if entry_type == MonitoringEntryType.THERAPY:
            TherapyEntries.objects.create(
                entry=entry,
                medication_name=self.cleaned_data["medication_name"],
                medication_category=self.cleaned_data.get("medication_category") or None,
                dose_amount=self.cleaned_data.get("dose_amount"),
                dose_unit=self.cleaned_data.get("dose_unit") or None,
                administration_method=self.cleaned_data.get("administration_method") or None,
            )

        if entry_type == MonitoringEntryType.MEAL:
            MealEntries.objects.create(
                entry=entry,
                meal_type=self.cleaned_data.get("meal_type") or None,
                meal_description=self.cleaned_data.get("meal_description") or None,
                carbohydrates_g=self.cleaned_data.get("carbohydrates_g"),
                bread_units=self.cleaned_data.get("bread_units"),
            )

        if entry_type == MonitoringEntryType.ACTIVITY:
            ActivityEntries.objects.create(
                entry=entry,
                activity_type=self.cleaned_data["activity_type"],
                activity_duration_min=self.cleaned_data.get("activity_duration_min"),
                activity_intensity=self.cleaned_data.get("activity_intensity") or None,
            )

        if entry_type == MonitoringEntryType.WELLBEING:
            WellbeingEntries.objects.create(
                entry=entry,
                wellbeing_type=self.cleaned_data["wellbeing_type"],
                symptom_description=self.cleaned_data.get("symptom_description") or None,
                severity=self.cleaned_data.get("severity") or None,
            )

        if entry_type == MonitoringEntryType.VITAL_SIGNS:
            VitalSignsEntries.objects.create(
                entry=entry,
                weight_kg=self.cleaned_data.get("weight_kg"),
                systolic_bp=self.cleaned_data.get("systolic_bp"),
                diastolic_bp=self.cleaned_data.get("diastolic_bp"),
                pulse_bpm=self.cleaned_data.get("pulse_bpm"),
            )

    def save(self, *, patient, user, entry=None):
        if not hasattr(self, "cleaned_data"):
            raise ValueError("MonitoringEntryForm.save() called before validation.")

        now = timezone.now()
        entry_type = self.cleaned_data["entry_type"]
        with transaction.atomic():
            if entry is None:
                entry = MonitoringEntries.objects.create(
                    patient=patient,
                    entered_by_user=user,
                    entry_type=entry_type,
                    entry_datetime=self.cleaned_data["entry_datetime"],
                    comment=self.cleaned_data.get("comment") or "",
                    created_at=now,
                    updated_at=now,
                )
            else:
                entry.entry_type = entry_type
                entry.entry_datetime = self.cleaned_data["entry_datetime"]
                entry.comment = self.cleaned_data.get("comment") or ""
                entry.entered_by_user = user
                entry.updated_at = now
                entry.save(
                    update_fields=[
                        "entry_type",
                        "entry_datetime",
                        "comment",
                        "entered_by_user",
                        "updated_at",
                    ]
                )
                self._delete_detail_entries(entry)

            self._create_detail_entry(entry, entry_type)

            patient.updated_at = now
            patient.save(update_fields=["updated_at"])

        return entry
