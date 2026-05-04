document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-table-toggle]").forEach(function (button) {
        button.addEventListener("click", function () {
            var panelId = button.getAttribute("aria-controls");
            var panel = document.getElementById(panelId);
            var isExpanded = button.getAttribute("aria-expanded") === "true";

            if (!panel) {
                return;
            }

            panel.hidden = isExpanded;
            button.setAttribute("aria-expanded", String(!isExpanded));
            button.textContent = isExpanded ? "Показать таблицу" : "Скрыть таблицу";
        });
    });
});
