document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("select[data-searchable]").forEach(enhance);

    function enhance(select) {
        const wrapper = document.createElement("div");
        wrapper.className = "searchable-select";
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);
        select.classList.add("searchable-select-native");

        const input = document.createElement("input");
        input.type = "text";
        input.className = "searchable-select-input";
        input.placeholder = select.getAttribute("data-placeholder") || "Search...";
        wrapper.appendChild(input);

        const dropdown = document.createElement("div");
        dropdown.className = "searchable-select-dropdown";
        dropdown.style.display = "none";
        wrapper.appendChild(dropdown);

        function optionsList() {
            return Array.prototype.slice.call(select.options);
        }

        function syncInputToSelection() {
            const opt = select.options[select.selectedIndex];
            input.value = opt ? opt.textContent : "";
        }

        function buildDropdown(filterText) {
            dropdown.innerHTML = "";
            const filter = (filterText || "").toLowerCase().trim();

            optionsList().forEach(function (opt) {
                if (filter && opt.value && opt.textContent.toLowerCase().indexOf(filter) === -1) return;

                const item = document.createElement("div");
                item.className = "searchable-select-item";
                item.textContent = opt.textContent;
                if (opt.value === select.value) item.classList.add("active");
                item.addEventListener("mousedown", function (e) {
                    e.preventDefault();
                    select.value = opt.value;
                    syncInputToSelection();
                    dropdown.style.display = "none";
                    select.dispatchEvent(new Event("change"));
                });
                dropdown.appendChild(item);
            });

            if (!dropdown.children.length) {
                const empty = document.createElement("div");
                empty.className = "searchable-select-empty";
                empty.textContent = "No matches";
                dropdown.appendChild(empty);
            }
        }

        input.addEventListener("focus", function () {
            buildDropdown("");
            dropdown.style.display = "block";
        });

        input.addEventListener("input", function () {
            buildDropdown(input.value);
            dropdown.style.display = "block";
        });

        input.addEventListener("blur", function () {
            // let a mousedown-selected item register before we hide the dropdown
            setTimeout(function () {
                dropdown.style.display = "none";
                syncInputToSelection();
            }, 150);
        });

        input.addEventListener("keydown", function (e) {
            if (e.key === "Escape") {
                dropdown.style.display = "none";
                syncInputToSelection();
                input.blur();
            }
        });

        syncInputToSelection();
    }
});
