import csv
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone

from monitoring.models import AttachmentRequestStatus, MonitoringEntries, Patients

from core.utils import get_user_role, serialize_entry


EXPORT_HEADERS = ("Дата и время", "Пациент", "Тип записи", "Детали", "Комментарий")
FORMULA_PREFIXES = ("=", "+", "-", "@")


def get_export_entries(user, cleaned_data):
    queryset = (
        MonitoringEntries.objects.select_related(
            "patient__user",
            "entered_by_user",
            "glucose_entry",
            "therapy_entry",
            "meal_entry",
            "activity_entry",
            "wellbeing_entry",
            "vital_signs_entry",
        )
        .filter(
            entry_datetime__date__gte=cleaned_data["start_date"],
            entry_datetime__date__lte=cleaned_data["end_date"],
        )
        .order_by("-entry_datetime", "-entry_id")
    )

    role = get_user_role(user)
    if role == "doctor":
        return queryset.filter(patient=cleaned_data["patient"])
    if role == "patient" and hasattr(user, "patient_profile"):
        return queryset.filter(patient=user.patient_profile)
    return queryset.none()


def get_export_patient_search_results(user, query):
    doctor_profile = getattr(user, "doctor_profile", None)
    if doctor_profile is None or not query:
        return None

    queryset = (
        Patients.objects.select_related("user")
        .filter(
            doctor_attachments__doctor=doctor_profile,
            doctor_attachments__status=AttachmentRequestStatus.CONFIRMED,
        )
        .distinct()
    )

    if "@" in query:
        queryset = queryset.filter(user__email__icontains=query)
    else:
        for term in [item for item in query.split() if item]:
            queryset = queryset.filter(
                Q(user__last_name__icontains=term)
                | Q(user__first_name__icontains=term)
                | Q(user__middle_name__icontains=term)
                | Q(user__email__icontains=term)
            )

    return queryset.order_by("user__last_name", "user__first_name", "patient_id")[:50]


def build_export_rows(entries):
    rows = []
    for entry in entries:
        item = serialize_entry(entry)
        entry_datetime = (
            timezone.localtime(entry.entry_datetime)
            if timezone.is_aware(entry.entry_datetime)
            else entry.entry_datetime
        )
        rows.append(
            {
                "date": entry_datetime.strftime("%d.%m.%Y %H:%M"),
                "patient": item["patient_name"],
                "entry_type": item["entry_type"],
                "detail": item["detail"],
                "comment": item["comment"],
            }
        )
    return rows


def _safe_spreadsheet_value(value):
    value = "" if value is None else str(value)
    stripped = value.lstrip()
    if stripped.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value


def _row_values(row):
    return (
        row["date"],
        row["patient"],
        row["entry_type"],
        row["detail"],
        row["comment"],
    )


def build_csv_export(rows, filename):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    response.write("\ufeff")

    writer = csv.writer(response, delimiter=";")
    writer.writerow(EXPORT_HEADERS)
    for row in rows:
        writer.writerow(tuple(_safe_spreadsheet_value(value) for value in _row_values(row)))

    return response


def _worksheet_xml(rows):
    xml_rows = []
    export_rows = (EXPORT_HEADERS, *(tuple(_row_values(row)) for row in rows))
    for row_index, row in enumerate(export_rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            column_letter = chr(ord("A") + column_index - 1)
            cell_ref = f"{column_letter}{row_index}"
            cell_value = escape(_safe_spreadsheet_value(value))
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{cell_value}</t></is></c>'
            )
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        '<cols><col min="1" max="5" width="24" customWidth="1"/></cols>'
        f'<sheetData>{"".join(xml_rows)}</sheetData>'
        '</worksheet>'
    )


def build_xlsx_export(rows, filename):
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Мониторинг" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        archive.writestr("xl/worksheets/sheet1.xml", _worksheet_xml(rows))

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    return response
