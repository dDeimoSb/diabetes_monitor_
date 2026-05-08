from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils import timezone

from core.forms import DateRangeFilterForm
from core.utils import (
    build_monitoring_analytics,
    get_selected_metric_keys,
    serialize_entry,
)
from monitoring.models import (
    AttachmentRequestStatus,
    CriticalEventStatus,
    CriticalEvents,
    MonitoringEntries,
    MonitoringEntryType,
    Notifications,
    PatientDoctorAttachments,
)
from monitoring.services.critical_events import (
    delete_critical_events_for_entry,
    sync_critical_events_for_entry,
)

from .forms import AttachmentResponseForm, MonitoringEntryForm


PATIENT_CHART_SUMMARY_PER_PAGE = 15
PATIENT_HISTORY_PER_PAGE = 15
PATIENT_CHART_MAX_ENTRIES = 200
PATIENT_CHART_MAX_EVENTS = 100
ENTRY_TYPE_VALUES = {
    "glucose": MonitoringEntryType.GLUCOSE,
    "therapy": MonitoringEntryType.THERAPY,
    "meal": MonitoringEntryType.MEAL,
    "activity": MonitoringEntryType.ACTIVITY,
    "wellbeing": MonitoringEntryType.WELLBEING,
    "vital_signs": MonitoringEntryType.VITAL_SIGNS,
}
AVAILABLE_ENTRY_TYPES = set(ENTRY_TYPE_VALUES.values())


# Доступ пациента
def _require_patient(request):
    if getattr(request.user, "profile_role", "") != "patient":
        messages.warning(request, "Раздел доступен только пациенту.")
        return None
    return request.user.patient_profile


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


def _attachment_queryset(patient):
    return PatientDoctorAttachments.objects.select_related(
        "doctor__user",
        "patient__user",
    ).filter(patient=patient)


def _parse_query_date(query):
    parsed_date = parse_date(query)
    if parsed_date:
        return parsed_date

    try:
        return datetime.strptime(query, "%d.%m.%Y").date()
    except ValueError:
        return None


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


def _get_pagination_query(request, page_param="page"):
    query_params = request.GET.copy()
    query_params.pop(page_param, None)
    return query_params.urlencode()


def _get_active_entry_type(request, fallback=MonitoringEntryType.GLUCOSE):
    active_entry_type = request.POST.get("entry_type") or fallback
    if active_entry_type not in AVAILABLE_ENTRY_TYPES:
        return MonitoringEntryType.GLUCOSE
    return active_entry_type


def _entry_form_context(form, active_entry_type, **extra):
    context = {
        "form": form,
        "entry_type_values": ENTRY_TYPE_VALUES,
        "active_entry_type": active_entry_type,
    }
    context.update(extra)
    return context


@login_required
def dashboard(request):
    patient = _require_patient(request)
    if patient is None:
        return redirect("role_redirect")

    today = timezone.localdate()
    entries_today = _entry_queryset(patient).filter(entry_datetime__date=today)
    recent_entries = [serialize_entry(entry) for entry in entries_today.order_by("-entry_datetime")[:5]]
    if not recent_entries:
        recent_entries = [
            serialize_entry(entry)
            for entry in _entry_queryset(patient).order_by("-entry_datetime")[:5]
        ]

    last_glucose_entry = (
        _entry_queryset(patient)
        .filter(entry_type="Глюкоза")
        .order_by("-entry_datetime")
        .first()
    )
    last_glucose = None
    if last_glucose_entry and hasattr(last_glucose_entry, "glucose_entry"):
        last_glucose = last_glucose_entry.glucose_entry.glucose_value_mmol

    open_events_qs = CriticalEvents.objects.filter(
        entry__patient=patient,
    ).exclude(status=CriticalEventStatus.CLOSED)
    open_events = open_events_qs.select_related("entry").order_by("-detected_at")[:5]

    attachments = _attachment_queryset(patient)
    pending_requests = attachments.filter(status=AttachmentRequestStatus.PENDING).order_by(
        "-created_at",
        "-attachment_id",
    )
    confirmed_attachments = attachments.filter(
        status=AttachmentRequestStatus.CONFIRMED
    ).order_by(
        "doctor__user__last_name",
        "doctor__user__first_name",
        "doctor__doctor_id",
    )

    context = {
        "summary": {
            "entries_today": entries_today.count(),
            "unread_notifications": Notifications.objects.filter(
                recipient_user=request.user,
                is_read=False,
            ).count(),
            "open_events": open_events_qs.count(),
            "last_glucose": last_glucose,
            "pending_attachment_requests": pending_requests.count(),
        },
        "recent_entries": recent_entries,
        "open_events": open_events,
        "pending_attachment_requests": pending_requests[:5],
        "confirmed_attachments": confirmed_attachments[:5],
    }
    return render(request, "patient/dashboard.html", context)


