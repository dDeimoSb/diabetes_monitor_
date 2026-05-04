(function () {
    function togglePassword(button) {
        var wrapper = button.closest(".password-input-wrap");
        if (!wrapper) {
            return;
        }

        var input = wrapper.querySelector("input");
        if (!input) {
            return;
        }

        var isVisible = input.type === "text";
        input.type = isVisible ? "password" : "text";
        button.classList.toggle("is-visible", !isVisible);
        button.setAttribute("aria-pressed", String(!isVisible));
        button.setAttribute(
            "aria-label",
            !isVisible ? button.dataset.hideLabel : button.dataset.showLabel
        );
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
            button.addEventListener("click", function () {
                togglePassword(button);
            });
        });
    });
})();
