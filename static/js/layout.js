document.addEventListener("DOMContentLoaded", function () {
    var menuToggle = document.getElementById("menuToggle");
    var topNav = document.getElementById("topNav");

    if (menuToggle && topNav) {
        menuToggle.addEventListener("click", function () {
            topNav.classList.toggle("open");
        });
    }

    var sidebar = document.getElementById("sidebar");
    var sidebarBackdrop = document.getElementById("sidebarBackdrop");
    var sidebarOpen = document.getElementById("sidebarOpen");
    var sidebarClose = document.getElementById("sidebarClose");
    var pageOpenClass = "has-sidebar-open";

    function syncSidebarState(isOpen) {
        if (!sidebar) {
            return;
        }
        sidebar.classList.toggle("open", isOpen);
        sidebar.setAttribute("aria-hidden", String(!isOpen));
        if (isOpen) {
            sidebar.removeAttribute("inert");
        } else {
            sidebar.setAttribute("inert", "");
        }
        if (sidebarBackdrop) {
            sidebarBackdrop.classList.toggle("open", isOpen);
            sidebarBackdrop.setAttribute("aria-hidden", String(!isOpen));
        }
        document.body.classList.toggle(pageOpenClass, isOpen);
        if (sidebarOpen) {
            sidebarOpen.setAttribute("aria-expanded", String(isOpen));
        }
    }

    function openSidebar() {
        if (!sidebar || sidebar.classList.contains("open")) {
            return;
        }
        syncSidebarState(true);
        if (sidebarClose) {
            window.requestAnimationFrame(function () {
                sidebarClose.focus();
            });
        }
    }

    function closeSidebar() {
        if (!sidebar) {
            return;
        }
        var wasOpen = sidebar.classList.contains("open");
        syncSidebarState(false);
        if (wasOpen && sidebarOpen) {
            sidebarOpen.focus();
        }
    }

    syncSidebarState(false);

    if (sidebarOpen && sidebar) {
        sidebarOpen.addEventListener("click", openSidebar);
    }
    if (sidebarClose && sidebar) {
        sidebarClose.addEventListener("click", closeSidebar);
    }
    if (sidebarBackdrop && sidebar) {
        sidebarBackdrop.addEventListener("click", closeSidebar);
    }
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && sidebar && sidebar.classList.contains("open")) {
            event.preventDefault();
            closeSidebar();
        }
    });
});