@login_required
def attachments(request):
    patient = _require_patient(request)
    if patient is None:
        return redirect("role_redirect")

    if request.method == "POST":
        form = AttachmentResponseForm(request.POST, patient_profile=patient)
        if form.is_valid():
            attachment = form.attachment
            if form.cleaned_data["action"] == AttachmentResponseForm.ACTION_CONFIRM:
                attachment.status = AttachmentRequestStatus.CONFIRMED
                success_message = (
                    f"Вы подтвердили прикрепление к врачу {attachment.doctor.user.display_name}."
                )
            else:
                attachment.status = AttachmentRequestStatus.REJECTED
                success_message = (
                    f"Вы отклонили запрос от врача {attachment.doctor.user.display_name}."
                )
            attachment.resolved_at = timezone.now()
            attachment.save(update_fields=["status", "resolved_at"])
            messages.success(request, success_message)
            return redirect("patient_attachments")
        if form.expired_attachment is not None:
            form.expired_attachment.status = AttachmentRequestStatus.EXPIRED
            form.expired_attachment.resolved_at = timezone.now()
            form.expired_attachment.save(update_fields=["status", "resolved_at"])
        for error in form.non_field_errors():
            messages.error(request, error)

    incoming_requests = _attachment_queryset(patient).filter(
        status=AttachmentRequestStatus.PENDING
    ).order_by("-created_at", "-attachment_id")
    confirmed_attachments = _attachment_queryset(patient).filter(
        status=AttachmentRequestStatus.CONFIRMED
    ).order_by(
        "doctor__user__last_name",
        "doctor__user__first_name",
        "doctor__doctor_id",
    )
    request_history = _attachment_queryset(patient).exclude(
        status=AttachmentRequestStatus.PENDING
    ).order_by("-created_at", "-attachment_id")

    context = {
        "confirmed_attachments": confirmed_attachments[:100],
        "incoming_requests": incoming_requests[:100],
        "request_history": request_history[:100],
    }
    return render(request, "patient/attachments.html", context)


@login_required
def add_entry(request):
    patient = _require_patient(request)
    if patient is None:
        return redirect("role_redirect")

    form = MonitoringEntryForm(request.POST or None)
    active_entry_type = _get_active_entry_type(request)

    if request.method == "POST" and form.is_valid():
        entry = form.save(patient=patient, user=request.user)
        # Синхронизация предупреждений
        sync_critical_events_for_entry(entry)
        messages.success(request, "Запись самоконтроля добавлена.")
        return redirect(f"{reverse('patient_history')}?entry_id={entry.entry_id}")

    return render(
        request,
        "patient/add_entry.html",
        _entry_form_context(
            form,
            active_entry_type,
            page_title="Добавление записи самоконтроля",
            page_subtitle="Форма внесения данных дневника самоконтроля.",
            submit_label="Сохранить запись",
        ),
    )


@login_required
def edit_entry(request, entry_id):
    patient = _require_patient(request)
    if patient is None:
        return redirect("role_redirect")

    entry = get_object_or_404(_entry_queryset(patient), entry_id=entry_id)
    form = MonitoringEntryForm(
        request.POST or None,
        initial=MonitoringEntryForm.get_initial_from_entry(entry),
    )
    active_entry_type = _get_active_entry_type(request, fallback=entry.entry_type)

    if request.method == "POST" and form.is_valid():
        entry = form.save(patient=patient, user=request.user, entry=entry)
        sync_critical_events_for_entry(entry)
        messages.success(request, "Запись самоконтроля обновлена.")
        return redirect(f"{reverse('patient_history')}?entry_id={entry.entry_id}")

    return render(
        request,
        "patient/add_entry.html",
        _entry_form_context(
            form,
            active_entry_type,
            entry=entry,
            is_edit=True,
            page_title="Редактирование записи",
            page_subtitle="Изменение данных выбранной записи самоконтроля.",
            submit_label="Сохранить изменения",
        ),
    )


@login_required
def delete_entry(request, entry_id):
    patient = _require_patient(request)
    if patient is None:
        return redirect("role_redirect")

    entry = get_object_or_404(_entry_queryset(patient), entry_id=entry_id)
    if request.method == "POST":
        # Очистка предупреждений
        delete_critical_events_for_entry(entry)
        entry.delete()
        patient.updated_at = timezone.now()
        patient.save(update_fields=["updated_at"])
        messages.success(request, "Запись самоконтроля удалена.")
        return redirect("patient_history")

    return render(
        request,
        "patient/delete_entry_confirm.html",
        {
            "entry": serialize_entry(entry),
        },
    )


