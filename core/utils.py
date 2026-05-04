from decimal import Decimal

from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def get_user_role(user):
    return getattr(user, "profile_role", "")


def get_base_template(user):
    role = get_user_role(user)
    if role == "doctor":
        return "base_doctor_app.html"
    if role == "patient":
        return "base_patient_app.html"
    return "base_public.html"


def get_dashboard_url(user):
    role = get_user_role(user)
    if role == "doctor":
        return reverse("doctor_dashboard")
    if role == "patient":
        return reverse("patient_dashboard")
    return reverse("home")


def get_safe_redirect_target(request, target, fallback_url):
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return fallback_url


def format_value(value):
    if value in (None, ""):
        return ""
    if isinstance(value, Decimal):
        normalized = value.normalize()
        value = normalized if normalized == normalized.to_integral() else normalized
    return str(value).replace(".", ",")


def describe_entry(entry):
    parts = []

    if hasattr(entry, "glucose_entry"):
        glucose = entry.glucose_entry
        parts.append(f"{format_value(glucose.glucose_value_mmol)} ммоль/л")
        if glucose.glucose_context:
            parts.append(glucose.get_glucose_context_display())

    if hasattr(entry, "therapy_entry"):
        therapy = entry.therapy_entry
        parts.append(therapy.medication_name)
        dose_bits = [format_value(therapy.dose_amount), therapy.dose_unit]
        dose = " ".join(bit for bit in dose_bits if bit)
        if dose:
            parts.append(dose)
        if therapy.administration_method:
            parts.append(therapy.administration_method)

    if hasattr(entry, "meal_entry"):
        meal = entry.meal_entry
        if meal.meal_type:
            parts.append(meal.get_meal_type_display())
        if meal.meal_description:
            parts.append(meal.meal_description)
        if meal.bread_units:
            parts.append(f"{format_value(meal.bread_units)} ХЕ")
        if meal.carbohydrates_g:
            parts.append(f"{format_value(meal.carbohydrates_g)} г углеводов")

    if hasattr(entry, "activity_entry"):
        activity = entry.activity_entry
        parts.append(activity.activity_type)
        if activity.activity_duration_min:
            parts.append(f"{activity.activity_duration_min} мин")
        if activity.activity_intensity:
            parts.append(activity.get_activity_intensity_display())

    if hasattr(entry, "wellbeing_entry"):
        wellbeing = entry.wellbeing_entry
        parts.append(wellbeing.get_wellbeing_type_display())
        if wellbeing.severity:
            parts.append(wellbeing.get_severity_display())
        if wellbeing.symptom_description:
            parts.append(wellbeing.symptom_description)

    if hasattr(entry, "vital_signs_entry"):
        vital = entry.vital_signs_entry
        if vital.weight_kg:
            parts.append(f"Вес {format_value(vital.weight_kg)} кг")
        if vital.systolic_bp and vital.diastolic_bp:
            parts.append(f"АД {vital.systolic_bp}/{vital.diastolic_bp}")
        if vital.pulse_bpm:
            parts.append(f"Пульс {vital.pulse_bpm}")

    if entry.comment:
        parts.append(f"Комментарий: {entry.comment}")

    return "; ".join(part for part in parts if part) or "Без дополнительных данных"


def serialize_entry(entry):
    return {
        "id": entry.entry_id,
        "entry": entry,
        "patient": entry.patient,
        "patient_name": entry.patient.user.display_name,
        "entry_type": entry.get_entry_type_display(),
        "entry_datetime": entry.entry_datetime,
        "detail": describe_entry(entry),
        "comment": entry.comment or "",
    }


ANALYTICS_METRICS = {
    "glucose": {
        "label": "Глюкоза",
        "unit": "ммоль/л",
    },
    "systolic_bp": {
        "label": "Систолическое АД",
        "unit": "мм рт. ст.",
    },
    "diastolic_bp": {
        "label": "Диастолическое АД",
        "unit": "мм рт. ст.",
    },
    "pulse": {
        "label": "Пульс",
        "unit": "уд/мин",
    },
    "weight": {
        "label": "Вес",
        "unit": "кг",
    },
    "bread_units": {
        "label": "Хлебные единицы",
        "unit": "ХЕ",
    },
    "carbohydrates": {
        "label": "Углеводы",
        "unit": "г",
    },
    "activity_duration": {
        "label": "Активность",
        "unit": "мин",
    },
}

