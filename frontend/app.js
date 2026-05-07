((globalScope) => {
  const API_URL = "http://127.0.0.1:8000";
  const WEATHER_OPTIONS = ["normal", "warm", "cold"];
  const DEFAULT_PRESET_KEY = "baseline";
  const TODAY = new Date().toISOString().slice(0, 10);

  const PRESET_SCENARIOS = {
    baseline: {
      label: "Baseline",
      caption: "Reference planning case with calibrated baseline assumptions.",
      state: {
        template_name: "baseline",
        display_name: "Baseline",
        scenario_date: TODAY,
        description: "Reference case with historical trends",
        base_year: 2025,
        forecast_horizon: 10,
        housing_growth_rate: 0.01,
        electrification_targets: {
          space_heating: 0.02,
          hybrid_space_heating: 0.01
        },
        efficiency_targets: {
          space_heating: 0.01,
          hybrid_space_heating: 0.005
        },
        weather_assumption: "normal"
      }
    },
    high_electrification: {
      label: "High Electrification",
      caption: "Faster all-electric and hybrid adoption while preserving the calibrated template.",
      state: {
        template_name: "high_electrification",
        display_name: "High Electrification",
        scenario_date: TODAY,
        description: "Accelerated transition with stronger electrification and hybrid adoption",
        base_year: 2025,
        forecast_horizon: 10,
        housing_growth_rate: 0.013,
        electrification_targets: {
          space_heating: 0.12,
          hybrid_space_heating: 0.08
        },
        efficiency_targets: {
          space_heating: 0.015,
          hybrid_space_heating: 0.01
        },
        weather_assumption: "normal"
      }
    },
    conservative: {
      label: "Conservative",
      caption: "Slower transition pathway with lower adoption and smaller efficiency gains.",
      state: {
        template_name: "baseline",
        display_name: "Conservative",
        scenario_date: TODAY,
        description: "Slow-transition case with limited electrification and modest efficiency gains",
        base_year: 2025,
        forecast_horizon: 10,
        housing_growth_rate: 0.007,
        electrification_targets: {
          space_heating: 0.01,
          hybrid_space_heating: 0.005
        },
        efficiency_targets: {
          space_heating: 0.008,
          hybrid_space_heating: 0.004
        },
        weather_assumption: "normal"
      }
    }
  };

  const DOM_IDS = {
    presetStrip: "presetStrip",
    displayNameInput: "displayNameInput",
    scenarioDateInput: "scenarioDateInput",
    scenarioDescriptionInput: "scenarioDescriptionInput",
    baseYearInput: "baseYearInput",
    forecastHorizonInput: "forecastHorizonInput",
    housingGrowthRange: "housingGrowthRange",
    housingGrowthNumber: "housingGrowthNumber",
    weatherSelect: "weatherSelect",
    spaceHeatingElectrificationRange: "spaceHeatingElectrificationRange",
    spaceHeatingElectrificationNumber: "spaceHeatingElectrificationNumber",
    hybridHeatingAdoptionRange: "hybridHeatingAdoptionRange",
    hybridHeatingAdoptionNumber: "hybridHeatingAdoptionNumber",
    spaceHeatingEfficiencyRange: "spaceHeatingEfficiencyRange",
    spaceHeatingEfficiencyNumber: "spaceHeatingEfficiencyNumber",
    hybridHeatingEfficiencyRange: "hybridHeatingEfficiencyRange",
    hybridHeatingEfficiencyNumber: "hybridHeatingEfficiencyNumber",
    spaceHeatingElectrificationHint: "spaceHeatingElectrificationHint",
    hybridHeatingAdoptionHint: "hybridHeatingAdoptionHint",
    dirtyState: "dirtyState",
    previewModeBadge: "previewModeBadge",
    heroScenarioId: "heroScenarioId",
    heroTemplateName: "heroTemplateName",
    heroServerStatus: "heroServerStatus",
    heroActionStatus: "heroActionStatus",
    actionStatus: "actionStatus",
    summaryScenarioId: "summaryScenarioId",
    summaryWindow: "summaryWindow",
    summaryWeather: "summaryWeather",
    summaryGrowth: "summaryGrowth",
    summaryAnnualElectrification: "summaryAnnualElectrification",
    summaryAnnualHybrid: "summaryAnnualHybrid",
    validationList: "validationList",
    jsonPreview: "jsonPreview",
    saveFilenameBadge: "saveFilenameBadge",
    runScenarioButton: "runScenarioButton",
    exportScenarioButton: "exportScenarioButton",
    importScenarioButton: "importScenarioButton",
    copyPreviewButton: "copyPreviewButton",
    resetScenarioButton: "resetScenarioButton",
    scenarioImportInput: "scenarioImportInput",
    refreshScenariosButton: "refreshScenariosButton",
    primaryScenarioSelect: "primaryScenarioSelect",
    comparisonScenarioSelect: "comparisonScenarioSelect",
    loadedScenarioGrid: "loadedScenarioGrid",
    loadedScenarioNarrative: "loadedScenarioNarrative",
    comparisonGrid: "comparisonGrid",
    comparisonTable: "comparisonTable",
    chartGallery: "chartGallery"
  };

  const APP = {
    activePresetKey: DEFAULT_PRESET_KEY,
    currentState: createStateFromPreset(DEFAULT_PRESET_KEY),
    lastCommittedPayload: "",
    lastActionMessage: "Ready to build or load a scenario.",
    serverHealthy: false,
    scenarioCatalog: [],
    primaryScenarioId: "",
    comparisonScenarioId: "",
    primaryBundle: null,
    comparisonBundle: null
  };

  let dom = {};

  function safeClone(value) {
    if (typeof structuredClone === "function") {
      return structuredClone(value);
    }
    return JSON.parse(JSON.stringify(value));
  }

  function createStateFromPreset(presetKey) {
    const key = PRESET_SCENARIOS[presetKey] ? presetKey : DEFAULT_PRESET_KEY;
    return safeClone(PRESET_SCENARIOS[key].state);
  }

  function roundTo(value, decimals) {
    return Number(value.toFixed(decimals));
  }

  function clampNumber(value, min, max, fallback, decimals = 4) {
    const parsed = Number(value);
    const usable = Number.isFinite(parsed) ? parsed : fallback;
    return roundTo(Math.min(max, Math.max(min, usable)), decimals);
  }

  function clampInteger(value, min, max, fallback) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      return fallback;
    }
    return Math.min(max, Math.max(min, Math.round(parsed)));
  }

  function normalizeString(value, fallback = "") {
    const text = String(value ?? "").trim();
    return text || fallback;
  }

  function slugify(value) {
    return normalizeString(value, "scenario")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "scenario";
  }

  function formatPercent(value, digits = 1) {
    return `${(Number(value || 0) * 100).toFixed(digits)}%`;
  }

  function formatWeather(value) {
    const text = normalizeString(value, "normal").toLowerCase();
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function formatNumber(value, digits = 1) {
    if (value === undefined || value === null || value === "") {
      return "N/A";
    }
    return Number(value).toLocaleString(undefined, {
      maximumFractionDigits: digits,
      minimumFractionDigits: digits
    });
  }

  function formatBigNumber(value) {
    if (value === undefined || value === null || value === "") {
      return "N/A";
    }
    return Number(value).toLocaleString(undefined, {
      maximumFractionDigits: 0
    });
  }

  function parseDateOrBlank(value) {
    const text = normalizeString(value);
    if (!text) {
      return "";
    }
    return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : "";
  }

  function buildScenarioId(displayName, scenarioDate) {
    const slug = slugify(displayName);
    return scenarioDate ? `${slug}_${scenarioDate}` : slug;
  }

  function validateState(state) {
    const normalized = {
      template_name: normalizeString(state?.template_name, "baseline"),
      display_name: normalizeString(state?.display_name),
      scenario_date: parseDateOrBlank(state?.scenario_date),
      description: normalizeString(state?.description, "Scenario prepared in the NW Natural scenario studio."),
      base_year: clampInteger(state?.base_year, 2020, 2050, 2025),
      forecast_horizon: clampInteger(state?.forecast_horizon, 1, 50, 10),
      housing_growth_rate: clampNumber(state?.housing_growth_rate, 0, 0.05, 0.01, 4),
      electrification_targets: {
        space_heating: clampNumber(state?.electrification_targets?.space_heating, 0, 1, 0, 4),
        hybrid_space_heating: clampNumber(state?.electrification_targets?.hybrid_space_heating, 0, 1, 0, 4)
      },
      efficiency_targets: {
        space_heating: clampNumber(state?.efficiency_targets?.space_heating, 0, 0.05, 0, 4),
        hybrid_space_heating: clampNumber(state?.efficiency_targets?.hybrid_space_heating, 0, 0.05, 0, 4)
      },
      weather_assumption: WEATHER_OPTIONS.includes(state?.weather_assumption)
        ? state.weather_assumption
        : "normal"
    };

    const errors = [];
    const notes = [];

    if (!normalized.display_name) {
      errors.push("Scenario name is required.");
    }

    if (!normalized.scenario_date) {
      errors.push("Scenario date is required.");
    }

    if (!WEATHER_OPTIONS.includes(state?.weather_assumption)) {
      notes.push("Weather assumption was reset to normal.");
    }

    return {
      valid: errors.length === 0,
      errors,
      notes,
      normalized
    };
  }

  function buildConfigPayload(state) {
    const { normalized } = validateState(state);
    const horizon = Math.max(normalized.forecast_horizon, 1);
    const scenarioId = buildScenarioId(normalized.display_name, normalized.scenario_date);

    return {
      template_name: normalized.template_name,
      display_name: normalized.display_name,
      scenario_date: normalized.scenario_date,
      name: scenarioId,
      description: normalized.description,
      base_year: normalized.base_year,
      forecast_horizon: normalized.forecast_horizon,
      housing_growth_rate: normalized.housing_growth_rate,
      electrification_rate: roundTo(normalized.electrification_targets.space_heating / horizon, 4),
      hybrid_adoption_rate: roundTo(normalized.electrification_targets.hybrid_space_heating / horizon, 4),
      efficiency_improvement: normalized.efficiency_targets.space_heating,
      weather_assumption: normalized.weather_assumption,
      ui_targets: {
        electrification_rate: {
          space_heating: normalized.electrification_targets.space_heating,
          hybrid_space_heating: normalized.electrification_targets.hybrid_space_heating
        },
        efficiency_improvement: {
          space_heating: normalized.efficiency_targets.space_heating,
          hybrid_space_heating: normalized.efficiency_targets.hybrid_space_heating
        }
      }
    };
  }

  function serializePayload(payload) {
    return JSON.stringify(payload);
  }

  function setPair(rangeEl, numberEl, fractionValue, digits = 1) {
    const percentValue = roundTo(Number(fractionValue || 0) * 100, digits);
    rangeEl.value = String(percentValue);
    numberEl.value = String(percentValue);
  }

  function buildValidationItems(validation, payload) {
    const items = [
      {
        title: "Scenario identity",
        detail: validation.valid
          ? `Scenario will save as ${payload.name}.json and results will land in scenarios/${payload.name}/.`
          : "Scenario name and date are both required before export or model run."
      },
      {
        title: "Template preservation",
        detail: `This run will start from the calibrated ${payload.template_name}.json template before applying the visible frontend overrides.`
      },
      {
        title: "Annual model rates",
        detail: `GranularGas will receive ${formatPercent(payload.electrification_rate)} annual all-electric switching and ${formatPercent(payload.hybrid_adoption_rate)} annual hybrid adoption.`
      },
      {
        title: "API connection",
        detail: APP.serverHealthy
          ? "Local scenario API is reachable."
          : "Local scenario API is not responding yet. Start the server before running or browsing saved scenarios."
      }
    ];

    validation.notes.forEach((note) => {
      items.push({
        title: "Normalization note",
        detail: note
      });
    });

    return items;
  }

  function cacheDom() {
    dom = Object.fromEntries(
      Object.entries(DOM_IDS).map(([key, id]) => [key, document.getElementById(id)])
    );
  }

  function renderPresetButtons() {
    dom.presetStrip.innerHTML = "";

    Object.entries(PRESET_SCENARIOS).forEach(([key, preset]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `preset-button${key === APP.activePresetKey ? " is-active" : ""}`;
      button.innerHTML = `
        <span class="preset-button__name">${preset.label}</span>
        <span class="preset-button__caption">${preset.caption}</span>
      `;
      button.addEventListener("click", () => {
        APP.activePresetKey = key;
        APP.currentState = createStateFromPreset(key);
        APP.lastCommittedPayload = serializePayload(buildConfigPayload(APP.currentState));
        APP.lastActionMessage = `${preset.label} preset loaded.`;
        render();
      });
      dom.presetStrip.appendChild(button);
    });
  }

  function renderForm(validation) {
    const state = validation.normalized;
    dom.displayNameInput.value = APP.currentState.display_name ?? "";
    dom.scenarioDateInput.value = APP.currentState.scenario_date ?? "";
    dom.scenarioDescriptionInput.value = APP.currentState.description ?? "";
    dom.baseYearInput.value = state.base_year;
    dom.forecastHorizonInput.value = state.forecast_horizon;
    dom.weatherSelect.value = state.weather_assumption;

    setPair(dom.housingGrowthRange, dom.housingGrowthNumber, state.housing_growth_rate);
    setPair(
      dom.spaceHeatingElectrificationRange,
      dom.spaceHeatingElectrificationNumber,
      state.electrification_targets.space_heating
    );
    setPair(
      dom.hybridHeatingAdoptionRange,
      dom.hybridHeatingAdoptionNumber,
      state.electrification_targets.hybrid_space_heating
    );
    setPair(
      dom.spaceHeatingEfficiencyRange,
      dom.spaceHeatingEfficiencyNumber,
      state.efficiency_targets.space_heating
    );
    setPair(
      dom.hybridHeatingEfficiencyRange,
      dom.hybridHeatingEfficiencyNumber,
      state.efficiency_targets.hybrid_space_heating
    );
  }

  function renderCurrentSummary(validation, payload) {
    const endYear = payload.base_year + payload.forecast_horizon;
    dom.heroScenarioId.textContent = payload.name || "Scenario ID pending";
    dom.heroTemplateName.textContent = payload.template_name;
    dom.heroServerStatus.textContent = APP.serverHealthy ? "Connected" : "Offline";
    dom.heroActionStatus.textContent = APP.lastActionMessage;

    dom.summaryScenarioId.textContent = payload.name || "Scenario ID pending";
    dom.summaryWindow.textContent = `${payload.base_year}-${endYear}`;
    dom.summaryWeather.textContent = formatWeather(payload.weather_assumption);
    dom.summaryGrowth.textContent = formatPercent(payload.housing_growth_rate);
    dom.summaryAnnualElectrification.textContent = formatPercent(payload.electrification_rate);
    dom.summaryAnnualHybrid.textContent = formatPercent(payload.hybrid_adoption_rate);
    dom.spaceHeatingElectrificationHint.textContent = `Study-end target by ${endYear}; converts to ${formatPercent(payload.electrification_rate)} annual all-electric switching.`;
    dom.hybridHeatingAdoptionHint.textContent = `Study-end target by ${endYear}; converts to ${formatPercent(payload.hybrid_adoption_rate)} annual hybrid adoption.`;
    dom.saveFilenameBadge.textContent = `${payload.name || "scenario"}.json`;

    const dirty = serializePayload(payload) !== APP.lastCommittedPayload;
    dom.dirtyState.textContent = dirty ? "Unsaved Changes" : "Preset Loaded";
    dom.dirtyState.classList.toggle("is-dirty", dirty);
    dom.previewModeBadge.textContent = validation.valid ? "Run Ready" : "Missing Required Fields";
  }

  function renderValidation(validation, payload) {
    const items = buildValidationItems(validation, payload);
    dom.validationList.innerHTML = "";
    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "validation-item";
      row.innerHTML = `
        <div class="validation-item__badge">${item.title === "Scenario identity" && !validation.valid ? "!" : "OK"}</div>
        <div class="validation-item__copy">
          <span class="validation-item__title">${item.title}</span>
          <span class="validation-item__detail">${item.detail}</span>
        </div>
      `;
      dom.validationList.appendChild(row);
    });
  }

  function renderPreview(payload) {
    dom.jsonPreview.textContent = JSON.stringify(payload, null, 2);
  }

  function renderScenarioSelectors() {
    const primaryOptions = APP.scenarioCatalog.length
      ? APP.scenarioCatalog
      : [];

    dom.primaryScenarioSelect.innerHTML = primaryOptions.length
      ? primaryOptions.map((scenario) => `
          <option value="${scenario.id}" ${scenario.id === APP.primaryScenarioId ? "selected" : ""}>
            ${scenario.display_name || scenario.saved_name} (${scenario.id})
          </option>
        `).join("")
      : `<option value="">No saved scenarios found</option>`;

    const compareOptions = [
      `<option value="">None</option>`,
      ...primaryOptions.map((scenario) => `
        <option value="${scenario.id}" ${scenario.id === APP.comparisonScenarioId ? "selected" : ""}>
          ${scenario.display_name || scenario.saved_name} (${scenario.id})
        </option>
      `)
    ];

    dom.comparisonScenarioSelect.innerHTML = compareOptions.join("");
  }

  function renderLoadedScenarioSummary() {
    if (!APP.primaryBundle) {
      dom.loadedScenarioGrid.innerHTML = `
        <article class="summary-card summary-card--wide">
          <span class="summary-card__label">Saved Results</span>
          <strong>Select a saved scenario to load its summary and charts.</strong>
        </article>
      `;
      dom.loadedScenarioNarrative.textContent = "Use Refresh if you have just run the model and want to reload the scenario library.";
      return;
    }

    const scenario = APP.primaryBundle.scenario;
    const compareScenario = APP.comparisonBundle?.scenario || null;
    dom.loadedScenarioGrid.innerHTML = `
      <article class="summary-card">
        <span class="summary-card__label">Primary Scenario</span>
        <strong>${scenario.display_name}</strong>
      </article>
      <article class="summary-card">
        <span class="summary-card__label">Saved ID</span>
        <strong>${scenario.id}</strong>
      </article>
      <article class="summary-card">
        <span class="summary-card__label">Scenario Date</span>
        <strong>${scenario.scenario_date || "N/A"}</strong>
      </article>
      <article class="summary-card">
        <span class="summary-card__label">Final UPC</span>
        <strong>${formatNumber(scenario.final_upc)}</strong>
      </article>
      <article class="summary-card">
        <span class="summary-card__label">Final Total Therms</span>
        <strong>${formatBigNumber(scenario.final_total_therms)}</strong>
      </article>
      <article class="summary-card">
        <span class="summary-card__label">Final IRP Diff</span>
        <strong>${scenario.final_diff_pct !== undefined && scenario.final_diff_pct !== null ? `${formatNumber(scenario.final_diff_pct)}%` : "N/A"}</strong>
      </article>
    `;

    dom.loadedScenarioNarrative.textContent = compareScenario
      ? `Comparing ${scenario.display_name} against ${compareScenario.display_name}. The metrics and chart gallery below use the saved files in the GranularGas scenarios directory.`
      : `Loaded ${scenario.display_name}. The chart gallery below is reading the saved PNG outputs already stored in scenarios/${scenario.id}/.`;
  }

  function comparisonRows(primary, compare) {
    const metrics = [
      ["Saved ID", primary?.id, compare?.id],
      ["Final Year", primary?.latest_year, compare?.latest_year],
      ["Final Total Therms", primary?.final_total_therms, compare?.final_total_therms],
      ["Final UPC", primary?.final_upc, compare?.final_upc],
      ["Final IRP UPC", primary?.final_irp_upc, compare?.final_irp_upc],
      ["Estimated Total UPC", primary?.final_estimated_total_upc, compare?.final_estimated_total_upc],
      ["IRP Diff %", primary?.final_diff_pct, compare?.final_diff_pct]
    ];

    return metrics.map(([label, left, right]) => {
      const numericLeft = Number(left);
      const numericRight = Number(right);
      const bothNumeric = Number.isFinite(numericLeft) && Number.isFinite(numericRight);
      const delta = bothNumeric ? numericLeft - numericRight : null;
      return {
        label,
        left,
        right,
        delta
      };
    });
  }

  function formatMetricValue(label, value) {
    if (value === undefined || value === null || value === "") {
      return "N/A";
    }
    if (label.includes("Therms")) {
      return formatBigNumber(value);
    }
    if (label.includes("Diff %")) {
      return `${formatNumber(value)}%`;
    }
    if (label.includes("UPC")) {
      return formatNumber(value);
    }
    return String(value);
  }

  function renderComparison() {
    if (!APP.primaryBundle) {
      dom.comparisonGrid.innerHTML = `
        <article class="metric-card metric-card--wide">
          <h3>Scenario comparison</h3>
          <p class="placeholder-text">Select a primary scenario from the saved results browser to compare final metrics.</p>
        </article>
      `;
      dom.comparisonTable.querySelector("tbody").innerHTML = "";
      return;
    }

    const primary = APP.primaryBundle.scenario;
    const compare = APP.comparisonBundle?.scenario || null;

    dom.comparisonGrid.innerHTML = compare
      ? `
        <article class="metric-card">
          <h3>Primary Final UPC</h3>
          <p class="metric-value">${formatNumber(primary.final_upc)}</p>
        </article>
        <article class="metric-card">
          <h3>Compare Final UPC</h3>
          <p class="metric-value">${formatNumber(compare.final_upc)}</p>
        </article>
        <article class="metric-card">
          <h3>UPC Delta</h3>
          <p class="metric-value">${formatNumber(Number(primary.final_upc) - Number(compare.final_upc))}</p>
        </article>
      `
      : `
        <article class="metric-card">
          <h3>Final Total Therms</h3>
          <p class="metric-value">${formatBigNumber(primary.final_total_therms)}</p>
        </article>
        <article class="metric-card">
          <h3>Final UPC</h3>
          <p class="metric-value">${formatNumber(primary.final_upc)}</p>
        </article>
        <article class="metric-card">
          <h3>Final IRP Diff</h3>
          <p class="metric-value">${primary.final_diff_pct !== undefined && primary.final_diff_pct !== null ? `${formatNumber(primary.final_diff_pct)}%` : "N/A"}</p>
        </article>
      `;

    const rows = comparisonRows(primary, compare);
    dom.comparisonTable.querySelector("tbody").innerHTML = rows.map((row) => `
      <tr>
        <td>${row.label}</td>
        <td>${formatMetricValue(row.label, row.left)}</td>
        <td>${compare ? formatMetricValue(row.label, row.right) : "N/A"}</td>
        <td>${compare && row.delta !== null ? formatMetricValue(row.label, row.delta) : "N/A"}</td>
      </tr>
    `).join("");
  }

  function buildChartMap(bundle) {
    const map = new Map();
    (bundle?.charts || []).forEach((chart) => {
      map.set(chart.key, chart);
    });
    return map;
  }

  function renderChartGallery() {
    if (!APP.primaryBundle) {
      dom.chartGallery.innerHTML = `
        <div class="chart-empty-state">
          <p>Select a saved scenario to load its result charts from the GranularGas scenarios folder.</p>
        </div>
      `;
      return;
    }

    const primaryCharts = buildChartMap(APP.primaryBundle);
    const compareCharts = buildChartMap(APP.comparisonBundle);
    const chartKeys = Array.from(new Set([
      ...primaryCharts.keys(),
      ...compareCharts.keys()
    ]));

    if (!chartKeys.length) {
      dom.chartGallery.innerHTML = `
        <div class="chart-empty-state">
          <p>No saved chart PNGs were found for the selected scenario.</p>
        </div>
      `;
      return;
    }

    dom.chartGallery.innerHTML = chartKeys.map((key) => {
      const primaryChart = primaryCharts.get(key);
      const compareChart = compareCharts.get(key);
      const label = primaryChart?.label || compareChart?.label || key;

      if (APP.comparisonBundle) {
        return `
          <article class="chart-compare-card">
            <h3>${label}</h3>
            <div class="chart-compare-grid">
              <div class="chart-frame">
                <span class="chart-frame__label">${APP.primaryBundle.scenario.display_name}</span>
                ${primaryChart ? `<img src="${API_URL}${primaryChart.url}" alt="${label} for ${APP.primaryBundle.scenario.display_name}">` : `<div class="chart-missing">Chart not available</div>`}
              </div>
              <div class="chart-frame">
                <span class="chart-frame__label">${APP.comparisonBundle.scenario.display_name}</span>
                ${compareChart ? `<img src="${API_URL}${compareChart.url}" alt="${label} for ${APP.comparisonBundle.scenario.display_name}">` : `<div class="chart-missing">Chart not available</div>`}
              </div>
            </div>
          </article>
        `;
      }

      return `
        <article class="chart-card">
          <h3>${label}</h3>
          ${primaryChart ? `<img src="${API_URL}${primaryChart.url}" alt="${label} for ${APP.primaryBundle.scenario.display_name}">` : `<div class="chart-missing">Chart not available</div>`}
        </article>
      `;
    }).join("");
  }

  function render() {
    const validation = validateState(APP.currentState);
    const payload = buildConfigPayload(APP.currentState);

    renderPresetButtons();
    renderForm(validation);
    renderCurrentSummary(validation, payload);
    renderValidation(validation, payload);
    renderPreview(payload);
    renderScenarioSelectors();
    renderLoadedScenarioSummary();
    renderComparison();
    renderChartGallery();
  }

  function updateState(mutator, actionMessage) {
    mutator(APP.currentState);
    APP.lastActionMessage = actionMessage || "Scenario updated.";
    render();
  }

  function updatePercentField(setter, rawPercentValue, maxPercent) {
    const parsed = Number(rawPercentValue);
    const safePercent = Number.isFinite(parsed) ? Math.min(maxPercent, Math.max(0, parsed)) : 0;
    const fraction = roundTo(safePercent / 100, 4);
    updateState((state) => setter(state, fraction));
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(`${API_URL}${url}`, {
      headers: {
        "Content-Type": "application/json"
      },
      ...options
    });

    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};
    if (!response.ok) {
      const message = payload?.error || "API request failed.";
      throw new Error(message);
    }
    return payload;
  }

  async function refreshScenarioCatalog(preferredScenarioId = APP.primaryScenarioId) {
    try {
      const scenarios = await fetchJson("/api/scenarios");
      APP.scenarioCatalog = scenarios;

      if (!APP.primaryScenarioId && scenarios.length) {
        APP.primaryScenarioId = preferredScenarioId || scenarios[0].id;
      } else if (preferredScenarioId) {
        APP.primaryScenarioId = preferredScenarioId;
      }

      if (APP.primaryScenarioId) {
        await loadPrimaryScenario(APP.primaryScenarioId);
      } else {
        APP.primaryBundle = null;
      }

      if (APP.comparisonScenarioId) {
        await loadComparisonScenario(APP.comparisonScenarioId);
      }

      APP.lastActionMessage = scenarios.length
        ? "Saved scenarios refreshed from the GranularGas scenarios folder."
        : "No saved scenario result folders were found yet.";
      render();
    } catch (error) {
      APP.lastActionMessage = `Could not refresh saved scenarios: ${error.message}`;
      APP.scenarioCatalog = [];
      APP.primaryBundle = null;
      APP.comparisonBundle = null;
      render();
    }
  }

  async function checkServerHealth() {
    try {
      await fetchJson("/api/health");
      APP.serverHealthy = true;
    } catch (error) {
      APP.serverHealthy = false;
      APP.lastActionMessage = "Local scenario API is offline. Start the Python server to run or browse scenarios.";
    }
    render();
  }

  async function loadPrimaryScenario(scenarioId) {
    if (!scenarioId) {
      APP.primaryBundle = null;
      render();
      return;
    }
    APP.primaryScenarioId = scenarioId;
    APP.primaryBundle = await fetchJson(`/api/results/${encodeURIComponent(scenarioId)}`);
    render();
  }

  async function loadComparisonScenario(scenarioId) {
    if (!scenarioId) {
      APP.comparisonScenarioId = "";
      APP.comparisonBundle = null;
      render();
      return;
    }
    if (scenarioId === APP.primaryScenarioId) {
      APP.lastActionMessage = "Choose a different comparison scenario to avoid comparing a run against itself.";
      APP.comparisonScenarioId = "";
      APP.comparisonBundle = null;
      render();
      return;
    }
    APP.comparisonScenarioId = scenarioId;
    APP.comparisonBundle = await fetchJson(`/api/results/${encodeURIComponent(scenarioId)}`);
    render();
  }

  function downloadPayload(filename, payload) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    const objectUrl = URL.createObjectURL(blob);

    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(objectUrl);
  }

  function importStateFromPayload(payload) {
    const forecastHorizon = clampInteger(payload?.forecast_horizon, 1, 50, 10);
    const uiTargets = payload?.ui_targets || {};
    const electrificationTargets = uiTargets.electrification_rate || {};
    const efficiencyTargets = uiTargets.efficiency_improvement || {};

    const allElectricTarget = electrificationTargets.space_heating !== undefined
      ? clampNumber(electrificationTargets.space_heating, 0, 1, 0, 4)
      : clampNumber((payload?.electrification_rate || 0) * forecastHorizon, 0, 1, 0, 4);

    const hybridTarget = electrificationTargets.hybrid_space_heating !== undefined
      ? clampNumber(electrificationTargets.hybrid_space_heating, 0, 1, 0, 4)
      : clampNumber((payload?.hybrid_adoption_rate || 0) * forecastHorizon, 0, 1, 0, 4);

    const spaceEfficiency = efficiencyTargets.space_heating !== undefined
      ? clampNumber(efficiencyTargets.space_heating, 0, 0.05, 0, 4)
      : clampNumber(payload?.efficiency_improvement, 0, 0.05, 0, 4);

    const hybridEfficiency = efficiencyTargets.hybrid_space_heating !== undefined
      ? clampNumber(efficiencyTargets.hybrid_space_heating, 0, 0.05, spaceEfficiency, 4)
      : spaceEfficiency;

    const displayName = normalizeString(
      payload?.display_name || payload?.scenario_display_name || payload?.name,
      "Imported Scenario"
    );
    const parsedDate = parseDateOrBlank(payload?.scenario_date || "");
    const fallbackNameMatch = normalizeString(payload?.name).match(/^(.*)_(\d{4}-\d{2}-\d{2})$/);

    return {
      template_name: normalizeString(payload?.template_name, "baseline"),
      display_name: fallbackNameMatch ? fallbackNameMatch[1].replace(/_/g, " ") : displayName,
      scenario_date: parsedDate || (fallbackNameMatch ? fallbackNameMatch[2] : TODAY),
      description: normalizeString(payload?.description, "Imported scenario"),
      base_year: clampInteger(payload?.base_year, 2020, 2050, 2025),
      forecast_horizon: forecastHorizon,
      housing_growth_rate: clampNumber(payload?.housing_growth_rate, 0, 0.05, 0.01, 4),
      electrification_targets: {
        space_heating: allElectricTarget,
        hybrid_space_heating: hybridTarget
      },
      efficiency_targets: {
        space_heating: spaceEfficiency,
        hybrid_space_heating: hybridEfficiency
      },
      weather_assumption: WEATHER_OPTIONS.includes(payload?.weather_assumption)
        ? payload.weather_assumption
        : "normal"
    };
  }

  async function handleRunScenario() {
    const validation = validateState(APP.currentState);
    if (!validation.valid) {
      APP.lastActionMessage = validation.errors.join(" ");
      render();
      return;
    }

    if (!APP.serverHealthy) {
      APP.lastActionMessage = "The local scenario API is offline. Start the Python server first.";
      render();
      return;
    }

    const payload = buildConfigPayload(APP.currentState);
    APP.lastActionMessage = `Running ${payload.name} and saving results into the GranularGas scenarios folder...`;
    render();

    try {
      const bundle = await fetchJson("/api/forecast", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      APP.lastCommittedPayload = serializePayload(payload);
      APP.primaryScenarioId = bundle.scenario.id;
      APP.primaryBundle = bundle;
      APP.comparisonBundle = null;
      APP.comparisonScenarioId = "";
      APP.lastActionMessage = `Model run complete. Saved ${bundle.scenario.id}.json and results in scenarios/${bundle.scenario.id}/.`;
      await refreshScenarioCatalog(bundle.scenario.id);
    } catch (error) {
      APP.lastActionMessage = `Model run failed: ${error.message}`;
      render();
    }
  }

  function handleExportScenario() {
    const validation = validateState(APP.currentState);
    if (!validation.valid) {
      APP.lastActionMessage = validation.errors.join(" ");
      render();
      return;
    }

    const payload = buildConfigPayload(APP.currentState);
    downloadPayload(`${payload.name}.json`, payload);
    APP.lastCommittedPayload = serializePayload(payload);
    APP.lastActionMessage = `Exported ${payload.name}.json.`;
    render();
  }

  async function handleCopyPreview() {
    const payload = buildConfigPayload(APP.currentState);
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      APP.lastActionMessage = "Clipboard access is not available in this browser context.";
      render();
      return;
    }

    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      APP.lastActionMessage = "Preview copied to the clipboard.";
    } catch (error) {
      APP.lastActionMessage = "Copy was blocked by the browser.";
    }
    render();
  }

  function handleResetScenario() {
    const key = APP.activePresetKey || DEFAULT_PRESET_KEY;
    APP.currentState = createStateFromPreset(key);
    APP.lastCommittedPayload = serializePayload(buildConfigPayload(APP.currentState));
    APP.lastActionMessage = `${PRESET_SCENARIOS[key].label} preset restored.`;
    render();
  }

  async function handleScenarioImport(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      const payload = JSON.parse(await file.text());
      APP.currentState = importStateFromPayload(payload);
      APP.activePresetKey = null;
      APP.lastCommittedPayload = serializePayload(buildConfigPayload(APP.currentState));
      APP.lastActionMessage = `Imported ${file.name}.`;
    } catch (error) {
      APP.lastActionMessage = `Import failed: ${error.message}`;
    } finally {
      event.target.value = "";
      render();
    }
  }

  function wireEvents() {
    dom.displayNameInput.addEventListener("input", (event) => {
      updateState((state) => {
        state.display_name = event.target.value;
      }, "Scenario name updated.");
    });

    dom.scenarioDateInput.addEventListener("input", (event) => {
      updateState((state) => {
        state.scenario_date = event.target.value;
      }, "Scenario date updated.");
    });

    dom.scenarioDescriptionInput.addEventListener("input", (event) => {
      updateState((state) => {
        state.description = event.target.value;
      }, "Scenario description updated.");
    });

    dom.baseYearInput.addEventListener("input", (event) => {
      updateState((state) => {
        state.base_year = Number(event.target.value);
      });
    });

    dom.forecastHorizonInput.addEventListener("input", (event) => {
      updateState((state) => {
        state.forecast_horizon = Number(event.target.value);
      });
    });

    dom.weatherSelect.addEventListener("change", (event) => {
      updateState((state) => {
        state.weather_assumption = event.target.value;
      }, `Weather assumption updated to ${formatWeather(event.target.value)}.`);
    });

    const bindPercentPair = (rangeEl, numberEl, setter, maxPercent) => {
      const handler = (event) => {
        updatePercentField(setter, event.target.value, maxPercent);
      };
      rangeEl.addEventListener("input", handler);
      numberEl.addEventListener("input", handler);
    };

    bindPercentPair(dom.housingGrowthRange, dom.housingGrowthNumber, (state, value) => {
      state.housing_growth_rate = value;
    }, 5);

    bindPercentPair(dom.spaceHeatingElectrificationRange, dom.spaceHeatingElectrificationNumber, (state, value) => {
      state.electrification_targets.space_heating = value;
    }, 100);

    bindPercentPair(dom.hybridHeatingAdoptionRange, dom.hybridHeatingAdoptionNumber, (state, value) => {
      state.electrification_targets.hybrid_space_heating = value;
    }, 100);

    bindPercentPair(dom.spaceHeatingEfficiencyRange, dom.spaceHeatingEfficiencyNumber, (state, value) => {
      state.efficiency_targets.space_heating = value;
    }, 5);

    bindPercentPair(dom.hybridHeatingEfficiencyRange, dom.hybridHeatingEfficiencyNumber, (state, value) => {
      state.efficiency_targets.hybrid_space_heating = value;
    }, 5);

    dom.runScenarioButton.addEventListener("click", handleRunScenario);
    dom.exportScenarioButton.addEventListener("click", handleExportScenario);
    dom.copyPreviewButton.addEventListener("click", handleCopyPreview);
    dom.resetScenarioButton.addEventListener("click", handleResetScenario);
    dom.importScenarioButton.addEventListener("click", () => dom.scenarioImportInput.click());
    dom.scenarioImportInput.addEventListener("change", handleScenarioImport);
    dom.refreshScenariosButton.addEventListener("click", () => refreshScenarioCatalog());

    dom.primaryScenarioSelect.addEventListener("change", async (event) => {
      APP.primaryScenarioId = event.target.value;
      await loadPrimaryScenario(APP.primaryScenarioId);
    });

    dom.comparisonScenarioSelect.addEventListener("change", async (event) => {
      APP.comparisonScenarioId = event.target.value;
      await loadComparisonScenario(APP.comparisonScenarioId);
    });
  }

  async function init() {
    if (typeof document === "undefined") {
      return;
    }

    if (!document.getElementById(DOM_IDS.presetStrip)) {
      return;
    }

    cacheDom();
    APP.lastCommittedPayload = serializePayload(buildConfigPayload(APP.currentState));
    wireEvents();
    render();
    await checkServerHealth();
    if (APP.serverHealthy) {
      await refreshScenarioCatalog();
    }
  }

  globalScope.NWScenarioDashboard = {
    init,
    buildConfigPayload,
    validateState
  };

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", init);
  }
})(typeof window !== "undefined" ? window : globalThis);