@login_required
def history(request):
    patient = _require_patient(request)
    if patient is None:
        return redirect("role_redirect")

    queryset = _entry_queryset(patient).order_by("-entry_datetime", "-entry_id")
    start_date, end_date = _get_valid_date_range(request)
    entry_type = request.GET.get("entry_type") or ""
    query = request.GET.get("q") or ""
    highlighted_entry_id = request.GET.get("entry_id") or ""

    if entry_type and entry_type not in AVAILABLE_ENTRY_TYPES:
        messages.warning(request, "Выберите корректный тип записи.")
        entry_type = ""

    if start_date:
        queryset = queryset.filter(entry_datetime__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(entry_datetime__date__lte=end_date)
    if entry_type:
        queryset = queryset.filter(entry_type=entry_type)
    if query:
        query_filter = (
            Q(comment__icontains=query) | Q(entry_type__icontains=query)
        )
        query_date = _parse_query_date(query)
        if query_date:
            query_filter |= Q(entry_datetime__date=query_date)
        queryset = queryset.filter(query_filter)

    entries_page = Paginator(
        queryset,
        PATIENT_HISTORY_PER_PAGE,
    ).get_page(request.GET.get("page"))

    entries = []
    for entry in entries_page.object_list:
        item = serialize_entry(entry)
        item["highlighted"] = str(entry.entry_id) == highlighted_entry_id
        entries.append(item)

    context = {
        "entries": entries,
        "entries_page": entries_page,
        "pagination_query": _get_pagination_query(request),
        "filters": {
            "start_date": _date_to_filter_value(start_date),
            "end_date": _date_to_filter_value(end_date),
            "entry_type": entry_type,
            "q": query,
            "entry_id": highlighted_entry_id,
        },
        "entry_type_choices": MonitoringEntries._meta.get_field("entry_type").choices,
    }
    return render(request, "patient/history.html", context)


@login_required
def charts(request):
    patient = _require_patient(request)
    if patient is None:
        return redirect("role_redirect")

    start_date, end_date = _get_valid_date_range(request)
    entries_queryset = _entry_queryset(patient)
    if start_date:
        entries_queryset = entries_queryset.filter(entry_datetime__date__gte=start_date)
    if end_date:
        entries_queryset = entries_queryset.filter(entry_datetime__date__lte=end_date)
    entries_total = entries_queryset.count()
    if entries_total > PATIENT_CHART_MAX_ENTRIES:
        messages.warning(
            request,
            f"Для графиков показаны последние {PATIENT_CHART_MAX_ENTRIES} записей из {entries_total}. Уточните период, чтобы увидеть более ранние данные.",
        )
    entries = list(
        entries_queryset.order_by("-entry_datetime", "-entry_id")[:PATIENT_CHART_MAX_ENTRIES]
    )
    critical_events_queryset = CriticalEvents.objects.filter(entry__patient=patient)
    if start_date:
        critical_events_queryset = critical_events_queryset.filter(
            entry__entry_datetime__date__gte=start_date,
        )
    if end_date:
        critical_events_queryset = critical_events_queryset.filter(
            entry__entry_datetime__date__lte=end_date,
        )
    critical_events = list(
        critical_events_queryset.select_related("entry").order_by(
            "-detected_at",
            "-critical_event_id",
        )[:PATIENT_CHART_MAX_EVENTS]
    )
    selected_metric_keys = get_selected_metric_keys(request.GET)
    analytics = build_monitoring_analytics(
        entries,
        selected_metric_keys,
        critical_events,
    )
    summary_rows_page = Paginator(
        analytics["summary_rows"],
        PATIENT_CHART_SUMMARY_PER_PAGE,
    ).get_page(request.GET.get("summary_page"))

    return render(
        request,
        "core/charts.html",
        {
            "base_template": "base_patient_app.html",
            "browser_title": "Графики",
            "dashboard_title": "Графики",
            "header_title": "Графики",
            "header_subtitle": "Визуальный анализ записей самоконтроля за выбранный период.",
            "reset_url": request.path,
            "summary_table_title": "Таблица значений",
            "summary_empty_text": "Показателей по выбранным параметрам пока нет.",
            "critical_events_empty_text": "Критических событий за выбранный период нет.",
            "analytics": analytics,
            "summary_rows_page": summary_rows_page,
            "critical_events": critical_events,
            "critical_events_page": None,
            "pagination_queries": {
                "summary": _get_pagination_query(
                    request,
                    page_param="summary_page",
                ),
            },
            "filters": {
                "start_date": _date_to_filter_value(start_date),
                "end_date": _date_to_filter_value(end_date),
            },
        },
    )