DEFAULT_ANALYTICS_METRICS = ("glucose",)


def get_metric_options(selected_metric_keys=None):
    selected_metric_keys = set(selected_metric_keys or ())
    return [
        {
            "key": key,
            "label": config["label"],
            "unit": config["unit"],
            "selected": key in selected_metric_keys,
        }
        for key, config in ANALYTICS_METRICS.items()
    ]


def get_selected_metric_keys(params):
    selected = [
        key for key in params.getlist("metrics")
        if key in ANALYTICS_METRICS
    ]
    return tuple(selected or DEFAULT_ANALYTICS_METRICS)


def _metric_value(entry, metric_key):
    if metric_key == "glucose" and hasattr(entry, "glucose_entry"):
        return entry.glucose_entry.glucose_value_mmol

    if metric_key == "systolic_bp" and hasattr(entry, "vital_signs_entry"):
        return entry.vital_signs_entry.systolic_bp

    if metric_key == "diastolic_bp" and hasattr(entry, "vital_signs_entry"):
        return entry.vital_signs_entry.diastolic_bp

    if metric_key == "pulse" and hasattr(entry, "vital_signs_entry"):
        return entry.vital_signs_entry.pulse_bpm

    if metric_key == "weight" and hasattr(entry, "vital_signs_entry"):
        return entry.vital_signs_entry.weight_kg

    if metric_key == "bread_units" and hasattr(entry, "meal_entry"):
        return entry.meal_entry.bread_units

    if metric_key == "carbohydrates" and hasattr(entry, "meal_entry"):
        return entry.meal_entry.carbohydrates_g

    if metric_key == "activity_duration" and hasattr(entry, "activity_entry"):
        return entry.activity_entry.activity_duration_min

    return None


def build_monitoring_analytics(entries, selected_metric_keys, critical_events=()):
    entries = sorted(entries, key=lambda entry: entry.entry_datetime)
    critical_entry_ids = {
        event.entry_id
        for event in critical_events
        if getattr(event, "entry_id", None)
    }

    chart_series = []
    for metric_key in selected_metric_keys:
        config = ANALYTICS_METRICS[metric_key]
        points = []
        for entry in entries:
            value = _metric_value(entry, metric_key)
            if value in (None, ""):
                continue
            points.append(
                {
                    "entry_id": entry.entry_id,
                    "date_label": entry.entry_datetime.strftime("%d.%m.%Y %H:%M"),
                    "value_float": float(value),
                    "value_display": format_value(value),
                    "is_critical": entry.entry_id in critical_entry_ids,
                }
            )

        chart_series.append(
            {
                "key": metric_key,
                "label": config["label"],
                "unit": config["unit"],
                "points": points,
                "has_line": len(points) > 1,
                "has_data": bool(points),
            }
        )

    summary_rows = []
    for entry in sorted(entries, key=lambda item: item.entry_datetime, reverse=True):
        values = []
        has_metric_value = False
        for metric_key in selected_metric_keys:
            value = _metric_value(entry, metric_key)
            if value not in (None, ""):
                has_metric_value = True
            config = ANALYTICS_METRICS[metric_key]
            values.append(
                {
                    "key": metric_key,
                    "label": config["label"],
                    "unit": config["unit"],
                    "value": format_value(value) or "—",
                }
            )

        if has_metric_value:
            summary_rows.append(
                {
                    "entry": serialize_entry(entry),
                    "is_critical": entry.entry_id in critical_entry_ids,
                    "values": values,
                }
            )

    return {
        "metric_options": get_metric_options(selected_metric_keys),
        "selected_metric_keys": selected_metric_keys,
        "selected_metric_labels": [
            ANALYTICS_METRICS[key]["label"] for key in selected_metric_keys
        ],
        "chart_series": chart_series,
        "summary_rows": summary_rows,
        "critical_entry_ids": critical_entry_ids,
    }


def get_notification_target_url(user, notification):
    critical_event = notification.critical_event
    if not critical_event or not critical_event.entry_id:
        return ""

    patient = critical_event.entry.patient
    role = get_user_role(user)
    if role == "doctor":
        return reverse("doctor_patient_analytics", args=[patient.patient_id])

    return f"{reverse('patient_history')}?entry_id={critical_event.entry_id}"
