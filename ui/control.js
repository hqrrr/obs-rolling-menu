// Holds the latest state object fetched from the backend
let currentState = null;
// Debounce timer ID used to batch frequent form changes into a single save
let saveTimer = null;
// Name of the currently applied preset (if any)
let currentPresetName = "";
// Cached list of all available columns from the backend
let allColumns = [];

/**
 * Fetch all available columns from the backend and populate the column-select
 * dropdown in the control UI.
 */
async function loadColumns() {
    const resp = await fetch("/api/columns");
    const data = await resp.json();
    allColumns = data.columns || [];

    const colSelect = document.getElementById("column-select");
    colSelect.innerHTML = "";

    allColumns.forEach(col => {
        const opt = document.createElement("option");
        opt.value = col;
        opt.textContent = col;
        colSelect.appendChild(opt);
    });
}

/**
 * Update the "group by" dropdown options based on the currently selected column.
 *
 * Rules:
 * - First option: "no grouping".
 * - Grouping candidates: all columns except the selected display column.
 * - Single-column group options: one per candidate.
 * - Combined group options: pairs of columns (up to two columns), ordered (i < j).
 * - If the current state's groupByColumn is still valid, it is restored.
 */
function refreshGroupByOptions() {
    const groupSelect = document.getElementById("group-by-select");
    const colSelect = document.getElementById("column-select");
    if (!groupSelect || !colSelect) return;

    const selectedCol = colSelect.value;
    groupSelect.innerHTML = "";

    // First option: "no grouping"
    const optNone = document.createElement("option");
    optNone.value = "";
    optNone.textContent = "- 不分类 / No Classification -";
    groupSelect.appendChild(optNone);

    // Candidate columns: all columns except the currently selected display column
    const candidates = (allColumns || []).filter(c => c !== selectedCol);

    // Single-column options
    candidates.forEach(col => {
        const opt = document.createElement("option");
        opt.value = col;
        opt.textContent = col;
        groupSelect.appendChild(opt);
    });

    // Combined options: up to two columns, pairs (i < j)
    for (let i = 0; i < candidates.length; i++) {
        for (let j = i + 1; j < candidates.length; j++) {
            const c1 = candidates[i];
            const c2 = candidates[j];
            const value = `${c1}+${c2}`;
            const label = `${c1} + ${c2}`;

            const opt = document.createElement("option");
            opt.value = value;
            opt.textContent = label;
            groupSelect.appendChild(opt);
        }
    }

    // Restore groupByColumn from currentState if the value is still valid
    const gb = currentState.groupByColumn || "";
    const exists = Array.from(groupSelect.options).some(o => o.value === gb);
    groupSelect.value = exists ? gb : "";
}

/**
 * Fetch the current overlay state from the backend and apply it to the form.
 */
async function loadState() {
    const resp = await fetch("/api/state");
    currentState = await resp.json();

    const colSelect = document.getElementById("column-select");
    if (currentState.selected_column) {
        colSelect.value = currentState.selected_column;
    }

    fillFormFromState();

    refreshGroupByOptions();
}

/**
 * Fetch the list of available presets and populate the preset dropdown.
 *
 * Behavior:
 * - Adds a top-level "no preset selected" option.
 * - Attempts to keep the previously selected preset selected if it still exists.
 */
async function loadPresets() {
    const resp = await fetch("/api/presets");
    const data = await resp.json();
    const presets = data.presets || [];

    const select = document.getElementById("preset-select");
    select.innerHTML = "";

    // Top-level "no preset" option
    const optNone = document.createElement("option");
    optNone.value = "";
    optNone.textContent = "- 未选择预设 / No preset selected -";
    select.appendChild(optNone);

    presets.forEach(name => {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        select.appendChild(opt);
    });

    // Keep the previously selected preset if it still exists
    if (currentPresetName && presets.includes(currentPresetName)) {
        select.value = currentPresetName;
    } else {
        currentPresetName = "";
        select.value = "";
    }
}

