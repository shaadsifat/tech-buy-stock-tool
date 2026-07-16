document.addEventListener("DOMContentLoaded", function () {
    const table = document.getElementById("product-table");
    if (!table) return;

    const STATUS_POLL_MS = 1500;
    const ROW_POLL_MS = 1500;

    function rows() {
        return Array.prototype.slice.call(table.querySelectorAll("tr[data-product-row]"));
    }

    function fmtPrice(v) {
        if (v === null || v === undefined) return '<span class="muted">—</span>';
        return Number(v).toFixed(2);
    }

    function fmtDiff(a, b) {
        const diff = a - b;
        const sign = diff >= 0 ? "+" : "";
        return '<span class="badge badge-neutral">' + sign + diff.toFixed(2) + "</span>";
    }

    function badge(cls, text) {
        return '<span class="badge ' + cls + '">' + text + "</span>";
    }

    function muted() {
        return '<span class="muted">—</span>';
    }

    function patchRow(tr, row) {
        const set = function (col, html) {
            const td = tr.querySelector('td[data-col="' + col + '"]');
            if (td) td.innerHTML = html;
        };

        set("techbuy_stock", row.techbuy_stock || muted());
        set("other_stock", row.other_stock || muted());
        set("techbuy_regular", fmtPrice(row.techbuy_regular));
        set("techbuy_sale", fmtPrice(row.techbuy_sale));
        set("other_regular", fmtPrice(row.other_regular));
        set("other_sale", fmtPrice(row.other_sale));

        if (row.techbuy_regular !== null && row.other_regular !== null) {
            set("regular_diff", fmtDiff(row.techbuy_regular, row.other_regular));
        } else {
            set("regular_diff", muted());
        }

        if (row.techbuy_sale !== null && row.other_sale !== null) {
            set("sale_diff", fmtDiff(row.techbuy_sale, row.other_sale));
        } else if (row.fetched_status === "Fetched") {
            set("sale_diff", badge("badge-neutral", "N/A"));
        } else {
            set("sale_diff", muted());
        }

        if (row.need_action === "Yes") {
            set("need_action", badge("badge-yes", "Yes"));
        } else if (row.need_action === "No") {
            set("need_action", badge("badge-no", "No"));
        } else {
            set("need_action", muted());
        }

        set("fetched_status", row.fetched_status ? badge("badge-neutral", row.fetched_status) : muted());

        const reviewedCheckbox = tr.querySelector(".reviewed-checkbox");
        if (reviewedCheckbox) {
            if (row.need_action === "No") {
                reviewedCheckbox.checked = true;
                reviewedCheckbox.disabled = true;
                reviewedCheckbox.title = "Locked — price and stock status both already match";
            } else {
                reviewedCheckbox.checked = !!row.reviewed;
                reviewedCheckbox.disabled = false;
                reviewedCheckbox.removeAttribute("title");
            }
        }

        tr.classList.toggle("row-reviewed", !!row.reviewed);

        tr.classList.remove("row-update-flash");
        void tr.offsetWidth;
        tr.classList.add("row-update-flash");

        tr.setAttribute("data-fetched-at", row.fetched_at || "");
    }

    function pollRowUpdates() {
        const trs = rows();
        if (!trs.length) return;

        const ids = trs.map(function (tr) { return tr.getAttribute("data-product-id"); });

        fetch("/products/row-updates", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids: ids }),
        })
            .then(function (r) { return r.json(); })
            .then(function (res) {
                if (!res.ok) return;
                res.rows.forEach(function (row) {
                    const tr = table.querySelector('tr[data-product-id="' + row.id + '"]');
                    if (!tr) return;
                    const known = tr.getAttribute("data-fetched-at") || "";
                    const latest = row.fetched_at || "";
                    if (latest !== known) {
                        patchRow(tr, row);
                    }
                });
            })
            .catch(function () {
                // transient network hiccup — next poll will catch up
            });
    }

    let wasRunning = false;

    // ---- stop-fetching control, visible whenever any fetch is running ----
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

    function pollStatus() {
        fetch("/fetch/status")
            .then(function (r) { return r.json(); })
            .then(function (status) {
                updateRunningBar(status);

                if (status.running) {
                    wasRunning = true;
                    pollRowUpdates();
                } else if (wasRunning) {
                    // fetch just finished — one last poll to catch the final row(s)
                    wasRunning = false;
                    pollRowUpdates();
                }
            })
            .finally(function () {
                setTimeout(pollStatus, STATUS_POLL_MS);
            });
    }

    setTimeout(pollStatus, ROW_POLL_MS);
});
