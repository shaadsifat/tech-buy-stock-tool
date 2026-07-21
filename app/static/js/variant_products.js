document.addEventListener("DOMContentLoaded", function () {
    const table = document.getElementById("variant-product-table");
    if (!table) return;

    // ---- category dropdown ----
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

    // ---- expand/collapse variant sub-table ----
    table.addEventListener("click", function (e) {
        const btn = e.target.closest(".expand-toggle-btn");
        if (!btn) return;
        const targetId = btn.getAttribute("data-expand-target");
        const group = document.getElementById(targetId);
        if (!group) return;
        const expanded = btn.getAttribute("aria-expanded") === "true";
        group.hidden = expanded;
        btn.setAttribute("aria-expanded", String(!expanded));
        btn.classList.toggle("expanded", !expanded);
    });

    // ---- per-variant reviewed checkbox ----
    function updateParentReviewedState(groupRow) {
        // A product is only "Reviewed" once every one of its variants is (locked
        // checkboxes count too, since they're checked+disabled in the DOM already).
        const productId = groupRow.id.replace("variant-group-", "");
        const parentRow = table.querySelector('tr[data-parent-row][data-product-id="' + productId + '"]');
        if (!parentRow) return;

        const checkboxes = Array.prototype.slice.call(groupRow.querySelectorAll(".variant-reviewed-checkbox"));
        const allReviewed = checkboxes.length > 0 && checkboxes.every(function (cb) { return cb.checked; });

        parentRow.classList.toggle("row-reviewed", allReviewed);
        const badgeCell = parentRow.querySelector('td[data-col="reviewed"]');
        if (badgeCell) {
            const badge = badgeCell.querySelector(".badge");
            if (badge) {
                badge.textContent = allReviewed ? "Yes" : "No";
                badge.classList.toggle("badge-no", allReviewed);
                badge.classList.toggle("badge-yes", !allReviewed);
            }
        }
    }

    table.addEventListener("change", function (e) {
        const checkbox = e.target.closest(".variant-reviewed-checkbox");
        if (!checkbox) return;

        const variantId = checkbox.getAttribute("data-variant-id");
        const reviewed = checkbox.checked;
        const row = checkbox.closest("tr[data-variant-row]");
        if (row) row.classList.toggle("row-reviewed", reviewed);

        const groupRow = checkbox.closest("tr[data-variant-group-row]");
        if (groupRow) updateParentReviewedState(groupRow);

        fetch("/products/variants/" + variantId + "/reviewed", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reviewed: reviewed }),
        }).catch(function () {
            checkbox.checked = !reviewed;
            if (row) row.classList.toggle("row-reviewed", !reviewed);
            if (groupRow) updateParentReviewedState(groupRow);
        });
    });

    // ---- click-to-copy cells (outer product row + nested variant rows) ----
    const NO_COPY_COLUMNS = ["actions", "techbuy_link", "other_link", "reviewed"];
    let copyToast = null;
    let copyToastTimer = null;

    function showCopyToast(x, y) {
        if (!copyToast) {
            copyToast = document.createElement("div");
            copyToast.className = "copy-toast";
            copyToast.textContent = "Copied!";
            document.body.appendChild(copyToast);
        }
        copyToast.style.left = x + "px";
        copyToast.style.top = y + "px";
        copyToast.classList.remove("show");
        void copyToast.offsetWidth;
        copyToast.classList.add("show");
        clearTimeout(copyToastTimer);
        copyToastTimer = setTimeout(function () {
            copyToast.classList.remove("show");
        }, 900);
    }

    table.addEventListener("click", function (e) {
        const td = e.target.closest("td[data-col]");
        if (!td || !table.contains(td)) return;

        const col = td.getAttribute("data-col");
        if (NO_COPY_COLUMNS.indexOf(col) !== -1) return;

        const text = (td.getAttribute("data-full-text") || td.innerText).trim();
        if (!text || text === "—") return;

        if (!navigator.clipboard) return;

        navigator.clipboard.writeText(text).then(function () {
            showCopyToast(e.clientX, e.clientY);
            td.classList.remove("copy-flash");
            void td.offsetWidth;
            td.classList.add("copy-flash");
        }).catch(function () {
            // clipboard unavailable (e.g. non-secure context) — fail silently
        });
    });
});
