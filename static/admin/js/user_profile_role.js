(function () {
    function getFieldRow(fieldId) {
        var input = document.getElementById(fieldId);
        if (!input) {
            return null;
        }

        return input.closest(".form-row")
            || input.closest(".fieldBox")
            || input.closest(".form-group")
            || input.parentElement;
    }

    function setVisibility(row, isVisible) {
        if (!row) {
            return;
        }

        row.style.display = isVisible ? "" : "none";
    }

    function updateProfileFields() {
        var roleField = document.getElementById("id_profile_role");
        if (!roleField) {
            return;
        }

        var specialtyRow = getFieldRow("id_specialty");
        var diabetesTypeRow = getFieldRow("id_diabetes_type");
        var role = roleField.value;

        setVisibility(specialtyRow, role === "doctor");
        setVisibility(diabetesTypeRow, role === "patient");
    }

    document.addEventListener("DOMContentLoaded", function () {
        var roleField = document.getElementById("id_profile_role");
        if (!roleField) {
            return;
        }

        updateProfileFields();
        roleField.addEventListener("change", updateProfileFields);
    });
})();
