document.addEventListener("DOMContentLoaded", function () {
    const table = document.getElementById("variant-product-table");
    const bulkBar = document.getElementById("bulk-action-bar");
    if (!table || !bulkBar) return;

    const selectAllCheckbox = document.getElementById("select-all-checkbox");
    const bulkCount = document.getElementById("bulk-selected-count");
    const markReviewedBtn = document.getElementById("bulk-mark-reviewed-btn");
    const refetchBtn = document.getElementById("bulk-refetch-btn");
    const exportBtn = document.getElementById("bulk-export-btn");
    const deleteBtn = document.getElementById("bulk-delete-btn");
    const clearBtn = document.getElementById("bulk-clear-btn");

    function rowCheckboxes() {
        return Array.prototype.slice.call(table.querySelectorAll(".row-select-checkbox"));
    }

    function selectedIds() {
        return rowCheckboxes()
            .filter(function (cb) { return cb.checked; })
            .map(function (cb) { return cb.getAttribute("data-product-id"); });
    }

    function updateBar() {
        const ids = selectedIds();
        const all = rowCheckboxes();

        if (ids.length > 0) {
            bulkBar.style.display = "flex";
            bulkCount.textContent = ids.length + " selected";
        } else {
            bulkBar.style.display = "none";
        }

        if (selectAllCheckbox) {
            selectAllCheckbox.checked = all.length > 0 && ids.length === all.length;
            selectAllCheckbox.indeterminate = ids.length > 0 && ids.length < all.length;
        }
    }

    table.addEventListener("change", function (e) {
        if (e.target.classList.contains("row-select-checkbox")) {
            updateBar();
        }
    });

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener("change", function () {
            rowCheckboxes().forEach(function (cb) { cb.checked = selectAllCheckbox.checked; });
            updateBar();
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener("click", function () {
            rowCheckboxes().forEach(function (cb) { cb.checked = false; });
            updateBar();
        });
    }

    if (deleteBtn) {
        deleteBtn.addEventListener("click", function () {
            const ids = selectedIds();
            if (!ids.length) return;
            if (!confirm("Permanently delete " + ids.length + " product(s) — all their variants included? This cannot be undone.")) return;

            deleteBtn.disabled = true;
            fetch("/products/bulk-delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ids: ids }),
            }).then(function () {
                window.location.reload();
            }).catch(function () {
                deleteBtn.disabled = false;
            });
        });
    }

    if (markReviewedBtn) {
        markReviewedBtn.addEventListener("click", function () {
            const ids = selectedIds();
            if (!ids.length) return;

            markReviewedBtn.disabled = true;
            fetch("/products/variants/bulk-mark-reviewed", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ids: ids }),
            }).then(function () {
                window.location.reload();
            }).catch(function () {
                markReviewedBtn.disabled = false;
            });
        });
    }

    if (exportBtn) {
        exportBtn.addEventListener("click", function () {
            const ids = selectedIds();
            if (!ids.length) return;

            const form = document.createElement("form");
            form.method = "POST";
            form.action = "/products/bulk-export";
            ids.forEach(function (id) {
                const input = document.createElement("input");
                input.type = "hidden";
                input.name = "ids";
                input.value = id;
                form.appendChild(input);
            });
            document.body.appendChild(form);
            form.submit();
            form.remove();
        });
    }

    function pollRefetch(originalText) {
        fetch("/fetch/status")
            .then(function (r) { return r.json(); })
            .then(function (status) {
                if (status.running) {
                    refetchBtn.textContent = "Fetching " + status.done + "/" + status.total + "...";
                    setTimeout(function () { pollRefetch(originalText); }, 1000);
                } else {
                    // no per-cell live-patching for the nested variant tables yet —
                    // variant_live_update.js reloads the page once the run finishes
                    refetchBtn.disabled = false;
                    refetchBtn.textContent = originalText;
                }
            });
    }

    if (refetchBtn) {
        refetchBtn.addEventListener("click", function () {
            const ids = selectedIds();
            if (!ids.length) return;

            const originalText = refetchBtn.textContent;
            refetchBtn.disabled = true;
            refetchBtn.textContent = "Starting...";

            fetch("/products/bulk-refetch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ids: ids }),
            }).then(function (r) { return r.json(); }).then(function (res) {
                if (!res.ok) {
                    alert(res.error || "Could not start fetch.");
                    refetchBtn.disabled = false;
                    refetchBtn.textContent = originalText;
                    return;
                }
                pollRefetch(originalText);
            });
        });
    }

    updateBar();

    window.__resetBulkBar = updateBar;
});
