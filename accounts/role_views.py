from django.contrib import messages
from django.shortcuts import redirect

from core.utils import get_dashboard_url, get_user_role


def role_redirect_view(request):
    if not request.user.is_authenticated:
        messages.info(request, "Сначала выполните вход.")
        return redirect("login")

    role = get_user_role(request.user)
    if role in {"doctor", "patient"}:
        return redirect(get_dashboard_url(request.user))

    messages.warning(
        request,
        "Для учётной записи пока не определён профиль врача или пациента.",
    )
    return redirect("home")
