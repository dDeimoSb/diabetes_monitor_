from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from core.forms import DateRangeFilterForm
from core.utils import (
    build_monitoring_analytics,
    get_selected_metric_keys,
    get_safe_redirect_target,
)
from monitoring.models import (
    AttachmentRequestStatus,
    CriticalEventStatus,
    CriticalEvents,
    MonitoringEntries,
    Notifications,
    PatientDoctorAttachments,
    Patients,
)

from .forms import (
    ATTACHMENT_REQUEST_LIFETIME,
    CreateAttachmentRequestForm,
    PatientAttachmentSearchForm,
)


DOCTOR_DASHBOARD_PATIENTS_PER_PAGE = 50
DOCTOR_ATTACH_PATIENT_SEARCH_RESULTS_PER_PAGE = 50
DOCTOR_ATTACHMENT_REQUESTS_PER_PAGE = 25
DOCTOR_PATIENT_ANALYTICS_SUMMARY_PER_PAGE = 15
DOCTOR_PATIENT_ANALYTICS_EVENTS_PER_PAGE = 25
DOCTOR_PATIENT_ANALYTICS_MAX_ENTRIES = 500
DOCTOR_PATIENT_ANALYTICS_MAX_EVENTS = 100
DOCTOR_CRITICAL_EVENTS_PER_PAGE = 25


def _require_doctor(request):
    if getattr(request.user, "profile_role", "") != "doctor":
        messages.warning(request, "Раздел доступен только врачу.")
        return None
    return request.user.doctor_profile


def _patient_queryset(doctor_profile):
    return (
        Patients.objects.select_related("user")
        .filter(
            doctor_attachments__doctor=doctor_profile,
            doctor_attachments__status=AttachmentRequestStatus.CONFIRMED,
        )
        .distinct()
    )


def _attachment_queryset(doctor_profile):
    return PatientDoctorAttachments.objects.select_related(
        "patient__user",
        "doctor__user",
    ).filter(doctor=doctor_profile)


def _entry_queryset(patient):
    return MonitoringEntries.objects.select_related(
        "patient__user",
        "glucose_entry",
        "therapy_entry",
        "meal_entry",
        "activity_entry",
        "wellbeing_entry",
        "vital_signs_entry",
    ).filter(patient=patient)


def _get_attach_patient_search_results(search_form, doctor_profile, page_number):
    search_results_page = Paginator(
        search_form.get_patient_queryset(),
        DOCTOR_ATTACH_PATIENT_SEARCH_RESULTS_PER_PAGE,
    ).get_page(page_number)
    return (
        search_form.get_results(doctor_profile, search_results_page.object_list),
        search_results_page,
    )


def _get_pagination_query(request, page_param="page"):
    query_params = request.GET.copy()
    query_params.pop(page_param, None)
    return query_params.urlencode()


def _date_to_filter_value(value):
    return value.isoformat() if value else ""


def _get_valid_date_range(request):
    form = DateRangeFilterForm(request.GET)
    if form.is_valid():
        return form.cleaned_data.get("start_date"), form.cleaned_data.get("end_date")

    for field_errors in form.errors.values():
        for error in field_errors:
            messages.warning(request, error)
    return None, None


@login_required
def dashboard(request):
    doctor_profile = _require_doctor(request)
    if doctor_profile is None:
        return redirect("role_redirect")

    query = request.GET.get("q") or ""
    patients = _patient_queryset(doctor_profile).order_by(
        "user__last_name",
        "user__first_name",
        "patient_id",
    )
    if query:
        patients = patients.filter(
            Q(user__last_name__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__middle_name__icontains=query)
            | Q(user__email__icontains=query)
        )
    patients_page = Paginator(
        patients,
        DOCTOR_DASHBOARD_PATIENTS_PER_PAGE,
    ).get_page(request.GET.get("page"))

    critical_events_queryset = CriticalEvents.objects.select_related(
        "entry__patient__user"
    ).filter(
        entry__patient__doctor_attachments__doctor=doctor_profile,
        entry__patient__doctor_attachments__status=AttachmentRequestStatus.CONFIRMED,
    )
    critical_events = critical_events_queryset.order_by(
        "-detected_at",
        "-critical_event_id",
    )[:5]

    sent_requests = _attachment_queryset(doctor_profile).order_by("-created_at", "-attachment_id")

    context = {
        "patients": patients_page.object_list,
        "patients_page": patients_page,
        "query": query,
        "recent_attachment_requests": sent_requests[:5],
        "summary": {
            "patients_count": _patient_queryset(doctor_profile).count(),
            "unread_notifications": Notifications.objects.filter(
                recipient_user=request.user,
                is_read=False,
            ).count(),
            "critical_events": critical_events_queryset.count(),
            "pending_attachment_requests": sent_requests.filter(
                status=AttachmentRequestStatus.PENDING
            ).count(),
        },
        "critical_events": critical_events,
    }
    return render(request, "doctor/dashboard.html", context)


