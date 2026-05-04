document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("monitoringEntryForm");
    if (!form) {
        return;
    }

    var typeSelect = form.querySelector('[name="entry_type"]');
    var entryDatetimeInput = form.querySelector('[name="entry_datetime"]');
    var fieldGroups = form.querySelectorAll("[data-entry-fields]");
    var autoDatetime = form.dataset.autoDatetime === "true";

    function pad(value) {
        return String(value).padStart(2, "0");
    }

    function getCurrentDatetimeValue() {
        var now = new Date();
        return [
            now.getFullYear(),
            pad(now.getMonth() + 1),
            pad(now.getDate())
        ].join("-") + "T" + [
            pad(now.getHours()),
            pad(now.getMinutes())
        ].join(":");
    }

    function setCurrentDatetime() {
        if (autoDatetime && entryDatetimeInput) {
            entryDatetimeInput.value = getCurrentDatetimeValue();
        }
    }

    function syncEntryFields() {
        if (!typeSelect) {
            return;
        }
        var selectedType = typeSelect.value;
        fieldGroups.forEach(function (group) {
            var isActive = group.dataset.entryFields === selectedType;
            group.hidden = !isActive;
            group.style.display = isActive ? "" : "none";
            group.setAttribute("aria-hidden", String(!isActive));
            group.querySelectorAll("input, select, textarea").forEach(function (control) {
                control.disabled = !isActive;
            });
        });
    }

    if (typeSelect) {
        typeSelect.addEventListener("change", syncEntryFields);
    }
    setCurrentDatetime();
    syncEntryFields();
});
