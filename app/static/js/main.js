document.addEventListener("DOMContentLoaded", function () {
    const startBtn = document.getElementById("start-fetch-btn");
    const stopBtn = document.getElementById("stop-fetch-btn");
    const importBtn = document.getElementById("import-excel-btn");
    const clearForm = document.getElementById("clear-form");
    const progressSection = document.getElementById("progress-section");
    const progressFill = document.getElementById("progress-fill");
    const progressText = document.getElementById("progress-text");
    const fetchedCountText = document.getElementById("fetched-count-text");
    const summaryBoxEl = document.getElementById("summary-box");

    let pollTimer = null;

    function setButtonsForRunning(running) {
        startBtn.disabled = running;
        startBtn.textContent = running ? "Fetching..." : "Start Fetching";
        stopBtn.style.display = running ? "inline-flex" : "none";
    }

    function updateProgress(status) {
        const total = status.total || 0;
        const done = status.done || 0;
        const pct = total > 0 ? Math.round((done / total) * 100) : 0;

        progressSection.style.display = "block";
        progressFill.style.width = pct + "%";
        progressText.textContent = total > 0
            ? `Fetching ${done} / ${total} products (${pct}%)`
            : "Starting...";
    }

    // ---- live dashboard refresh (stat cards + charts + summary), no reload ----
    function patchChart(key, data) {
        const card = document.querySelector('.chart-card[data-chart="' + key + '"]');
        if (!card) return;
        const values = Object.keys(data).map(function (k) { return data[k]; });
        const maxVal = values.length ? Math.max.apply(null, values) : 0;

        Object.keys(data).forEach(function (label) {
            const row = card.querySelector('.bar-row[data-label="' + label + '"]');
            if (!row) return;
            const value = data[label];
            const pct = maxVal ? (value / maxVal * 100) : 0;
            const fill = row.querySelector(".bar-fill");
            const valueEl = row.querySelector(".bar-value");
            if (fill) fill.style.setProperty("--bar-width", pct + "%");
            if (valueEl) valueEl.textContent = value;
        });
    }

    function refreshDashboard() {
        fetch("/dashboard/stats")
            .then(function (r) { return r.json(); })
            .then(function (res) {
                if (!res.ok) return;

                document.querySelectorAll(".stat-card[data-stat]").forEach(function (card) {
                    const key = card.getAttribute("data-stat");
                    const value = res.stats[key];
                    if (value === undefined) return;
                    const valueEl = card.querySelector(".stat-value");
                    if (valueEl) valueEl.textContent = value;
                });

                Object.keys(res.report).forEach(function (key) {
                    patchChart(key, res.report[key]);
                });

                if (summaryBoxEl) summaryBoxEl.textContent = res.summary_text;
                fetchedCountText.textContent = `${res.fetched_count} product(s) have fetched data ready.`;

                if (res.fetched_count > 0) {
                    importBtn.style.display = "inline-flex";
                    clearForm.style.display = "inline";
                }
            });
    }

    function pollStatus() {
        fetch("/fetch/status")
            .then((r) => r.json())
            .then((status) => {
                setButtonsForRunning(status.running);

                if (status.running || status.total > 0) {
                    updateProgress(status);
                }

                if (status.running) {
                    refreshDashboard();
                    pollTimer = setTimeout(pollStatus, 1500);
                } else {
                    clearTimeout(pollTimer);
                    if (status.total > 0) {
                        progressText.textContent = status.stopped
                            ? `Stopped. Fetched ${status.done} / ${status.total} products.`
                            : `Done. Fetched ${status.done} / ${status.total} products.`;
                        refreshDashboard();
                    }
                }
            });
    }

    startBtn.addEventListener("click", function () {
        fetch("/fetch/start", { method: "POST" })
            .then((r) => r.json())
            .then((res) => {
                if (res.ok) {
                    setButtonsForRunning(true);
                    pollStatus();
                } else {
                    alert(res.error || "Could not start fetch.");
                }
            });
    });

    stopBtn.addEventListener("click", function () {
        stopBtn.disabled = true;
        fetch("/fetch/stop", { method: "POST" })
            .then((r) => r.json())
            .then((res) => {
                stopBtn.disabled = false;
                if (!res.ok) {
                    alert(res.error || "Could not stop fetch.");
                }
            });
    });

    // In case a fetch is already running when the page loads (e.g. refresh,
    // or a fetch started from another page like Product List).
    fetch("/fetch/status")
        .then((r) => r.json())
        .then((status) => {
            if (status.running) {
                setButtonsForRunning(true);
                pollStatus();
            }
        });

    // ---- click-to-copy summary box ----
    const summaryBox = document.getElementById("summary-box");
    if (summaryBox && navigator.clipboard) {
        let toast = null;
        let toastTimer = null;

        summaryBox.addEventListener("click", function (e) {
            const text = summaryBox.innerText.trim();
            if (!text) return;

            navigator.clipboard.writeText(text).then(function () {
                if (!toast) {
                    toast = document.createElement("div");
                    toast.className = "copy-toast";
                    toast.textContent = "Copied!";
                    document.body.appendChild(toast);
                }
                toast.style.left = e.clientX + "px";
                toast.style.top = e.clientY + "px";
                toast.classList.remove("show");
                void toast.offsetWidth;
                toast.classList.add("show");
                clearTimeout(toastTimer);
                toastTimer = setTimeout(function () {
                    toast.classList.remove("show");
                }, 900);

                summaryBox.classList.remove("copy-flash");
                void summaryBox.offsetWidth;
                summaryBox.classList.add("copy-flash");
            }).catch(function () {
                // clipboard unavailable — fail silently
            });
        });
    }
});
