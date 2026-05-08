import re

from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction

from monitoring.models import DiabetesType, Patients

from .models import User

INPUT_ATTRS = {"class": "input-text"}
SELECT_ATTRS = {"class": "input-select"}


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Электронная почта",
        widget=forms.EmailInput(
            attrs={
                **INPUT_ATTRS,
                "placeholder": "name@example.com",
                "autocomplete": "email",
            }
        ),
    )
    password = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                **INPUT_ATTRS,
                "placeholder": "Введите пароль",
                "autocomplete": "current-password",
            }
        ),
    )


class RegistrationForm(forms.Form):
    EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    GENDER_CHOICES = [("", "---------"), *User.Gender.choices]
    DIABETES_TYPE_CHOICES = DiabetesType.choices

    last_name = forms.CharField(
        label="Фамилия *",
        max_length=150,
        widget=forms.TextInput(
            attrs={**INPUT_ATTRS, "placeholder": "Иванов", "autocomplete": "family-name"}
        ),
    )
    first_name = forms.CharField(
        label="Имя *",
        max_length=150,
        widget=forms.TextInput(
            attrs={**INPUT_ATTRS, "placeholder": "Иван", "autocomplete": "given-name"}
        ),
    )
    middle_name = forms.CharField(
        label="Отчество",
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                **INPUT_ATTRS,
                "placeholder": "Иванович",
                "autocomplete": "additional-name",
            }
        ),
    )
    email = forms.EmailField(
        label="Электронная почта *",
        widget=forms.EmailInput(
            attrs={**INPUT_ATTRS, "placeholder": "name@example.com", "autocomplete": "email"}
        ),
    )
    phone = forms.CharField(
        label="Телефон",
        max_length=25,
        required=False,
        widget=forms.TextInput(
            attrs={**INPUT_ATTRS, "placeholder": "+79991234567", "autocomplete": "tel"}
        ),
    )
    birth_date = forms.DateField(
        label="Дата рождения",
        required=False,
        widget=forms.DateInput(attrs={**INPUT_ATTRS, "type": "date"}),
    )
    gender = forms.ChoiceField(
        label="Пол",
        required=False,
        choices=GENDER_CHOICES,
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    diabetes_type = forms.ChoiceField(
        label="Тип диабета *",
        choices=DIABETES_TYPE_CHOICES,
        widget=forms.Select(attrs=SELECT_ATTRS),
    )
    password1 = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                **INPUT_ATTRS,
                "placeholder": "Не менее 8 символов",
                "autocomplete": "new-password",
            }
        ),
        min_length=8,
    )
    password2 = forms.CharField(
        label="Подтверждение пароля",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                **INPUT_ATTRS,
                "placeholder": "Повторите пароль",
                "autocomplete": "new-password",
            }
        ),
    )

    # Проверка email
    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if not self.EMAIL_PATTERN.fullmatch(email):
            raise ValidationError(
                "Введите корректный адрес электронной почты в формате name@example.com."
            )
        try:
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError(
                    "Пользователь с такой электронной почтой уже зарегистрирован."
                )
        except DatabaseError as exc:
            raise ValidationError(
                "Не удалось проверить адрес электронной почты. Попробуйте ещё раз позже."
            ) from exc
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            return ""

        normalized_phone = re.sub(r"[\s()-]", "", phone)
        max_digits = self.fields["phone"].max_length - 1
        phone_pattern = rf"\+[1-9]\d{{0,{max_digits - 1}}}"

        if not re.fullmatch(phone_pattern, normalized_phone):
            raise ValidationError(
                "Введите телефон в формате +79991234567."
            )

        return normalized_phone

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Пароли не совпадают.")

        if password1:
            try:
                password_validation.validate_password(password1)
            except ValidationError as exc:
                self.add_error("password1", exc)

        return cleaned_data

    # Создание пациента
    def save(self):
        with transaction.atomic():
            user = User.objects.create_user(
                email=self.cleaned_data["email"],
                password=self.cleaned_data["password1"],
                last_name=self.cleaned_data["last_name"],
                first_name=self.cleaned_data["first_name"],
                middle_name=self.cleaned_data.get("middle_name") or None,
                phone=self.cleaned_data.get("phone") or None,
                gender=self.cleaned_data.get("gender") or None,
                birth_date=self.cleaned_data.get("birth_date"),
                is_active=True,
            )

            Patients.objects.create(
                user=user,
                diabetes_type=self.cleaned_data["diabetes_type"],
            )

        return user