@login_required
def attach_patient(request):
    doctor_profile = _require_doctor(request)
    if doctor_profile is None:
        return redirect("role_redirect")

    create_form = CreateAttachmentRequestForm(doctor_profile=doctor_profile)
    if "patient_query" in request.GET:
        search_form = PatientAttachmentSearchForm(request.GET)
    else:
        search_form = PatientAttachmentSearchForm()
    search_results = None
    search_results_page = None
    search_query = ""
    if search_form.is_bound and search_form.is_valid():
        search_query = search_form.cleaned_data["patient_query"]
        search_results, search_results_page = _get_attach_patient_search_results(
            search_form,
            doctor_profile,
            request.GET.get("page"),
        )
    elif search_form.is_bound:
        search_results = []
        search_query = request.GET.get("patient_query") or ""

    if request.method == "POST" and request.POST.get("action") == "cancel_request":
        PatientDoctorAttachments.expire_pending()
        attachment = get_object_or_404(
            _attachment_queryset(doctor_profile),
            attachment_id=request.POST.get("attachment_id"),
        )
        if attachment.status != AttachmentRequestStatus.PENDING:
            messages.warning(request, "Этот запрос уже был обработан и не может быть отменен.")
        else:
            attachment.status = AttachmentRequestStatus.CANCELED
            attachment.resolved_at = timezone.now()
            attachment.save(update_fields=["status", "resolved_at"])
            messages.success(
                request,
                f"Запрос на прикрепление пациента {attachment.patient.user.display_name} отменен.",
            )
        return redirect("doctor_attach_patient")

    if request.method == "POST" and request.POST.get("action") == "create_request":
        PatientDoctorAttachments.expire_pending()
        create_form = CreateAttachmentRequestForm(request.POST, doctor_profile=doctor_profile)
        search_query = (request.POST.get("search_query") or "").strip()
        if search_query:
            search_form = PatientAttachmentSearchForm({"patient_query": search_query})
            if search_form.is_valid():
                search_query = search_form.cleaned_data["patient_query"]
                search_results, search_results_page = _get_attach_patient_search_results(
                    search_form,
                    doctor_profile,
                    request.POST.get("search_page"),
                )
            else:
                search_results = []
        if create_form.is_valid():
            attachment = create_form.save()
            messages.success(
                request,
                f"Запрос на прикрепление пациента {attachment.patient.user.display_name} создан.",
            )
            return redirect("doctor_attach_patient")
        for error in create_form.non_field_errors():
            messages.error(request, error)

    context = {
        "search_form": search_form,
        "create_form": create_form,
        "search_results": search_results,
        "search_results_page": search_results_page,
        "search_query": search_query,
        "request_lifetime_days": ATTACHMENT_REQUEST_LIFETIME.days,
    }
    sent_requests_page = Paginator(
        _attachment_queryset(doctor_profile).order_by("-created_at", "-attachment_id"),
        DOCTOR_ATTACHMENT_REQUESTS_PER_PAGE,
    ).get_page(request.GET.get("requests_page"))
    context.update(
        {
            "sent_requests": sent_requests_page.object_list,
            "sent_requests_page": sent_requests_page,
            "sent_requests_pagination_query": _get_pagination_query(
                request,
                page_param="requests_page",
            ),
        }
    )
    return render(request, "doctor/attach_patient.html", context)


@login_required
def patient_analytics(request, patient_id):
    doctor_profile = _require_doctor(request)
    if doctor_profile is None:
        return redirect("role_redirect")

    patient = get_object_or_404(
        _patient_queryset(doctor_profile),
        patient_id=patient_id,
    )

    start_date, end_date = _get_valid_date_range(request)
    entries = _entry_queryset(patient).order_by("-entry_datetime", "-entry_id")
    if start_date:
        entries = entries.filter(entry_datetime__date__gte=start_date)
    if end_date:
        entries = entries.filter(entry_datetime__date__lte=end_date)
    entries_total = entries.count()
    if entries_total > DOCTOR_PATIENT_ANALYTICS_MAX_ENTRIES:
        messages.warning(
            request,
            f"Для графиков показаны последние {DOCTOR_PATIENT_ANALYTICS_MAX_ENTRIES} записей из {entries_total}. Уточните период, чтобы увидеть более ранние данные.",
        )
    entry_list = list(entries[:DOCTOR_PATIENT_ANALYTICS_MAX_ENTRIES])

    critical_events_queryset = CriticalEvents.objects.filter(entry__patient=patient).select_related("entry")
    if start_date:
        critical_events_queryset = critical_events_queryset.filter(entry__entry_datetime__date__gte=start_date)
    if end_date:
        critical_events_queryset = critical_events_queryset.filter(entry__entry_datetime__date__lte=end_date)
    critical_events_for_analytics = list(
        critical_events_queryset.order_by("-detected_at", "-critical_event_id")[
            :DOCTOR_PATIENT_ANALYTICS_MAX_EVENTS
        ]
    )
    critical_events_page = Paginator(
        critical_events_queryset.order_by("-detected_at", "-critical_event_id"),
        DOCTOR_PATIENT_ANALYTICS_EVENTS_PER_PAGE,
    ).get_page(request.GET.get("events_page"))
    selected_metric_keys = get_selected_metric_keys(request.GET)
    analytics = build_monitoring_analytics(
        entry_list,
        selected_metric_keys,
        critical_events_for_analytics,
    )
    summary_rows_page = Paginator(
        analytics["summary_rows"],
        DOCTOR_PATIENT_ANALYTICS_SUMMARY_PER_PAGE,
    ).get_page(request.GET.get("summary_page"))

    pagination_queries = {
        "summary": _get_pagination_query(request, page_param="summary_page"),
        "events": _get_pagination_query(request, page_param="events_page"),
    }
    patient_subtitle = (
        f"Тип диабета: {patient.diabetes_type}, "
        f"Телефон: {patient.user.phone or '—'}, "
        f"Email: {patient.user.email}"
    )

    context = {
        "base_template": "base_doctor_app.html",
        "browser_title": "Карточка пациента",
        "dashboard_title": "Карточка пациента",
        "header_title": patient.user.display_name,
        "header_subtitle": patient_subtitle,
        "reset_url": request.path,
        "summary_table_title": "Таблица показателей",
        "summary_empty_text": "Показателей по выбранным параметрам за период нет.",
        "critical_events_empty_text": "Критических событий по пациенту нет.",
        "patient": patient,
        "analytics": analytics,
        "summary_rows_page": summary_rows_page,
        "critical_events": critical_events_page.object_list,
        "critical_events_page": critical_events_page,
        "pagination_queries": pagination_queries,
        "filters": {
            "start_date": _date_to_filter_value(start_date),
            "end_date": _date_to_filter_value(end_date),
        },
    }
    return render(request, "core/charts.html", context)


