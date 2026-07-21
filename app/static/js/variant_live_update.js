document.addEventListener("DOMContentLoaded", function () {
    const table = document.getElementById("variant-product-table");
    if (!table) return;

    const STATUS_POLL_MS = 1500;

    const fetchRunningBar = document.getElementById("fetch-running-bar");
    const fetchRunningText = document.getElementById("fetch-running-text");
    const stopBtn = document.getElementById("product-list-stop-fetch-btn");

    function updateRunningBar(status) {
        if (!fetchRunningBar) return;
        if (status.running) {
            fetchRunningBar.style.display = "flex";
            const total = status.total || 0;
            const done = status.done || 0;
            fetchRunningText.textContent = total > 0
                ? `Fetching ${done} / ${total} products…`
                : "Starting fetch…";
        } else {
            fetchRunningBar.style.display = "none";
        }
    }

    if (stopBtn) {
        stopBtn.addEventListener("click", function () {
            stopBtn.disabled = true;
            fetch("/fetch/stop", { method: "POST" })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    stopBtn.disabled = false;
                    if (!res.ok) alert(res.error || "Could not stop fetch.");
                });
        });
    }

    let wasRunning = false;

    function pollStatus() {
        fetch("/fetch/status")
            .then(function (r) { return r.json(); })
            .then(function (status) {
                updateRunningBar(status);

                if (status.running) {
                    wasRunning = true;
                } else if (wasRunning) {
                    // No per-cell live-patching for the nested variant tables yet — a
                    // full reload is the simplest way to show the freshly fetched data.
                    window.location.reload();
                    return;
                }
            })
            .finally(function () {
                setTimeout(pollStatus, STATUS_POLL_MS);
            });
    }

    setTimeout(pollStatus, STATUS_POLL_MS);
});
