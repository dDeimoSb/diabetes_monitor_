from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.utils import timezone

from monitoring.models import AttachmentRequestStatus, DiabetesType, Patients


SELECT_ATTRS = {"class": "input-select"}
INPUT_ATTRS = {"class": "input-text"}

User = get_user_model()


class DateRangeFilterForm(forms.Form):
    start_date = forms.DateField(
        label="Дата начала",
        required=False,
        widget=forms.DateInput(attrs={**INPUT_ATTRS, "type": "date"}),
    )
    end_date = forms.DateField(
        label="Дата окончания",
        required=False,
        widget=forms.DateInput(attrs={**INPUT_ATTRS, "type": "date"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and start_date > end_date:
            self.add_error("end_date", "Дата окончания должна быть не раньше даты начала.")

        return cleaned_data


class PrediabetesRiskForm(forms.Form):
    AGE_CHOICES = (
        (0, "Моложе 45 лет"),
        (2, "45 - 54 года"),
        (3, "55 - 64 года"),
        (4, "65 лет и старше"),
    )
    GENDER_CHOICES = (
        ("female", "Женский"),
        ("male", "Мужской"),
    )
    ACTIVITY_CHOICES = (
        (0, "Да"),
        (2, "Нет"),
    )
    NUTRITION_CHOICES = (
        (0, "Каждый день"),
        (1, "Не каждый день"),
    )
    BP_CHOICES = (
        (0, "Нет"),
        (2, "Да"),
    )
    GLUCOSE_HISTORY_CHOICES = (
        (0, "Нет"),
        (5, "Да"),
    )
    FAMILY_HISTORY_CHOICES = (
        (0, "Нет"),
        (3, "Да, у бабушки, дедушки, тёти, дяди или двоюродных родственников"),
        (5, "Да, у родителей, родных братьев, сестёр или детей"),
    )

    age_score = forms.TypedChoiceField(
        label="Возраст",
        choices=AGE_CHOICES,
        coerce=int,
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    gender = forms.ChoiceField(
        label="Пол",
        choices=GENDER_CHOICES,
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    height_cm = forms.DecimalField(
        label="Рост, см",
        min_value=100,
        max_value=250,
        decimal_places=1,
        max_digits=5,
        widget=forms.NumberInput(
            attrs={**INPUT_ATTRS, "placeholder": "Например, 168", "step": "0.1"}
        ),
    )
    weight_kg = forms.DecimalField(
        label="Вес, кг",
        min_value=30,
        max_value=300,
        decimal_places=1,
        max_digits=5,
        widget=forms.NumberInput(
            attrs={**INPUT_ATTRS, "placeholder": "Например, 74", "step": "0.1"}
        ),
    )
    waist_cm = forms.IntegerField(
        label="Окружность талии, см",
        min_value=50,
        max_value=200,
        widget=forms.NumberInput(
            attrs={**INPUT_ATTRS, "placeholder": "Например, 92"}
        ),
        help_text="Измеряется на уровне пупка без натяжения ленты.",
    )
    nutrition_score = forms.TypedChoiceField(
        label="Как часто Вы едите овощи, фрукты, ягоды?",
        choices=NUTRITION_CHOICES,
        coerce=int,
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    activity_score = forms.TypedChoiceField(
        label="Делаете ли Вы физические упражнения по 30 минут каждый день или 3 часа в течение недели?",
        choices=ACTIVITY_CHOICES,
        coerce=int,
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    bp_score = forms.TypedChoiceField(
        label="Принимали ли Вы когда-либо регулярно лекарства для снижения артериального давления?",
        choices=BP_CHOICES,
        coerce=int,
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    glucose_history_score = forms.TypedChoiceField(
        label="Обнаруживали ли у Вас когда-либо уровень глюкозы (сахара) крови выше нормы?",
        choices=GLUCOSE_HISTORY_CHOICES,
        coerce=int,
        widget=forms.Select(attrs=SELECT_ATTRS),
        help_text="Например, при профосмотре, диспансеризации, во время болезни или беременности.",
    )
    family_history_score = forms.TypedChoiceField(
        label="Был ли у Ваших родственников сахарный диабет 1 или 2 типа?",
        choices=FAMILY_HISTORY_CHOICES,
        coerce=int,
        widget=forms.Select(attrs=SELECT_ATTRS),
    )

    def get_result(self):
        bmi = self._calculate_bmi()
        bmi_score, bmi_label = self._get_bmi_score(bmi)
        waist_score = self._get_waist_score(
            self.cleaned_data["gender"],
            self.cleaned_data["waist_cm"],
        )
        score = (
            self.cleaned_data["age_score"]
            + bmi_score
            + waist_score
            + self.cleaned_data["activity_score"]
            + self.cleaned_data["nutrition_score"]
            + self.cleaned_data["bp_score"]
            + self.cleaned_data["glucose_history_score"]
            + self.cleaned_data["family_history_score"]
        )

        band = self._get_band(score)
        return {
            "score": score,
            "bmi": round(bmi, 1),
            "bmi_label": bmi_label,
            "category": band["category"],
            "band": band["band"],
            "level_class": band["level_class"],
            "summary": band["summary"],
            "recommendations": band["recommendations"],
        }

    def _calculate_bmi(self):
        height_m = float(self.cleaned_data["height_cm"]) / 100
        weight_kg = float(self.cleaned_data["weight_kg"])
        return weight_kg / (height_m * height_m)

    def _get_bmi_score(self, bmi):
        if bmi < 25:
            return 0, "ИМТ в целевом диапазоне"
        if bmi < 30:
            return 1, "Есть избыточная масса тела"
        return 3, "ИМТ соответствует ожирению"

    def _get_waist_score(self, gender, waist_cm):
        if gender == "male":
            if waist_cm < 94:
                return 0
            if waist_cm <= 102:
                return 3
            return 4

        if waist_cm < 80:
            return 0
        if waist_cm <= 88:
            return 3
        return 4

    def _get_band(self, score):
        if score < 7:
            return {
                "band": "Риск развития сахарного диабета в течение 10 лет: Низкий риск, 1 из 100, или 1%.",
                "category": "Низкий риск",
                "level_class": "low",
                "summary": "У Вас хорошее здоровье и Вы должны продолжать вести здоровый образ жизни. ",
                "recommendations": [
                    "Продолжайте поддерживать регулярную физическую активность и сбалансированное питание.",
                    "Контролируйте массу тела и окружность талии в динамике.",
                    "Проходите профилактические обследования в сроки, которые рекомендует врач.",
                ],
            }
        if score < 12:
            return {
                "band": "Риск развития сахарного диабета в течение 10 лет: Слегка повышенный риск, 1 из 25, или 4%.",
                "category": "Низкий риск",
                "level_class": "low",
                "summary": "У Вас хорошее здоровье и Вы должны продолжать вести здоровый образ жизни. ",
                "recommendations": [
                    "Продолжайте поддерживать регулярную физическую активность и сбалансированное питание.",
                    "Контролируйте массу тела и окружность талии в динамике.",
                    "Проходите профилактические обследования в сроки, которые рекомендует врач.",
                ],
            }
        if score < 15:
            return {
                "band": "Риск развития сахарного диабета в течение 10 лет: Умеренный риск, 1 из 6, или 17%.",
                "category": "Умеренный риск",
                "level_class": "moderate",
                "summary": "Возможно, у вас предиабет. Вы должны посоветоваться со своим врачом, как Вам "
                "следует изменить образ жизни.",
                "recommendations": [
                    "Запишитесь на плановую консультацию терапевта или эндокринолога.",
                    "Обсудите обследование: глюкоза плазмы натощак, HbA1c или другие анализы по назначению врача.",
                    "Сфокусируйтесь на снижении массы тела при её избытке и на регулярной физической нагрузке.",
                ],
            }
        if score < 21:
            return {
                "band": "Риск развития сахарного диабета в течение 10 лет: Высокий риск, 1 из 3, или 33%.",
                "category": "Высокий риск",
                "level_class": "high",
                "summary": "Возможно, у Вас предиабет или сахарный диабет 2 типа. "
                "Не исключено, что Вам понадобятся и лекарства для снижения уровня глюкозы (сахара) в крови.",
                "recommendations": [
                    "В ближайшее время обратитесь к врачу для очной оценки факторов риска.",
                    "Не откладывайте лабораторный контроль глюкозы и HbA1c, если врач сочтёт это необходимым.",
                    "Начните отслеживать питание, вес, окружность талии и уровень активности.",
                ],
            }
        return {
            "band": "Риск развития сахарного диабета в течение 10 лет: Очень высокий, 1 из 2, или 50%.",
            "category": "Очень высокий риск",
            "level_class": "high",
            "summary": "По всей вероятности, у Вас есть сахарный диабет 2 типа. Вы должны проверить уровень глюкозы "
            "(сахара) в крови и постараться его нормализовать. Вы должны изменить свой образ жизни и Вам понадобятся и "
            "лекарства для контроля за уровнем глюкозы (сахара) в крови.",
            "recommendations": [
                "Запланируйте консультацию врача как можно скорее.",
                "До консультации постарайтесь избегать длительных периодов без движения и чрезмерного потребления сахара "
                "и сладких напитков.",
            ],
        }


class UserProfileForm(forms.ModelForm):
    specialty = forms.CharField(
        label="Специальность",
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={**INPUT_ATTRS, "placeholder": "Например, эндокринолог"}
        ),
    )
    diabetes_type = forms.ChoiceField(
        label="Тип диабета",
        choices=DiabetesType.choices,
        required=False,
        widget=forms.Select(attrs=SELECT_ATTRS),
    )

    class Meta:
        model = User
        fields = (
            "last_name",
            "first_name",
            "middle_name",
            "email",
            "phone",
            "birth_date",
            "gender",
        )
        widgets = {
            "last_name": forms.TextInput(
                attrs={**INPUT_ATTRS, "placeholder": "Иванов", "autocomplete": "family-name"}
            ),
            "first_name": forms.TextInput(
                attrs={**INPUT_ATTRS, "placeholder": "Иван", "autocomplete": "given-name"}
            ),
            "middle_name": forms.TextInput(
                attrs={
                    **INPUT_ATTRS,
                    "placeholder": "Иванович",
                    "autocomplete": "additional-name",
                }
            ),
            "email": forms.EmailInput(
                attrs={**INPUT_ATTRS, "placeholder": "name@example.com", "autocomplete": "email"}
            ),
            "phone": forms.TextInput(
                attrs={**INPUT_ATTRS, "placeholder": "+79991234567", "autocomplete": "tel"}
            ),
            "birth_date": forms.DateInput(attrs={**INPUT_ATTRS, "type": "date"}),
            "gender": forms.Select(attrs=SELECT_ATTRS),
        }
        labels = {
            "last_name": "Фамилия",
            "first_name": "Имя",
            "middle_name": "Отчество",
            "email": "Электронная почта",
            "phone": "Телефон",
            "birth_date": "Дата рождения",
            "gender": "Пол",
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user or kwargs.get("instance")
        super().__init__(*args, **kwargs)
        self.fields["gender"].required = False
        self.fields["gender"].choices = [("", "---------"), *User.Gender.choices]

        role = getattr(self.user, "profile_role", "")
        if role == "doctor":
            self.initial["specialty"] = self.user.doctor_profile.specialty
            self.fields.pop("diabetes_type")
        elif role == "patient":
            self.initial["diabetes_type"] = self.user.patient_profile.diabetes_type
            self.fields.pop("specialty")
        else:
            self.fields.pop("specialty")
            self.fields.pop("diabetes_type")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existing = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if existing.exists():
            raise ValidationError("Пользователь с такой электронной почтой уже существует.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        role = getattr(self.user, "profile_role", "")

        if role == "doctor" and not cleaned_data.get("specialty"):
            self.add_error("specialty", "Укажите специальность.")

        if role == "patient" and not cleaned_data.get("diabetes_type"):
            self.add_error("diabetes_type", "Укажите тип диабета.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)
        role = getattr(self.user, "profile_role", "")

        if role == "doctor":
            doctor_profile = user.doctor_profile
            doctor_profile.specialty = self.cleaned_data["specialty"]
            doctor_profile.updated_at = timezone.now()
            if commit:
                doctor_profile.save(update_fields=["specialty", "updated_at"])

        if role == "patient":
            patient_profile = user.patient_profile
            patient_profile.diabetes_type = self.cleaned_data["diabetes_type"]
            patient_profile.updated_at = timezone.now()
            if commit:
                patient_profile.save(update_fields=["diabetes_type", "updated_at"])

        return user


class PasswordUpdateForm(forms.Form):
    current_password = forms.CharField(
        label="Текущий пароль",
        strip=False,
        required=False,
        widget=forms.PasswordInput(
            attrs={**INPUT_ATTRS, "placeholder": "Введите текущий пароль"}
        ),
    )
    new_password1 = forms.CharField(
        label="Новый пароль",
        strip=False,
        required=False,
        widget=forms.PasswordInput(
            attrs={**INPUT_ATTRS, "placeholder": "Не менее 8 символов"}
        ),
    )
    new_password2 = forms.CharField(
        label="Подтверждение нового пароля",
        strip=False,
        required=False,
        widget=forms.PasswordInput(
            attrs={**INPUT_ATTRS, "placeholder": "Повторите новый пароль"}
        ),
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        fields = ("current_password", "new_password1", "new_password2")

        if not any(cleaned_data.get(field_name) for field_name in fields):
            return cleaned_data

        for field_name in fields:
            if not cleaned_data.get(field_name):
                self.add_error(field_name, "Заполните это поле.")

        if self.errors:
            return cleaned_data

        if not self.user.check_password(cleaned_data["current_password"]):
            self.add_error("current_password", "Текущий пароль указан неверно.")

        if cleaned_data["new_password1"] != cleaned_data["new_password2"]:
            self.add_error("new_password2", "Пароли не совпадают.")

        if self.errors:
            return cleaned_data

        try:
            password_validation.validate_password(cleaned_data["new_password1"], self.user)
        except ValidationError as exc:
            self.add_error("new_password1", exc)

        return cleaned_data

    def has_change_requested(self):
        if not hasattr(self, "cleaned_data"):
            return False
        return any(
            self.cleaned_data.get(field_name)
            for field_name in ("current_password", "new_password1", "new_password2")
        )

    def save(self):
        self.user.set_password(self.cleaned_data["new_password1"])
        self.user.save(update_fields=["password"])
        return self.user


class DataExportForm(forms.Form):
    EXPORT_FORMAT_CHOICES = (
        ("csv", "CSV"),
        ("excel", "XLSX"),
    )

    start_date = forms.DateField(
        label="Дата начала",
        widget=forms.DateInput(attrs={**INPUT_ATTRS, "type": "date"}),
    )
    end_date = forms.DateField(
        label="Дата окончания",
        widget=forms.DateInput(attrs={**INPUT_ATTRS, "type": "date"}),
    )
    export_format = forms.ChoiceField(
        label="Формат файла",
        choices=EXPORT_FORMAT_CHOICES,
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    patient_id = forms.IntegerField(
        label="Пациент",
        required=False,
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        if getattr(user, "profile_role", "") != "doctor":
            self.fields.pop("patient_id")

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        role = getattr(self.user, "profile_role", "")

        if start_date and end_date and start_date > end_date:
            self.add_error("end_date", "Дата окончания должна быть не раньше даты начала.")

        if role == "doctor":
            patient_id = cleaned_data.get("patient_id")
            doctor_profile = getattr(self.user, "doctor_profile", None)
            if not patient_id:
                self.add_error("patient_id", "Выберите пациента для экспорта.")
                return cleaned_data

            patient = (
                Patients.objects.select_related("user")
                .filter(
                    patient_id=patient_id,
                    doctor_attachments__doctor=doctor_profile,
                    doctor_attachments__status=AttachmentRequestStatus.CONFIRMED,
                )
                .distinct()
                .first()
            )
            if patient is None:
                self.add_error("patient_id", "Выберите пациента из списка найденных.")
                return cleaned_data

            cleaned_data["patient"] = patient

        return cleaned_data
