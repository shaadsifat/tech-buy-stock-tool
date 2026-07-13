document.addEventListener("DOMContentLoaded", function () {
    const startBtn = document.getElementById("start-fetch-btn");
    const importBtn = document.getElementById("import-excel-btn");
    const clearForm = document.getElementById("clear-form");
    const progressSection = document.getElementById("progress-section");
    const progressFill = document.getElementById("progress-fill");
    const progressText = document.getElementById("progress-text");
    const fetchedCountText = document.getElementById("fetched-count-text");

    let pollTimer = null;

    function setButtonsForRunning(running) {
        startBtn.disabled = running;
        startBtn.textContent = running ? "Fetching..." : "Start Fetching";
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

    function pollStatus() {
        fetch("/fetch/status")
            .then((r) => r.json())
            .then((status) => {
                setButtonsForRunning(status.running);

                if (status.running || status.total > 0) {
                    updateProgress(status);
                }

                if (status.running) {
                    pollTimer = setTimeout(pollStatus, 1000);
                } else {
                    clearTimeout(pollTimer);
                    if (status.total > 0) {
                        progressText.textContent = `Done. Fetched ${status.done} / ${status.total} products.`;
                        importBtn.style.display = "inline-flex";
                        clearForm.style.display = "inline";
                        fetchedCountText.textContent = `${status.done} product(s) have fetched data ready.`;
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

    // In case a fetch is already running when the page loads (e.g. refresh).
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