/**
 * Apply the given preset name:
 * - Load preset from backend.
 * - Merge into currentState.
 * - Update form and immediately save to backend so overlay updates.
 */
async function applyPreset(name) {
    if (!name) {
        currentPresetName = "";
        showPresetMessage("当前未使用任何预设。");
        return;
    }

    const resp = await fetch(`/api/presets/${encodeURIComponent(name)}`);
    const data = await resp.json();
    if (!data.ok) {
        showPresetMessage("预设加载失败：" + (data.error || ""));
        return;
    }

    currentPresetName = name;
    // Merge preset into currentState; preset values overwrite existing ones
    currentState = Object.assign({}, currentState, data.state || {});
    fillFormFromState();
    // Persist to backend so the overlay uses the new settings
    await saveStateToServer();
    showPresetMessage(`已应用预设「${name}」。`);
}

/**
 * Save the current state as a new preset with the name entered in the input.
 *
 * Rules:
 * - Name cannot be empty.
 * - Name must not duplicate an existing preset.
 * - Entire currentState is stored as the preset payload.
 */
async function saveCurrentAsPreset() {
    const input = document.getElementById("preset-name");
    const name = (input.value || "").trim();

    if (!name) {
        showPresetMessage("样式名称不能为空。");
        return;
    }

    // Basic duplicate-name check against current preset dropdown options
    const select = document.getElementById("preset-select");
    const exists = Array.from(select.options).some(opt => opt.value === name);
    if (exists) {
        showPresetMessage("样式名称已存在，请换一个。");
        return;
    }

    const body = {
        name: name,
        state: currentState
    };

    const resp = await fetch("/api/presets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });

    if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        if (data.error === "exists") {
            showPresetMessage("样式名称已存在。");
        } else if (data.error === "invalid_name") {
            showPresetMessage("样式名称非法（不能包含 / 或 \\）。");
        } else {
            showPresetMessage("保存失败。");
        }
        return;
    }

    showPresetMessage(`已保存为预设「${name}」。`);
    currentPresetName = name;
    await loadPresets();
    // Ensure the dropdown selects the newly saved preset
    document.getElementById("preset-select").value = name;
}

/**
 * Show a short message near the preset controls (status / error / info).
 */
function showPresetMessage(msg) {
    const el = document.getElementById("preset-message");
    if (!el) return;
    el.textContent = msg || "";
}

/**
 * Delete the currently selected preset after confirming with the user.
 */
async function deleteCurrentPreset() {
    const select = document.getElementById("preset-select");
    const name = select.value;
    if (!name) {
        showPresetMessage("当前没有选中的预设。");
        return;
    }

    const ok = window.confirm(`确定要删除预设「${name}」吗？此操作不可撤销！`);
    if (!ok) return;

    const resp = await fetch(`/api/presets/${encodeURIComponent(name)}`, {
        method: "DELETE"
    });

    if (!resp.ok) {
        showPresetMessage("删除失败。");
        return;
    }

    showPresetMessage(`已删除预设「${name}」。`);
    currentPresetName = "";
    document.getElementById("preset-select").value = "";
    await loadPresets();
}

/**
 * Populate the form inputs from the currentState object.
 *
 * This is called:
 * - After loading state from backend.
 * - After applying a preset.
 */
