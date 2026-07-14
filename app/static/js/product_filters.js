document.addEventListener("DOMContentLoaded", function () {
    const optionsDataEl = document.getElementById("filter-options-data");
    const activeDataEl = document.getElementById("filter-active-data");
    if (!optionsDataEl || !activeDataEl) return;

    const FILTER_OPTIONS = JSON.parse(optionsDataEl.textContent || "{}");
    const ACTIVE_FILTERS = JSON.parse(activeDataEl.textContent || "{}");

    const COLUMN_LABELS = {
        category: "Category",
        techbuy_stock: "Stock Status (Tech Buy)",
        other_stock: "Stock Status (Other)",
        need_action: "Need Action",
        fetched_status: "Fetched Status",
        reviewed: "Reviewed",
        other_site: "Other Site",
    };

    const NULL_VALUE = "__NULL__";

    const popover = document.getElementById("filter-popover");
    const popoverTitle = document.getElementById("filter-popover-title");
    const popoverBody = document.getElementById("filter-popover-body");
    const applyBtn = document.getElementById("filter-apply-btn");
    const clearBtn = document.getElementById("filter-clear-btn");
    const resetAllBtn = document.getElementById("reset-filters-btn");
    if (!popover) return;

    let activeCol = null;

    function currentFilters() {
        const copy = {};
        Object.keys(ACTIVE_FILTERS).forEach(function (k) {
            copy[k] = ACTIVE_FILTERS[k].slice();
        });
        return copy;
    }

    function navigateWithFilters(filters) {
        const url = new URL(window.location.href);
        const nonEmpty = {};
        Object.keys(filters).forEach(function (k) {
            if (filters[k] && filters[k].length) nonEmpty[k] = filters[k];
        });
        if (Object.keys(nonEmpty).length) {
            url.searchParams.set("filters", JSON.stringify(nonEmpty));
        } else {
            url.searchParams.delete("filters");
        }
        url.searchParams.set("page", "1");
        window.location.href = url.toString();
    }

    function openPopover(col, btn) {
        const opt = FILTER_OPTIONS[col];
        if (!opt) return;
        activeCol = col;

        popoverTitle.textContent = "Filter: " + (COLUMN_LABELS[col] || col);
        popoverBody.innerHTML = "";

        const active = ACTIVE_FILTERS[col]; // absent = no filter = treat all as checked
        const allValues = opt.values.slice();
        if (opt.has_null) allValues.push(NULL_VALUE);

        if (allValues.length === 0) {
            const empty = document.createElement("p");
            empty.className = "muted";
            empty.textContent = "No values yet.";
            popoverBody.appendChild(empty);
        }

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

        const rect = btn.getBoundingClientRect();
        const popoverWidth = 240; // matches .filter-popover CSS width
        let left = rect.left + window.scrollX;
        if (rect.left + popoverWidth > window.innerWidth) {
            // would overflow off the right edge — open leftward from the button instead
            left = rect.right + window.scrollX - popoverWidth;
        }

        popover.style.display = "block";
        popover.style.top = (rect.bottom + window.scrollY + 6) + "px";
        popover.style.left = left + "px";
    }

    function closePopover() {
        popover.style.display = "none";
        activeCol = null;
    }

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

    if (applyBtn) {
        applyBtn.addEventListener("click", function () {
            if (!activeCol) return;
            const checkboxes = popoverBody.querySelectorAll("input[type=checkbox]");
            const items = Array.prototype.slice.call(checkboxes);
            const checked = items.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });

            const filters = currentFilters();
            if (checked.length === 0 || checked.length === items.length) {
                delete filters[activeCol];
            } else {
                filters[activeCol] = checked;
            }
            navigateWithFilters(filters);
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener("click", function () {
            if (!activeCol) return;
            const filters = currentFilters();
            delete filters[activeCol];
            navigateWithFilters(filters);
        });
    }

    if (resetAllBtn) {
        resetAllBtn.addEventListener("click", function () {
            navigateWithFilters({});
        });
    }

    // ---- category dropdown (single-select convenience filter) ----
    const categorySelect = document.getElementById("category-select");
    if (categorySelect) {
        const activeCategory = ACTIVE_FILTERS.category;
        if (activeCategory && activeCategory.length === 1) {
            categorySelect.value = activeCategory[0];
        }
        categorySelect.addEventListener("change", function () {
            const filters = currentFilters();
            if (categorySelect.value) {
                filters.category = [categorySelect.value];
            } else {
                delete filters.category;
            }
            navigateWithFilters(filters);
        });
    }

    // ---- other site dropdown (single-select convenience filter) ----
    const otherSiteSelect = document.getElementById("other-site-select");
    if (otherSiteSelect) {
        const activeSite = ACTIVE_FILTERS.other_site;
        if (activeSite && activeSite.length === 1) {
            otherSiteSelect.value = activeSite[0];
        }
        otherSiteSelect.addEventListener("change", function () {
            const filters = currentFilters();
            if (otherSiteSelect.value) {
                filters.other_site = [otherSiteSelect.value];
            } else {
                delete filters.other_site;
            }
            navigateWithFilters(filters);
        });
    }
});
