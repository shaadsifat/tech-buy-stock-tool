document.addEventListener("DOMContentLoaded", function () {
    const toggleBtn = document.getElementById("sidebar-toggle-btn");
    if (!toggleBtn) return;

    const root = document.documentElement;
    const STORAGE_KEY = "sidebarCollapsed";

    function setLabel() {
        const collapsed = root.classList.contains("sidebar-collapsed");
        const label = collapsed ? "Expand sidebar" : "Collapse sidebar";
        toggleBtn.setAttribute("aria-label", label);
        toggleBtn.setAttribute("title", label);
    }

    setLabel();

    toggleBtn.addEventListener("click", function () {
        const collapsed = root.classList.toggle("sidebar-collapsed");
        try {
            localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
        } catch (e) {}
        setLabel();
    });
});