function fillFormFromState() {
    const fontSizeInput = document.getElementById("input-fontsize");
    const fontSizeValue = document.getElementById("fontsize-value");
    const listFontSizeInput = document.getElementById("input-list-fontsize");
    const listFontSizeValue = document.getElementById("list-fontsize-value");

    document.getElementById("input-text").value = currentState.text ?? "";

    fontSizeInput.value = currentState.fontSize ?? 42;
    if (fontSizeValue) {
        fontSizeValue.textContent = fontSizeInput.value + " px";
    }
    if (listFontSizeInput && listFontSizeValue) {
        listFontSizeInput.value = currentState.listFontSize ?? 24;
        listFontSizeValue.textContent = listFontSizeInput.value + " px";
    }

    document.getElementById("input-color").value = currentState.color ?? "#ffffff";
    document.getElementById("input-bg-opacity").value = currentState.backgroundOpacity ?? 0.4;
    document.getElementById("input-border-radius").value = currentState.borderRadius ?? 0;
    document.getElementById("input-bg-color").value = currentState.backgroundColor ?? "#000000";
    document.getElementById("opacity-value").textContent = (currentState.backgroundOpacity ?? 0.4).toFixed(2);
    document.getElementById("input-width").value = currentState.containerWidth ?? 600;
    document.getElementById("input-height").value = currentState.containerHeight ?? 300;
    document.getElementById("input-scroll-speed").value = currentState.scrollSpeed ?? 30;
    document.getElementById("input-list-color").value = currentState.listColor ?? "#ffffff";
    document.getElementById("input-text-seg-duration").value = currentState.textSegmentDuration ?? 5;

    // Map text font dropdown value back into state (family + weight)
    const textFontSel = document.getElementById("input-text-fontfamily");
    if (textFontSel) {
        const family = currentState.textFontFamily || "system";
        const weight = currentState.textFontWeight || 400;
        const composite = `${family}|${weight}`;
        const exists = Array.from(textFontSel.options).some(o => o.value === composite);
        textFontSel.value = exists ? composite : "system|400";
    }

    // Map list font dropdown value back into state (family + weight)
    const listFontSel = document.getElementById("input-list-fontfamily");
    if (listFontSel) {
        const family = currentState.listFontFamily || "system";
        const weight = currentState.listFontWeight || 400;
        const composite = `${family}|${weight}`;
        const exists = Array.from(listFontSel.options).some(o => o.value === composite);
        listFontSel.value = exists ? composite : "system|400";
    }

    // Restore groupBy selection if still valid
    const groupSelect = document.getElementById("group-by-select");
    if (groupSelect) {
        const gb = currentState.groupByColumn || "";
        const exists = Array.from(groupSelect.options).some(o => o.value === gb);
        groupSelect.value = exists ? gb : "";
    }
}

/**
 * Attach event listeners to all form inputs.
 *
 * Behavior:
 * - On each input event, update currentState from form values.
 * - Debounce calls to saveStateToServer() to avoid excessive network calls.
 * - Changing the selected column also triggers `refreshGroupByOptions`.
 */
