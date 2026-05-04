from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.db import DatabaseError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import LoginForm, RegistrationForm


def login_view(request):
    if request.user.is_authenticated:
        messages.info(request, "Вы уже вошли в систему.")
        return redirect("home")

    form = LoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        password = form.cleaned_data["password"]

        try:
            user = authenticate(request, email=email, password=password)
        except DatabaseError:
            user = None
            form.add_error(
                None,
                "Не удалось выполнить вход из-за ошибки базы данных. Попробуйте позже.",
            )
        else:
            if not user:
                form.add_error(None, "Неверная электронная почта или пароль.")

        if not form.non_field_errors():
            auth_login(request, user)
            request.session.set_expiry(60 * 60 * 24 * 14)
            messages.success(request, "Вход выполнен.")
            return redirect("role_redirect")

    return render(request, "accounts/login.html", {"form": form})


def register_view(request):
    if request.user.is_authenticated:
        messages.info(
            request,
            "Чтобы зарегистрировать новый аккаунт, сначала выйдите из аккаунта.",
        )
        return redirect("home")

    form = RegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            user = form.save()
        except DatabaseError:
            form.add_error(
                None,
                "Не удалось создать учётную запись. Проверьте соединение с базой данных и попробуйте ещё раз.",
            )
        else:
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            request.session.set_expiry(60 * 60 * 24 * 14)
            messages.success(request, "Регистрация завершена. Аккаунт пациента создан.")
            return redirect("role_redirect")

    return render(request, "accounts/register.html", {"form": form})


@require_POST
def logout_view(request):
    auth_logout(request)
    messages.success(request, "Вы вышли из системы.")
    return redirect("home")