@login_required
def critical_events(request):
    doctor_profile = _require_doctor(request)
    if doctor_profile is None:
        return redirect("role_redirect")

    if request.method == "POST":
        redirect_target = get_safe_redirect_target(
            request,
            request.POST.get("next"),
            reverse("doctor_critical_events"),
        )
        try:
            critical_event_id = int(request.POST.get("critical_event_id") or 0)
        except ValueError:
            messages.error(request, "Не удалось определить критическое событие.")
            return redirect(redirect_target)

        event = get_object_or_404(
            CriticalEvents,
            critical_event_id=critical_event_id,
            entry__patient__doctor_attachments__doctor=doctor_profile,
            entry__patient__doctor_attachments__status=AttachmentRequestStatus.CONFIRMED,
        )
        new_status = request.POST.get("status") or ""
        allowed_statuses = {
            value for value, _label in CriticalEvents._meta.get_field("status").choices
        }
        if new_status not in allowed_statuses:
            messages.error(request, "Выберите корректный статус события.")
        else:
            event.status = new_status
            if new_status == CriticalEventStatus.NEW:
                event.acknowledged_by_user = None
                event.acknowledged_at = None
            else:
                event.acknowledged_by_user = request.user
                event.acknowledged_at = timezone.now()
            event.save(
                update_fields=[
                    "status",
                    "acknowledged_by_user",
                    "acknowledged_at",
                ]
            )
            messages.success(request, "Статус критического события обновлен.")
        return redirect(redirect_target)

    patient_id = request.GET.get("patient") or ""
    status = request.GET.get("status") or ""
    start_date, end_date = _get_valid_date_range(request)
    allowed_statuses = {
        value for value, _label in CriticalEvents._meta.get_field("status").choices
    }

    if status and status not in allowed_statuses:
        messages.warning(request, "Выберите корректный статус события.")
        status = ""

    if patient_id:
        try:
            patient_id_filter = int(patient_id)
        except ValueError:
            messages.warning(request, "Выберите корректного пациента.")
            patient_id = ""
            patient_id_filter = None
    else:
        patient_id_filter = None

    events = CriticalEvents.objects.select_related(
        "entry__patient__user",
        "acknowledged_by_user",
    ).filter(
        entry__patient__doctor_attachments__doctor=doctor_profile,
        entry__patient__doctor_attachments__status=AttachmentRequestStatus.CONFIRMED,
    )

    if patient_id_filter:
        events = events.filter(entry__patient_id=patient_id_filter)
    if status:
        events = events.filter(status=status)
    if start_date:
        events = events.filter(detected_at__date__gte=start_date)
    if end_date:
        events = events.filter(detected_at__date__lte=end_date)

    events_page = Paginator(
        events.order_by("-detected_at", "-critical_event_id"),
        DOCTOR_CRITICAL_EVENTS_PER_PAGE,
    ).get_page(request.GET.get("page"))

    context = {
        "events": events_page.object_list,
        "events_page": events_page,
        "pagination_query": _get_pagination_query(request),
        "patients": _patient_queryset(doctor_profile).order_by(
            "user__last_name",
            "user__first_name",
        ),
        "status_choices": CriticalEvents._meta.get_field("status").choices,
        "filters": {
            "patient": patient_id,
            "status": status,
            "start_date": _date_to_filter_value(start_date),
            "end_date": _date_to_filter_value(end_date),
        },
    }
    return render(request, "doctor/critical_events.html", context)