function setupListeners() {
    const textInput = document.getElementById("input-text");
    const sizeInput = document.getElementById("input-fontsize");
    const sizeValue = document.getElementById("fontsize-value");
    const colorInput = document.getElementById("input-color");
    const textFontSel = document.getElementById("input-text-fontfamily");

    const bgInput = document.getElementById("input-bg-opacity");
    const opacityValue = document.getElementById("opacity-value");
    const borderRadiusInput = document.getElementById("input-border-radius");
    const bgColorInput = document.getElementById("input-bg-color");

    const columnSelect = document.getElementById("column-select");
    const groupSelect = document.getElementById("group-by-select");

    const presetSelect = document.getElementById("preset-select");
    const btnSavePreset = document.getElementById("btn-save-preset");
    const btnDeletePreset = document.getElementById("btn-delete-preset");

    const widthInput = document.getElementById("input-width");
    const heightInput = document.getElementById("input-height");
    const speedInput = document.getElementById("input-scroll-speed");
    const listSizeInput = document.getElementById("input-list-fontsize");
    const listSizeValue = document.getElementById("list-fontsize-value");
    const listColorInput = document.getElementById("input-list-color");
    const listFontSel = document.getElementById("input-list-fontfamily");

    const textSegDurInput = document.getElementById("input-text-seg-duration");

    // Preset dropdown: applying a different preset
    if (presetSelect) {
        presetSelect.addEventListener("change", () => {
            const name = presetSelect.value;
            applyPreset(name);
        });
    }

    // Save current state as a new preset
    if (btnSavePreset) {
        btnSavePreset.addEventListener("click", () => {
            saveCurrentAsPreset();
        });
    }

    // Delete the currently selected preset
    if (btnDeletePreset) {
        btnDeletePreset.addEventListener("click", () => {
            deleteCurrentPreset();
        });
    }

    /**
     * Handle generic input changes:
     * - Sync form values into currentState.
     * - Update "display" values (e.g., font size label).
     * - Schedule a debounced save to the backend.
     */
    function onChange() {
        currentState.text = textInput.value;
        currentState.fontSize = parseInt(sizeInput.value || "32");
        currentState.color = colorInput.value;

        currentState.backgroundOpacity = parseFloat(bgInput.value || "0.4");
        currentState.borderRadius = parseInt(borderRadiusInput.value || "0", 10);
        currentState.backgroundColor = bgColorInput.value || "#000000";

        currentState.selected_column = columnSelect.value;
        currentState.groupByColumn = groupSelect.value || "";

        currentState.containerWidth = parseInt(widthInput.value || "600", 10);
        currentState.containerHeight = parseInt(heightInput.value || "300", 10);

        currentState.scrollSpeed = parseFloat(speedInput.value || "30");
        currentState.listFontSize = parseInt(listSizeInput.value || "24", 10);
        currentState.listColor = listColorInput.value || "#ffffff";

        currentState.textSegmentDuration = parseFloat(textSegDurInput.value || "5");
        opacityValue.textContent = currentState.backgroundOpacity.toFixed(2);

        if (sizeValue) {
            sizeValue.textContent = sizeInput.value + " px";
        }
        if (listSizeValue) {
            listSizeValue.textContent = listSizeInput.value + " px";
        }
        if (textFontSel) {
            const [family, weightStr] = textFontSel.value.split("|");
            currentState.textFontFamily = family;
            currentState.textFontWeight = parseInt(weightStr || "400", 10);
        }
        if (listFontSel) {
            const [family, weightStr] = listFontSel.value.split("|");
            currentState.listFontFamily = family;
            currentState.listFontWeight = parseInt(weightStr || "400", 10);
        }

        scheduleSave();
    }

    // Register 'input' listeners for all relevant fields
    [
        textInput, sizeInput, colorInput, bgInput, bgColorInput,
        columnSelect, groupSelect, widthInput, heightInput,
        speedInput, listSizeInput, listColorInput,
        textSegDurInput, textFontSel, listFontSel, borderRadiusInput
    ].forEach(el => {
        el.addEventListener("input", onChange);
    });

    // Changing the selected column should also recalculate valid group-by options
    columnSelect.addEventListener("change", () => {
        refreshGroupByOptions();
        onChange(); // Trigger a full state update and save
    });
}

/**
 * Debounced save: schedule a saveStateToServer call after a short delay.
 */
function scheduleSave() {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(saveStateToServer, 200);
}

/**
 * Persist the currentState to the backend via /api/state.
 */
async function saveStateToServer() {
    try {
        await fetch("/api/state", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(currentState)
        });
    } catch (e) {
        console.error("Failed to save state", e);
    }
}

/**
 * Language Switcher
 */
function setupLanguageSwitcher() {
    const langSelect = document.getElementById("lang");
    if (!langSelect) return;

    function applyLang(lang) {
        // Hide all
        document.querySelectorAll("span[lang]").forEach(el => {
            el.style.display = "none";
        });

        // Show selected language
        document.querySelectorAll(`span[lang="${lang}"]`).forEach(el => {
            el.style.display = "inline";
        });
    }

    // Default: Chinese
    applyLang("chn");

    // Change handler
    langSelect.addEventListener("change", () => {
        applyLang(langSelect.value);
    });
}

/**
 * Main initialization:
 * - Load available columns.
 * - Load current state and apply to form.
 * - Load presets.
 * - Attach UI event listeners.
 */
(async function init() {
    await loadColumns();
    await loadState();
    await loadPresets();
    setupListeners();
    setupLanguageSwitcher();
})();
