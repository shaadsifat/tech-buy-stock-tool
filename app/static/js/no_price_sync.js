document.addEventListener("DOMContentLoaded", function () {
    const table = document.getElementById("no-sync-table");
    const bulkBar = document.getElementById("bulk-action-bar");
    if (!table || !bulkBar) return;

    const selectAllCheckbox = document.getElementById("select-all-checkbox");
    const bulkCount = document.getElementById("bulk-selected-count");
    const markBtn = document.getElementById("bulk-mark-no-sync-btn");
    const unmarkBtn = document.getElementById("bulk-unmark-no-sync-btn");
    const clearBtn = document.getElementById("bulk-clear-btn");

    const categorySelect = document.getElementById("category-select");
    if (categorySelect) {
        const url = new URL(window.location.href);
        const activeCategory = url.searchParams.get("category");
        if (activeCategory) categorySelect.value = activeCategory;

        categorySelect.addEventListener("change", function () {
            const target = new URL(window.location.href);
            if (categorySelect.value) {
                target.searchParams.set("category", categorySelect.value);
            } else {
                target.searchParams.delete("category");
            }
            target.searchParams.set("page", "1");
            window.location.href = target.toString();
        });
    }

    const pageSizeSelect = document.getElementById("page-size-select");
    if (pageSizeSelect) {
        pageSizeSelect.addEventListener("change", function () {
            const target = new URL(window.location.href);
            target.searchParams.set("size", pageSizeSelect.value);
            target.searchParams.set("page", "1");
            window.location.href = target.toString();
        });
    }

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

    function bulkToggle(flag) {
        const ids = selectedIds();
        if (!ids.length) return;
        fetch("/products/no-price-sync/toggle", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids: ids, flag: flag }),
        }).then(function () {
            window.location.reload();
        });
    }

    if (markBtn) markBtn.addEventListener("click", function () { bulkToggle(true); });
    if (unmarkBtn) unmarkBtn.addEventListener("click", function () { bulkToggle(false); });

    // ---- per-row checkbox ----
    table.addEventListener("change", function (e) {
        const checkbox = e.target.closest(".no-sync-checkbox");
        if (!checkbox) return;

        const productId = checkbox.getAttribute("data-product-id");
        const flag = checkbox.checked;
        const row = checkbox.closest("tr[data-product-row]");
        if (row) row.classList.toggle("row-reviewed", flag);

        fetch("/products/no-price-sync/toggle", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids: [productId], flag: flag }),
        }).catch(function () {
            checkbox.checked = !flag;
            if (row) row.classList.toggle("row-reviewed", !flag);
        });
    });

    updateBar();
    window.__resetBulkBar = updateBar;

    // ---- column filter popover (No Price Sync only) ----
    const optionsDataEl = document.getElementById("filter-options-data");
    const activeDataEl = document.getElementById("filter-active-data");
    if (optionsDataEl && activeDataEl) {
        const FILTER_OPTIONS = JSON.parse(optionsDataEl.textContent || "{}");
        const ACTIVE_FILTERS = JSON.parse(activeDataEl.textContent || "{}");
        const NULL_VALUE = "__NULL__";
        const COLUMN_LABELS = { no_price_sync: "No Price Sync" };

        const popover = document.getElementById("filter-popover");
        const popoverTitle = document.getElementById("filter-popover-title");
        const popoverBody = document.getElementById("filter-popover-body");
        const applyBtn = document.getElementById("filter-apply-btn");
        const clearBtn = document.getElementById("filter-clear-btn");
        const filterSearchInput = document.getElementById("filter-search-input");
        const selectAllBtn = document.getElementById("filter-select-all-btn");
        const deselectAllBtn = document.getElementById("filter-deselect-all-btn");

        let activeCol = null;

        function currentFilters() {
            const copy = {};
            Object.keys(ACTIVE_FILTERS).forEach(function (k) { copy[k] = ACTIVE_FILTERS[k].slice(); });
            return copy;
        }

        function navigateWithFilters(filters) {
            const target = new URL(window.location.href);
            const nonEmpty = {};
            Object.keys(filters).forEach(function (k) {
                if (filters[k] && filters[k].length) nonEmpty[k] = filters[k];
            });
            if (Object.keys(nonEmpty).length) {
                target.searchParams.set("filters", JSON.stringify(nonEmpty));
            } else {
                target.searchParams.delete("filters");
            }
            target.searchParams.set("page", "1");
            window.location.href = target.toString();
        }

        function filterPopoverOptions(searchText) {
            const filter = (searchText || "").toLowerCase().trim();
            popoverBody.querySelectorAll(".filter-option").forEach(function (label) {
                const text = label.textContent.toLowerCase();
                label.classList.toggle("filter-option-hidden", !!filter && text.indexOf(filter) === -1);
            });
        }

        function openPopover(col, btn) {
            const opt = FILTER_OPTIONS[col];
            if (!opt) return;
            activeCol = col;

            popoverTitle.textContent = "Filter: " + (COLUMN_LABELS[col] || col);
            popoverBody.innerHTML = "";
            if (filterSearchInput) filterSearchInput.value = "";

            const active = ACTIVE_FILTERS[col];
            const allValues = opt.values.slice();
            if (opt.has_null) allValues.push(NULL_VALUE);

            const showSearch = allValues.length > 8;
            if (filterSearchInput) filterSearchInput.parentElement.style.display = showSearch ? "block" : "none";

            allValues.forEach(function (val) {
                const label = document.createElement("label");
                label.className = "filter-option";
                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.value = val;
                cb.checked = !active || active.indexOf(val) !== -1;
                label.appendChild(cb);
                const span = document.createElement("span");
                span.textContent = val === NULL_VALUE ? "(Not fetched)" : val;
                label.appendChild(span);
                popoverBody.appendChild(label);
            });

            popover.style.display = "block";
            popover.style.top = "0px";
            popover.style.left = "0px";

            const rect = btn.getBoundingClientRect();
            const popoverWidth = 240;
            const popoverHeight = popover.offsetHeight;

            let left = rect.left + window.scrollX;
            if (rect.left + popoverWidth > window.innerWidth) left = rect.right + window.scrollX - popoverWidth;

            let top = rect.bottom + window.scrollY + 6;
            if (rect.bottom + popoverHeight + 6 > window.innerHeight) top = rect.top + window.scrollY - popoverHeight - 6;

            popover.style.top = top + "px";
            popover.style.left = left + "px";
        }

        function closePopover() {
            popover.style.display = "none";
            activeCol = null;
        }

        if (filterSearchInput) {
            filterSearchInput.addEventListener("input", function () {
                filterPopoverOptions(filterSearchInput.value);
            });
        }

        function visibleCheckboxes() {
            return Array.prototype.slice
                .call(popoverBody.querySelectorAll(".filter-option"))
                .filter(function (label) { return !label.classList.contains("filter-option-hidden"); })
                .map(function (label) { return label.querySelector("input[type=checkbox]"); });
        }

        if (selectAllBtn) selectAllBtn.addEventListener("click", function () {
            visibleCheckboxes().forEach(function (cb) { cb.checked = true; });
        });
        if (deselectAllBtn) deselectAllBtn.addEventListener("click", function () {
            visibleCheckboxes().forEach(function (cb) { cb.checked = false; });
        });

        document.querySelectorAll(".filter-btn").forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.stopPropagation();
                const col = btn.getAttribute("data-filter-col");
                if (activeCol === col && popover.style.display === "block") {
                    closePopover();
                } else {
                    openPopover(col, btn);
                }
            });
        });

        document.addEventListener("click", function (e) {
            if (popover.style.display === "block" && !popover.contains(e.target) && !e.target.closest(".filter-btn")) {
                closePopover();
            }
        });

        if (applyBtn) applyBtn.addEventListener("click", function () {
            if (!activeCol) return;
            const items = Array.prototype.slice.call(popoverBody.querySelectorAll("input[type=checkbox]"));
            const checked = items.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
            const filters = currentFilters();
            if (checked.length === 0 || checked.length === items.length) {
                delete filters[activeCol];
            } else {
                filters[activeCol] = checked;
            }
            navigateWithFilters(filters);
        });

        if (clearBtn) clearBtn.addEventListener("click", function () {
            if (!activeCol) return;
            const filters = currentFilters();
            delete filters[activeCol];
            navigateWithFilters(filters);
        });
    }
});
