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
      const isEndUse = key === "enduse_breakdown";
      const isEstUpc = key === "estimated_total_upc";
      const isModelVsIrp = key === "model_vs_irp";
      const isTotalDemand = key === "total_demand";
      const isSegmentDemand = key === "segment_demand";

      if (APP.comparisonBundle) {
        const primarySrc = primaryChart ? `${API_URL}${primaryChart.url}` : null;
        const compareSrc = compareChart ? `${API_URL}${compareChart.url}` : null;
        const primaryLabel = `${label} — ${APP.primaryBundle.scenario.display_name}`;
        const compareLabel = `${label} — ${APP.comparisonBundle.scenario.display_name}`;

        return `
          <article class="chart-compare-card">
            <div class="chart-card__header">
              <h3>${label}</h3>
              ${isEndUse ? `<button class="button button--ghost chart-overlay-btn" id="endUseOverlayButton" type="button">End Use Comparison</button>` : ""}
              ${isEstUpc ? `<button class="button button--ghost chart-overlay-btn" id="estUpcOverlayButton" type="button">UPC Comparison</button>` : ""}
              ${isModelVsIrp ? `<button class="button button--ghost chart-overlay-btn" id="irpDeclineOverlayButton" type="button">Decline Rate Comparison</button>` : ""}
              ${isTotalDemand ? `<button class="button button--ghost chart-overlay-btn" id="totalDemandOverlayButton" type="button">Total Comparison</button>` : ""}
              ${isSegmentDemand ? `<button class="button button--ghost chart-overlay-btn" id="segmentDemandOverlayButton" type="button">Segment Comparison</button>` : ""}
            </div>
            <div class="chart-compare-grid">
              <div class="chart-frame">
                <span class="chart-frame__label">${APP.primaryBundle.scenario.display_name}</span>
                ${primarySrc
                  ? `<img src="${primarySrc}" alt="${primaryLabel}" data-lightbox-src="${primarySrc}" data-lightbox-label="${primaryLabel}">`
                  : `<div class="chart-missing">Chart not available</div>`}
              </div>
              <div class="chart-frame">
                <span class="chart-frame__label">${APP.comparisonBundle.scenario.display_name}</span>
                ${compareSrc
                  ? `<img src="${compareSrc}" alt="${compareLabel}" data-lightbox-src="${compareSrc}" data-lightbox-label="${compareLabel}">`
                  : `<div class="chart-missing">Chart not available</div>`}
              </div>
            </div>
          </article>
        `;
      }

      const src = primaryChart ? `${API_URL}${primaryChart.url}` : null;
      const altLabel = `${label} — ${APP.primaryBundle.scenario.display_name}`;

      return `
        <article class="chart-card">
          <div class="chart-card__header">
            <h3>${label}</h3>
            ${isEndUse ? `<button class="button button--ghost chart-overlay-btn" id="endUseOverlayButton" type="button">End Use Comparison</button>` : ""}
            ${isEstUpc ? `<button class="button button--ghost chart-overlay-btn" id="estUpcOverlayButton" type="button">UPC Comparison</button>` : ""}
            ${isModelVsIrp ? `<button class="button button--ghost chart-overlay-btn" id="irpDeclineOverlayButton" type="button">Decline Rate Comparison</button>` : ""}
            ${isTotalDemand ? `<button class="button button--ghost chart-overlay-btn" id="totalDemandOverlayButton" type="button">Total Comparison</button>` : ""}
            ${isSegmentDemand ? `<button class="button button--ghost chart-overlay-btn" id="segmentDemandOverlayButton" type="button">Segment Comparison</button>` : ""}
          </div>
          ${src
            ? `<img src="${src}" alt="${altLabel}" data-lightbox-src="${src}" data-lightbox-label="${altLabel}">`
            : `<div class="chart-missing">Chart not available</div>`}
        </article>
      `;
    }).join("");

    // Wire overlay buttons if rendered
    const overlayBtn = document.getElementById("endUseOverlayButton");
    if (overlayBtn) overlayBtn.addEventListener("click", openEndUseOverlay);

    const estUpcBtn = document.getElementById("estUpcOverlayButton");
    if (estUpcBtn) estUpcBtn.addEventListener("click", openEstUpcOverlay);

    const irpDeclineBtn = document.getElementById("irpDeclineOverlayButton");
    if (irpDeclineBtn) irpDeclineBtn.addEventListener("click", openIrpDeclineOverlay);

    const totalDemandBtn = document.getElementById("totalDemandOverlayButton");
    if (totalDemandBtn) totalDemandBtn.addEventListener("click", openTotalDemandOverlay);

    const segmentDemandBtn = document.getElementById("segmentDemandOverlayButton");
    if (segmentDemandBtn) segmentDemandBtn.addEventListener("click", openSegmentDemandOverlay);

    attachChartClickHandlers();
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

  function showToast(message, type = "success", detail = "") {
    const existing = document.getElementById("runToast");
    if (existing) {
      existing.remove();
    }

    const toast = document.createElement("div");
    toast.id = "runToast";
    toast.className = `run-toast run-toast--${type}`;
    toast.setAttribute("role", type === "processing" ? "status" : "alert");
    toast.setAttribute("aria-live", "assertive");

    let icon;
    if (type === "success") {
      icon = `<span class="run-toast__icon">✓</span>`;
    } else if (type === "processing") {
      icon = `<span class="run-toast__icon run-toast__icon--spinner" aria-hidden="true"></span>`;
    } else {
      icon = `<span class="run-toast__icon">✕</span>`;
    }

    toast.innerHTML = `
      ${icon}
      <div class="run-toast__body">
        <span class="run-toast__message">${message}</span>
        ${detail ? `<span class="run-toast__detail">${detail}</span>` : ""}
        ${type === "processing" ? `<span class="run-toast__timer" id="runToastTimer">0s</span>` : ""}
      </div>
      ${type !== "processing" ? `<button class="run-toast__close" aria-label="Dismiss">&times;</button>` : ""}
    `;

    if (type !== "processing") {
      toast.querySelector(".run-toast__close").addEventListener("click", () => toast.remove());
    }

    document.body.appendChild(toast);

    if (type === "processing") {
      // Tick a live elapsed-time counter
      const startTime = Date.now();
      const timerEl = document.getElementById("runToastTimer");
      const interval = setInterval(() => {
        if (!timerEl || !timerEl.parentNode) {
          clearInterval(interval);
          return;
        }
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        timerEl.textContent = elapsed < 60
          ? `${elapsed}s`
          : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`;
      }, 1000);
      toast._timerInterval = interval;
    } else {
      // Auto-dismiss: 8 s for success, 20 s for errors
      const ttl = type === "success" ? 8000 : 20000;
      setTimeout(() => {
        if (toast.parentNode) {
          toast.classList.add("run-toast--fade");
          setTimeout(() => toast.remove(), 400);
        }
      }, ttl);
    }

    return toast;
  }

  function dismissProcessingToast() {
    const toast = document.getElementById("runToast");
    if (toast && toast._timerInterval) {
      clearInterval(toast._timerInterval);
    }
    if (toast) {
      toast.remove();
    }
  }

  async function handleRunScenario() {
    const validation = validateState(APP.currentState);
    if (!validation.valid) {
      const msg = validation.errors.join(" ");
      APP.lastActionMessage = msg;
      showToast(msg, "error");
      render();
      return;
    }

    if (!APP.serverHealthy) {
      const msg = "The local scenario API is offline. Start the Python server first.";
      APP.lastActionMessage = msg;
      showToast(msg, "error");
      render();
      return;
    }

    const payload = buildConfigPayload(APP.currentState);
    APP.lastActionMessage = `Running ${payload.name}…`;
    if (dom.runScenarioButton) {
      dom.runScenarioButton.disabled = true;
      dom.runScenarioButton.textContent = "Running…";
    }

    showToast(`Running ${payload.name}…`, "processing", "The model is running on the backend. This may take a minute.");
    render();

    try {
      const bundle = await fetchJson("/api/forecast", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      dismissProcessingToast();
      APP.lastCommittedPayload = serializePayload(payload);
      APP.primaryScenarioId = bundle.scenario.id;
      APP.primaryBundle = bundle;
      APP.comparisonBundle = null;
      APP.comparisonScenarioId = "";
      APP.lastActionMessage = `Model run complete. Saved ${bundle.scenario.id}.`;
      showToast(`Run complete — ${bundle.scenario.id}`, "success", `Results saved to scenarios/${bundle.scenario.id}/`);
      await refreshScenarioCatalog(bundle.scenario.id);
    } catch (error) {
      dismissProcessingToast();
      // Try to extract structured detail from the server's 500 response
      let detail = "";
      try {
        const parsed = JSON.parse(error.message);
        if (parsed?.details?.stderr) {
          detail = parsed.details.stderr.trim().split("\n").slice(-6).join("\n");
        } else if (parsed?.details?.message) {
          detail = parsed.details.message;
        } else if (typeof parsed?.details === "string") {
          detail = parsed.details;
        }
      } catch {
        detail = error.message;
      }
      const summary = "Model run failed — check the detail below and the server console for the full traceback.";
      APP.lastActionMessage = `Model run failed: ${error.message}`;
      showToast(summary, "error", detail);
      render();
    } finally {
      if (dom.runScenarioButton) {
        dom.runScenarioButton.disabled = false;
        dom.runScenarioButton.textContent = "Run Scenario";
      }
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
    function on(el, event, handler) {
      if (el) {
        el.addEventListener(event, handler);
      }
    }

    on(dom.displayNameInput, "input", (event) => {
      updateState((state) => {
        state.display_name = event.target.value;
      }, "Scenario name updated.");
    });

    on(dom.scenarioDateInput, "input", (event) => {
      updateState((state) => {
        state.scenario_date = event.target.value;
      }, "Scenario date updated.");
    });

    on(dom.scenarioDescriptionInput, "input", (event) => {
      updateState((state) => {
        state.description = event.target.value;
      }, "Scenario description updated.");
    });

    on(dom.baseYearInput, "input", (event) => {
      updateState((state) => {
        state.base_year = Number(event.target.value);
      });
    });

    on(dom.forecastHorizonInput, "input", (event) => {
      updateState((state) => {
        state.forecast_horizon = Number(event.target.value);
      });
    });

    on(dom.weatherSelect, "change", (event) => {
      updateState((state) => {
        state.weather_assumption = event.target.value;
      }, `Weather assumption updated to ${formatWeather(event.target.value)}.`);
    });

    const bindPercentPair = (rangeEl, numberEl, setter, maxPercent) => {
      const handler = (event) => {
        updatePercentField(setter, event.target.value, maxPercent);
      };
      on(rangeEl, "input", handler);
      on(numberEl, "input", handler);
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

    on(dom.runScenarioButton, "click", handleRunScenario);
    on(dom.exportScenarioButton, "click", handleExportScenario);
    on(dom.copyPreviewButton, "click", handleCopyPreview);
    on(dom.resetScenarioButton, "click", handleResetScenario);
    on(dom.importScenarioButton, "click", () => dom.scenarioImportInput && dom.scenarioImportInput.click());
    on(dom.scenarioImportInput, "change", handleScenarioImport);
    on(dom.refreshScenariosButton, "click", () => refreshScenarioCatalog());

    on(dom.primaryScenarioSelect, "change", async (event) => {
      APP.primaryScenarioId = event.target.value;
      await loadPrimaryScenario(APP.primaryScenarioId);
    });

    on(dom.comparisonScenarioSelect, "change", async (event) => {
      APP.comparisonScenarioId = event.target.value;
      await loadComparisonScenario(APP.comparisonScenarioId);
    });
  }

  // ── Lightbox ──────────────────────────────────────────────────────────────

  const LIGHTBOX = {
    el: null,
    img: null,
    caption: null
  };

  function openLightbox(src, label) {
    if (!LIGHTBOX.el) {
      return;
    }
    LIGHTBOX.img.src = src;
    LIGHTBOX.img.alt = label;
    LIGHTBOX.caption.textContent = label;
    LIGHTBOX.el.hidden = false;
    document.body.style.overflow = "hidden";
    LIGHTBOX.el.querySelector(".lightbox__close").focus();
  }

  function closeLightbox() {
    if (!LIGHTBOX.el) {
      return;
    }
    LIGHTBOX.el.hidden = true;
    LIGHTBOX.img.src = "";
    document.body.style.overflow = "";
  }

  function wireLightbox() {
    LIGHTBOX.el = document.getElementById("chartLightbox");
    LIGHTBOX.img = document.getElementById("lightboxImg");
    LIGHTBOX.caption = document.getElementById("lightboxCaption");

    if (!LIGHTBOX.el) {
      return;
    }

    document.getElementById("lightboxClose").addEventListener("click", closeLightbox);
    document.getElementById("lightboxBackdrop").addEventListener("click", closeLightbox);

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !LIGHTBOX.el.hidden) {
        closeLightbox();
      }
    });
  }

  function attachChartClickHandlers() {
    dom.chartGallery.querySelectorAll("img[data-lightbox-src]").forEach((img) => {
      img.addEventListener("click", () => {
        openLightbox(img.dataset.lightboxSrc, img.dataset.lightboxLabel || img.alt);
      });
    });
  }

  // ── End Use Overlay Chart ─────────────────────────────────────────────────

  // Palette for all 6 end uses
  const END_USE_COLORS = {
    space_heating:  "#4ecdc4",
    water_heating:  "#f7b731",
    cooking:        "#fd79a8",
    clothes_drying: "#a29bfe",
    fireplace:      "#ff7675",
    other:          "#81ecec"
  };

  // Two distinct palettes for the overlay chart
  // Primary: cool blue-green family
  const END_USE_COLORS_PRIMARY = {
    space_heating:  "#00b4d8",
    water_heating:  "#48cae4",
    cooking:        "#90e0ef",
    clothes_drying: "#0077b6",
    fireplace:      "#023e8a",
    other:          "#ade8f4"
  };
  // Comparison: warm orange-red family
  const END_USE_COLORS_COMPARE = {
    space_heating:  "#e85d04",
    water_heating:  "#f48c06",
    cooking:        "#faa307",
    clothes_drying: "#dc2f02",
    fireplace:      "#9d0208",
    other:          "#ffba08"
  };

  const END_USE_LABELS = {
    space_heating:  "Space Heating",
    water_heating:  "Water Heating",
    cooking:        "Cooking",
    clothes_drying: "Clothes Drying",
    fireplace:      "Fireplace",
    other:          "Other"
  };

  const END_USES = ["space_heating", "water_heating", "cooking", "clothes_drying", "fireplace", "other"];

  function buildEndUseSeriesFromBundle(bundle) {
    // Prefer estimated_total_upc which has actual per-end-use UPC values per year
    const euData = bundle.estimated_total_upc || [];
    if (euData.length) {
      return euData
        .slice()
        .sort((a, b) => a.year - b.year)
        .map((row) => ({
          year:           row.year,
          space_heating:  row.space_heating  || 0,
          water_heating:  row.water_heating  || 0,
          cooking:        row.cooking        || 0,
          clothes_drying: row.clothes_drying || 0,
          fireplace:      row.fireplace      || 0,
          other:          row.other          || 0
        }));
    }

    // Fallback: estimate from RECS percentages × UPC if estimated_total_upc is missing
    const recs = (bundle.recs_enduse_trend || []);
    const latestRecs = recs.length ? recs[recs.length - 1] : null;
    const shPct  = latestRecs ? (latestRecs.sh_pct  || 0) / 100 : 0.55;
    const whPct  = latestRecs ? (latestRecs.wh_pct  || 0) / 100 : 0.33;
    const appPct = latestRecs ? (latestRecs.appliance_pct || 0) / 100 : 0.12;

    return (bundle.yearly_summary || [])
      .slice()
      .sort((a, b) => a.year - b.year)
      .map((row) => {
        const upc = row.use_per_customer || 0;
        return {
          year:           row.year,
          space_heating:  upc * shPct,
          water_heating:  upc * whPct,
          cooking:        upc * appPct * 0.4,
          clothes_drying: upc * appPct * 0.25,
          fireplace:      upc * appPct * 0.2,
          other:          upc * appPct * 0.15
        };
      });
  }

  function drawEndUseOverlay(primaryBundle, compareBundle) {
    const canvas = document.getElementById("endUseCanvas");
    const legend = document.getElementById("endUseLegend");
    const title  = document.getElementById("endUseLightboxTitle");
    if (!canvas) return;

    const primaryName = primaryBundle.scenario.display_name;
    const compareName = compareBundle ? compareBundle.scenario.display_name : null;

    title.textContent = compareName
      ? `End Use Breakdown — ${primaryName} vs ${compareName}`
      : `End Use Breakdown — ${primaryName}`;

    const primarySeries = buildEndUseSeriesFromBundle(primaryBundle);
    const compareSeries = compareBundle ? buildEndUseSeriesFromBundle(compareBundle) : null;
    const endUses = END_USES;

    // Y-max = highest stacked total across both series
    let yMax = 0;
    [...primarySeries, ...(compareSeries || [])].forEach((row) => {
      const total = endUses.reduce((s, eu) => s + (row[eu] || 0), 0);
      if (total > yMax) yMax = total;
    });
    yMax = yMax * 1.1 || 1;

    // ── Canvas sizing ─────────────────────────────────────────────────────
    const dpr = window.devicePixelRatio || 1;
    const W = Math.round(Math.min(window.innerWidth * 0.96, 1400) - 64 - 180 - 24);
    const H = Math.round(window.innerHeight * 0.78);

    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width  = `${W}px`;
    canvas.style.height = `${H}px`;

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    const PAD_TOP  = 36;
    const PAD_BOT  = 52;
    const PAD_LEFT = 72;
    const PAD_RIGHT = 16;
    const chartW = W - PAD_LEFT - PAD_RIGHT;
    const chartH = H - PAD_TOP - PAD_BOT;

    // Use the union of years from both series for the shared X axis
    const allYears = Array.from(new Set([
      ...primarySeries.map((r) => r.year),
      ...(compareSeries ? compareSeries.map((r) => r.year) : [])
    ])).sort((a, b) => a - b);
    const n = allYears.length;

    function xPos(yearVal) {
      const idx = allYears.indexOf(yearVal);
      return PAD_LEFT + (idx / Math.max(n - 1, 1)) * chartW;
    }
    function yPos(val) {
      return PAD_TOP + chartH - (val / yMax) * chartH;
    }

    // ── Grid ──────────────────────────────────────────────────────────────
    const yTicks = 6;
    for (let t = 0; t <= yTicks; t++) {
      const y = PAD_TOP + chartH - (t / yTicks) * chartH;
      ctx.strokeStyle = t === 0 ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.06)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(PAD_LEFT, y);
      ctx.lineTo(PAD_LEFT + chartW, y);
      ctx.stroke();
      ctx.fillStyle = "rgba(232,255,248,0.5)";
      ctx.font = "12px sans-serif";
      ctx.textAlign = "right";
      ctx.fillText((yMax * t / yTicks).toFixed(0), PAD_LEFT - 10, y + 4);
    }

    // X axis labels
    ctx.textAlign = "center";
    ctx.fillStyle = "rgba(232,255,248,0.5)";
    ctx.font = "12px sans-serif";
    allYears.forEach((yr) => {
      const x = xPos(yr);
      ctx.fillText(String(yr), x, H - PAD_BOT + 20);
      ctx.strokeStyle = "rgba(255,255,255,0.1)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, PAD_TOP + chartH);
      ctx.lineTo(x, PAD_TOP + chartH + 5);
      ctx.stroke();
    });

    // Axis border
    ctx.strokeStyle = "rgba(255,255,255,0.22)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(PAD_LEFT, PAD_TOP);
    ctx.lineTo(PAD_LEFT, PAD_TOP + chartH);
    ctx.lineTo(PAD_LEFT + chartW, PAD_TOP + chartH);
    ctx.stroke();

    // Y axis label
    ctx.save();
    ctx.translate(14, PAD_TOP + chartH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillStyle = "rgba(232,255,248,0.35)";
    ctx.font = "11px sans-serif";
    ctx.fillText("Therms / Customer / Year", 0, 0);
    ctx.restore();

    // ── Draw one stacked area series onto the shared axes ─────────────────
    function drawStackedSeries(series, palette, lineWidth, dashed) {
      const stacks = series.map((row) => {
        let cum = 0;
        return endUses.map((eu) => {
          const bot = cum;
          cum += (row[eu] || 0);
          return { bot, top: cum };
        });
      });

      endUses.forEach((eu, euIdx) => {
        const color = palette[eu];

        // Draw only the top boundary line of each band (no fill)
        ctx.beginPath();
        series.forEach((row, i) => {
          const x = xPos(row.year);
          const y = yPos(stacks[i][euIdx].top);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        ctx.lineJoin = "round";
        ctx.setLineDash(dashed ? [8, 5] : []);
        ctx.stroke();
        ctx.setLineDash([]);

        // Dots at each data point
        series.forEach((row, i) => {
          const x = xPos(row.year);
          const y = yPos(stacks[i][euIdx].top);
          ctx.beginPath();
          ctx.arc(x, y, lineWidth + 0.5, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
        });
      });
    }

    // Primary: solid lines; compare: dashed lines — both fully visible
    drawStackedSeries(primarySeries, END_USE_COLORS_PRIMARY, 2.5, false);
    if (compareSeries) {
      drawStackedSeries(compareSeries, END_USE_COLORS_COMPARE, 2.5, true);
    }

    // ── Legend ────────────────────────────────────────────────────────────
    legend.innerHTML = "";

    function addLegendSection(label, palette, dashed) {
      const heading = document.createElement("div");
      heading.style.cssText = "font-size:0.75rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(232,255,248,0.45);margin-bottom:6px;margin-top:10px;";
      heading.textContent = label;
      legend.appendChild(heading);

      endUses.forEach((eu) => {
        const color = palette[eu];
        const item = document.createElement("div");
        item.className = "enduse-legend-item";

        const sw = document.createElement("canvas");
        sw.className = "enduse-legend-swatch-canvas";
        const swDpr = window.devicePixelRatio || 1;
        sw.width  = 36 * swDpr;
        sw.height = 14 * swDpr;
        sw.style.width  = "36px";
        sw.style.height = "14px";
        const sc = sw.getContext("2d");
        sc.scale(swDpr, swDpr);
        sc.strokeStyle = color;
        sc.lineWidth = 2.5;
        sc.setLineDash(dashed ? [6, 4] : []);
        sc.lineCap = "round";
        sc.beginPath(); sc.moveTo(4, 7); sc.lineTo(32, 7); sc.stroke();
        sc.setLineDash([]);
        sc.beginPath(); sc.arc(18, 7, 3, 0, Math.PI * 2);
        sc.fillStyle = color; sc.fill();

        const span = document.createElement("span");
        span.textContent = END_USE_LABELS[eu];
        item.appendChild(sw);
        item.appendChild(span);
        legend.appendChild(item);
      });
    }

    addLegendSection(primaryName, END_USE_COLORS_PRIMARY, false);
    if (compareSeries) {
      addLegendSection(compareName, END_USE_COLORS_COMPARE, true);
    }
  }

  function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  // ── Estimated Total UPC Overlay ───────────────────────────────────────────

  const UPC_LINE_COLORS = {
    primary: "#4ecdc4",
    compare: "#f7b731",
    irp:     "#ff7675"
  };

  function drawEstUpcOverlay(primaryBundle, compareBundle) {
    const canvas = document.getElementById("estUpcCanvas");
    const legend = document.getElementById("estUpcLegend");
    const title  = document.getElementById("estUpcLightboxTitle");
    if (!canvas) return;

    const primaryName = primaryBundle.scenario.display_name;
    const compareName = compareBundle ? compareBundle.scenario.display_name : null;

    title.textContent = compareName
      ? `Estimated Total UPC — ${primaryName} vs ${compareName}`
      : `Estimated Total UPC — ${primaryName}`;

    const primaryData = (primaryBundle.estimated_total_upc || []).slice().sort((a, b) => a.year - b.year);
    const compareData = compareBundle
      ? (compareBundle.estimated_total_upc || []).slice().sort((a, b) => a.year - b.year)
      : null;

    // Build unified year list
    const allYears = Array.from(new Set([
      ...primaryData.map((r) => r.year),
      ...(compareData ? compareData.map((r) => r.year) : [])
    ])).sort((a, b) => a - b);
    const n = allYears.length;
    if (n === 0) return;

    // Lines to draw: estimated_total_upc for each scenario + IRP UPC if present
    const primaryUpc  = allYears.map((yr) => { const r = primaryData.find((d) => d.year === yr); return r ? (r.estimated_total_upc ?? null) : null; });
    const compareUpc  = compareData ? allYears.map((yr) => { const r = compareData.find((d) => d.year === yr); return r ? (r.estimated_total_upc ?? null) : null; }) : null;
    const primaryIrp  = allYears.map((yr) => { const r = primaryData.find((d) => d.year === yr); return r ? (r.irp_upc ?? null) : null; });
    const hasIrp = primaryIrp.some((v) => v !== null);

    // Y range
    const allVals = [
      ...primaryUpc.filter((v) => v !== null),
      ...(compareUpc ? compareUpc.filter((v) => v !== null) : []),
      ...(hasIrp ? primaryIrp.filter((v) => v !== null) : [])
    ];
    const yMin = Math.max(0, Math.min(...allVals) * 0.9);
    const yMax = Math.max(...allVals) * 1.1 || 1;

    // Canvas sizing
    const dpr = window.devicePixelRatio || 1;
    const W = Math.round(Math.min(window.innerWidth * 0.96, 1400) - 64 - 180 - 24);
    const H = Math.round(window.innerHeight * 0.78);

    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width  = `${W}px`;
    canvas.style.height = `${H}px`;

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    const PAD_TOP  = 36;
    const PAD_BOT  = 52;
    const PAD_LEFT = 72;
    const PAD_RIGHT = 16;
    const chartW = W - PAD_LEFT - PAD_RIGHT;
    const chartH = H - PAD_TOP - PAD_BOT;

    function xPos(i) { return PAD_LEFT + (i / Math.max(n - 1, 1)) * chartW; }
    function yPos(v) { return PAD_TOP + chartH - ((v - yMin) / (yMax - yMin)) * chartH; }

    // Grid
    const yTicks = 6;
    for (let t = 0; t <= yTicks; t++) {
      const val = yMin + (yMax - yMin) * t / yTicks;
      const y = yPos(val);
      ctx.strokeStyle = t === 0 ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.06)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(PAD_LEFT, y); ctx.lineTo(PAD_LEFT + chartW, y); ctx.stroke();
      ctx.fillStyle = "rgba(232,255,248,0.5)";
      ctx.font = "12px sans-serif";
      ctx.textAlign = "right";
      ctx.fillText(val.toFixed(0), PAD_LEFT - 10, y + 4);
    }

    // X labels
    ctx.textAlign = "center";
    ctx.fillStyle = "rgba(232,255,248,0.5)";
    ctx.font = "12px sans-serif";
    allYears.forEach((yr, i) => {
      const x = xPos(i);
      ctx.fillText(String(yr), x, H - PAD_BOT + 20);
      ctx.strokeStyle = "rgba(255,255,255,0.1)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, PAD_TOP + chartH); ctx.lineTo(x, PAD_TOP + chartH + 5); ctx.stroke();
    });

    // Axis border
    ctx.strokeStyle = "rgba(255,255,255,0.22)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(PAD_LEFT, PAD_TOP);
    ctx.lineTo(PAD_LEFT, PAD_TOP + chartH);
    ctx.lineTo(PAD_LEFT + chartW, PAD_TOP + chartH);
    ctx.stroke();

    // Y axis label
    ctx.save();
    ctx.translate(14, PAD_TOP + chartH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillStyle = "rgba(232,255,248,0.35)";
    ctx.font = "11px sans-serif";
    ctx.fillText("Therms / Customer / Year", 0, 0);
    ctx.restore();

    function drawLine(values, color, dashed, lineWidth) {
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth || 2.5;
      ctx.lineJoin = "round";
      ctx.setLineDash(dashed ? [8, 5] : []);
      let started = false;
      values.forEach((v, i) => {
        if (v === null) { started = false; return; }
        const x = xPos(i); const y = yPos(v);
        if (!started) { ctx.moveTo(x, y); started = true; } else { ctx.lineTo(x, y); }
      });
      ctx.stroke();
      ctx.setLineDash([]);
      // Dots
      values.forEach((v, i) => {
        if (v === null) return;
        ctx.beginPath();
        ctx.arc(xPos(i), yPos(v), 3.5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      });
    }

    drawLine(primaryUpc, UPC_LINE_COLORS.primary, false, 3);
    if (compareUpc) drawLine(compareUpc, UPC_LINE_COLORS.compare, false, 3);
    if (hasIrp) drawLine(primaryIrp, UPC_LINE_COLORS.irp, true, 2);

    // Legend
    legend.innerHTML = "";
    const legendItems = [
      { color: UPC_LINE_COLORS.primary, label: primaryName, dashed: false },
      ...(compareUpc ? [{ color: UPC_LINE_COLORS.compare, label: compareName, dashed: false }] : []),
      ...(hasIrp ? [{ color: UPC_LINE_COLORS.irp, label: "IRP UPC", dashed: true }] : [])
    ];

    legendItems.forEach(({ color, label, dashed }) => {
      const item = document.createElement("div");
      item.className = "enduse-legend-item";

      const sw = document.createElement("canvas");
      sw.className = "enduse-legend-swatch-canvas";
      const swDpr = window.devicePixelRatio || 1;
      sw.width  = 36 * swDpr; sw.height = 14 * swDpr;
      sw.style.width = "36px"; sw.style.height = "14px";
      const sc = sw.getContext("2d");
      sc.scale(swDpr, swDpr);
      sc.strokeStyle = color;
      sc.lineWidth = dashed ? 2 : 3;
      sc.setLineDash(dashed ? [6, 4] : []);
      sc.lineCap = "round";
      sc.beginPath(); sc.moveTo(4, 7); sc.lineTo(32, 7); sc.stroke();
      sc.setLineDash([]);
      sc.beginPath(); sc.arc(18, 7, 3, 0, Math.PI * 2);
      sc.fillStyle = color; sc.fill();

      const span = document.createElement("span");
      span.textContent = label;
      item.appendChild(sw);
      item.appendChild(span);
      legend.appendChild(item);
    });
  }

  function openEstUpcOverlay() {
    if (!APP.primaryBundle) return;
    const el = document.getElementById("estUpcLightbox");
    if (!el) return;
    el.hidden = false;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => drawEstUpcOverlay(APP.primaryBundle, APP.comparisonBundle));
  }

  function closeEstUpcOverlay() {
    const el = document.getElementById("estUpcLightbox");
    if (el) el.hidden = true;
    document.body.style.overflow = "";
  }

  // ── IRP Decline Rate Overlay ──────────────────────────────────────────────

  function computeDeclineRates(data, field) {
    // Returns array of { year, rate } where rate = (val[i] - val[i-1]) / val[i-1] * 100
    const sorted = data.slice().sort((a, b) => a.year - b.year);
    const rates = [];
    for (let i = 1; i < sorted.length; i++) {
      const prev = sorted[i - 1][field];
      const curr = sorted[i][field];
      if (prev != null && curr != null && prev !== 0) {
        rates.push({ year: sorted[i].year, rate: ((curr - prev) / prev) * 100 });
      }
    }
    return rates;
  }

  function drawIrpDeclineOverlay(primaryBundle, compareBundle) {
    const canvas = document.getElementById("irpDeclineCanvas");
    const legend = document.getElementById("irpDeclineLegend");
    const title  = document.getElementById("irpDeclineLightboxTitle");
    if (!canvas) return;

    const primaryName = primaryBundle.scenario.display_name;
    const compareName = compareBundle ? compareBundle.scenario.display_name : null;

    title.textContent = compareName
      ? `Annual Decline Rates — ${primaryName} vs ${compareName}`
      : `Annual Decline Rates — ${primaryName}`;

    const primaryIrp = primaryBundle.irp_comparison || [];
    const compareIrp = compareBundle ? (compareBundle.irp_comparison || []) : null;

    // Compute decline rates for each series
    const primaryModelRates = computeDeclineRates(primaryIrp, "model_upc");
    const primaryEstRates   = computeDeclineRates(primaryIrp, "estimated_total_upc");
    const primaryIrpRates   = computeDeclineRates(primaryIrp, "irp_upc");
    const compareModelRates = compareIrp ? computeDeclineRates(compareIrp, "model_upc") : null;
    const compareEstRates   = compareIrp ? computeDeclineRates(compareIrp, "estimated_total_upc") : null;

    // Union of all years
    const allYears = Array.from(new Set([
      ...primaryModelRates.map((r) => r.year),
      ...primaryIrpRates.map((r) => r.year),
      ...(compareModelRates ? compareModelRates.map((r) => r.year) : [])
    ])).sort((a, b) => a - b);
    const n = allYears.length;
    if (n === 0) return;

    function rateAt(rates, yr) {
      const found = rates.find((r) => r.year === yr);
      return found ? found.rate : null;
    }

    // Build value arrays aligned to allYears
    const series = [
      { label: `${primaryName} — Model UPC`,     color: "#4ecdc4", dashed: false, vals: allYears.map((y) => rateAt(primaryModelRates, y)) },
      { label: `${primaryName} — Est. Total UPC`, color: "#a29bfe", dashed: false, vals: allYears.map((y) => rateAt(primaryEstRates, y)) },
      { label: "IRP UPC",                          color: "#ff7675", dashed: true,  vals: allYears.map((y) => rateAt(primaryIrpRates, y)) },
      ...(compareModelRates ? [
        { label: `${compareName} — Model UPC`,      color: "#f7b731", dashed: false, vals: allYears.map((y) => rateAt(compareModelRates, y)) },
        { label: `${compareName} — Est. Total UPC`, color: "#fd79a8", dashed: false, vals: allYears.map((y) => rateAt(compareEstRates, y)) }
      ] : [])
    ];

    // Y range — include 0 line
    const allVals = series.flatMap((s) => s.vals.filter((v) => v !== null));
    const yMin = Math.min(0, Math.min(...allVals) * 1.2);
    const yMax = Math.max(0, Math.max(...allVals) * 1.2) || 1;

    // Canvas sizing
    const dpr = window.devicePixelRatio || 1;
    const W = Math.round(Math.min(window.innerWidth * 0.96, 1400) - 64 - 200 - 24);
    const H = Math.round(window.innerHeight * 0.78);

    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width  = `${W}px`;
    canvas.style.height = `${H}px`;

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    const PAD_TOP  = 36;
    const PAD_BOT  = 52;
    const PAD_LEFT = 72;
    const PAD_RIGHT = 16;
    const chartW = W - PAD_LEFT - PAD_RIGHT;
    const chartH = H - PAD_TOP - PAD_BOT;

    function xPos(i) { return PAD_LEFT + (i / Math.max(n - 1, 1)) * chartW; }
    function yPos(v) { return PAD_TOP + chartH - ((v - yMin) / (yMax - yMin)) * chartH; }

    // Grid
    const yTicks = 6;
    for (let t = 0; t <= yTicks; t++) {
      const val = yMin + (yMax - yMin) * t / yTicks;
      const y = yPos(val);
      ctx.strokeStyle = Math.abs(val) < 0.01 ? "rgba(255,255,255,0.35)" : (t === 0 ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.06)");
      ctx.lineWidth = Math.abs(val) < 0.01 ? 1.5 : 1;
      ctx.beginPath(); ctx.moveTo(PAD_LEFT, y); ctx.lineTo(PAD_LEFT + chartW, y); ctx.stroke();
      ctx.fillStyle = "rgba(232,255,248,0.5)";
      ctx.font = "12px sans-serif";
      ctx.textAlign = "right";
      ctx.fillText(`${val.toFixed(1)}%`, PAD_LEFT - 10, y + 4);
    }

    // Zero line label
    const zeroY = yPos(0);
    ctx.fillStyle = "rgba(232,255,248,0.3)";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "left";
    ctx.fillText("0%", PAD_LEFT + 4, zeroY - 4);

    // X labels
    ctx.textAlign = "center";
    ctx.fillStyle = "rgba(232,255,248,0.5)";
    ctx.font = "12px sans-serif";
    allYears.forEach((yr, i) => {
      const x = xPos(i);
      ctx.fillText(String(yr), x, H - PAD_BOT + 20);
      ctx.strokeStyle = "rgba(255,255,255,0.1)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, PAD_TOP + chartH); ctx.lineTo(x, PAD_TOP + chartH + 5); ctx.stroke();
    });

    // Axis border
    ctx.strokeStyle = "rgba(255,255,255,0.22)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(PAD_LEFT, PAD_TOP);
    ctx.lineTo(PAD_LEFT, PAD_TOP + chartH);
    ctx.lineTo(PAD_LEFT + chartW, PAD_TOP + chartH);
    ctx.stroke();

    // Y axis label
    ctx.save();
    ctx.translate(14, PAD_TOP + chartH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillStyle = "rgba(232,255,248,0.35)";
    ctx.font = "11px sans-serif";
    ctx.fillText("Annual Change (%)", 0, 0);
    ctx.restore();

    // Draw lines
    series.forEach(({ color, dashed, vals }) => {
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = dashed ? 2 : 2.5;
      ctx.lineJoin = "round";
      ctx.setLineDash(dashed ? [8, 5] : []);
      let started = false;
      vals.forEach((v, i) => {
        if (v === null) { started = false; return; }
        const x = xPos(i); const y = yPos(v);
        if (!started) { ctx.moveTo(x, y); started = true; } else { ctx.lineTo(x, y); }
      });
      ctx.stroke();
      ctx.setLineDash([]);
      vals.forEach((v, i) => {
        if (v === null) return;
        ctx.beginPath();
        ctx.arc(xPos(i), yPos(v), 3.5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      });
    });

    // Legend
    legend.innerHTML = "";
    series.forEach(({ color, label, dashed }) => {
      const item = document.createElement("div");
      item.className = "enduse-legend-item";
      item.style.marginBottom = "6px";

      const sw = document.createElement("canvas");
      sw.className = "enduse-legend-swatch-canvas";
      const swDpr = window.devicePixelRatio || 1;
      sw.width  = 36 * swDpr; sw.height = 14 * swDpr;
      sw.style.width = "36px"; sw.style.height = "14px";
      const sc = sw.getContext("2d");
      sc.scale(swDpr, swDpr);
      sc.strokeStyle = color;
      sc.lineWidth = dashed ? 2 : 2.5;
      sc.setLineDash(dashed ? [6, 4] : []);
      sc.lineCap = "round";
      sc.beginPath(); sc.moveTo(4, 7); sc.lineTo(32, 7); sc.stroke();
      sc.setLineDash([]);
      sc.beginPath(); sc.arc(18, 7, 3, 0, Math.PI * 2);
      sc.fillStyle = color; sc.fill();

      const span = document.createElement("span");
      span.textContent = label;
      item.appendChild(sw);
      item.appendChild(span);
      legend.appendChild(item);
    });
  }

  function openIrpDeclineOverlay() {
    if (!APP.primaryBundle) return;
    const el = document.getElementById("irpDeclineLightbox");
    if (!el) return;
    el.hidden = false;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => drawIrpDeclineOverlay(APP.primaryBundle, APP.comparisonBundle));
  }

  function closeIrpDeclineOverlay() {
    const el = document.getElementById("irpDeclineLightbox");
    if (el) el.hidden = true;
    document.body.style.overflow = "";
  }

  function closeIrpDeclineOverlay() {
    const el = document.getElementById("irpDeclineLightbox");
    if (el) el.hidden = true;
    document.body.style.overflow = "";
  }

  // ── Total Demand Overlay ──────────────────────────────────────────────────

  function drawTotalDemandOverlay(primaryBundle, compareBundle) {
    const canvas = document.getElementById("totalDemandCanvas");
    const legend = document.getElementById("totalDemandLegend");
    const title  = document.getElementById("totalDemandLightboxTitle");
    if (!canvas) return;

    const primaryName = primaryBundle.scenario.display_name;
    const compareName = compareBundle ? compareBundle.scenario.display_name : null;
    title.textContent = compareName
      ? `Total Demand — ${primaryName} vs ${compareName}`
      : `Total Demand — ${primaryName}`;

    const primaryRows = (primaryBundle.yearly_summary || []).slice().sort((a, b) => a.year - b.year);
    const compareRows = compareBundle
      ? (compareBundle.yearly_summary || []).slice().sort((a, b) => a.year - b.year)
      : null;

    const allYears = Array.from(new Set([
      ...primaryRows.map((r) => r.year),
      ...(compareRows ? compareRows.map((r) => r.year) : [])
    ])).sort((a, b) => a - b);
    const n = allYears.length;
    if (n === 0) return;

    function valAt(rows, yr, field) {
      const r = rows.find((d) => d.year === yr);
      return r ? (r[field] ?? null) : null;
    }

    const series = [
      { label: `${primaryName} — Total Therms`, color: "#4ecdc4", dashed: false,
        vals: allYears.map((y) => valAt(primaryRows, y, "total_therms")) },
      { label: `${primaryName} — UPC`,           color: "#a29bfe", dashed: false,
        vals: allYears.map((y) => valAt(primaryRows, y, "use_per_customer")), axis: "right" },
      ...(compareRows ? [
        { label: `${compareName} — Total Therms`, color: "#f7b731", dashed: true,
          vals: allYears.map((y) => valAt(compareRows, y, "total_therms")) },
        { label: `${compareName} — UPC`,           color: "#fd79a8", dashed: true,
          vals: allYears.map((y) => valAt(compareRows, y, "use_per_customer")), axis: "right" }
      ] : [])
    ];

    // Two Y axes: left = therms, right = UPC
    const thermsSeries = series.filter((s) => !s.axis);
    const upcSeries    = series.filter((s) => s.axis === "right");

    const thermsVals = thermsSeries.flatMap((s) => s.vals.filter((v) => v !== null));
    const upcVals    = upcSeries.flatMap((s) => s.vals.filter((v) => v !== null));
    const thermsMax  = Math.max(...thermsVals) * 1.1 || 1;
    const thermsMin  = Math.max(0, Math.min(...thermsVals) * 0.9);
    const upcMax     = Math.max(...upcVals) * 1.1 || 1;
    const upcMin     = Math.max(0, Math.min(...upcVals) * 0.9);

    const dpr = window.devicePixelRatio || 1;
    const W = Math.round(Math.min(window.innerWidth * 0.96, 1400) - 64 - 200 - 24);
    const H = Math.round(window.innerHeight * 0.78);
    canvas.width  = W * dpr; canvas.height = H * dpr;
    canvas.style.width = `${W}px`; canvas.style.height = `${H}px`;

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    const PAD_TOP = 36, PAD_BOT = 52, PAD_LEFT = 80, PAD_RIGHT = 72;
    const chartW = W - PAD_LEFT - PAD_RIGHT;
    const chartH = H - PAD_TOP - PAD_BOT;

    function xPos(i) { return PAD_LEFT + (i / Math.max(n - 1, 1)) * chartW; }
    function yPosLeft(v)  { return PAD_TOP + chartH - ((v - thermsMin) / (thermsMax - thermsMin)) * chartH; }
    function yPosRight(v) { return PAD_TOP + chartH - ((v - upcMin)    / (upcMax    - upcMin))    * chartH; }

    // Grid + left Y axis
    const yTicks = 6;
    for (let t = 0; t <= yTicks; t++) {
      const y = PAD_TOP + chartH - (t / yTicks) * chartH;
      ctx.strokeStyle = t === 0 ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.06)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(PAD_LEFT, y); ctx.lineTo(PAD_LEFT + chartW, y); ctx.stroke();
      const thermsVal = thermsMin + (thermsMax - thermsMin) * t / yTicks;
      ctx.fillStyle = "rgba(232,255,248,0.5)"; ctx.font = "11px sans-serif"; ctx.textAlign = "right";
      ctx.fillText((thermsVal / 1e6).toFixed(1) + "M", PAD_LEFT - 8, y + 4);
      const upcVal = upcMin + (upcMax - upcMin) * t / yTicks;
      ctx.textAlign = "left";
      ctx.fillStyle = "rgba(162,155,254,0.7)";
      ctx.fillText(upcVal.toFixed(0), PAD_LEFT + chartW + 8, y + 4);
    }

    // X labels
    ctx.textAlign = "center"; ctx.fillStyle = "rgba(232,255,248,0.5)"; ctx.font = "12px sans-serif";
    allYears.forEach((yr, i) => {
      const x = xPos(i);
      ctx.fillText(String(yr), x, H - PAD_BOT + 20);
      ctx.strokeStyle = "rgba(255,255,255,0.1)"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, PAD_TOP + chartH); ctx.lineTo(x, PAD_TOP + chartH + 5); ctx.stroke();
    });

    // Axis borders
    ctx.strokeStyle = "rgba(255,255,255,0.22)"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(PAD_LEFT, PAD_TOP); ctx.lineTo(PAD_LEFT, PAD_TOP + chartH); ctx.lineTo(PAD_LEFT + chartW, PAD_TOP + chartH); ctx.stroke();
    ctx.strokeStyle = "rgba(162,155,254,0.4)"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(PAD_LEFT + chartW, PAD_TOP); ctx.lineTo(PAD_LEFT + chartW, PAD_TOP + chartH); ctx.stroke();

    // Y axis labels
    ctx.save(); ctx.translate(14, PAD_TOP + chartH / 2); ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center"; ctx.fillStyle = "rgba(232,255,248,0.35)"; ctx.font = "11px sans-serif";
    ctx.fillText("Total Therms", 0, 0); ctx.restore();
    ctx.save(); ctx.translate(W - 14, PAD_TOP + chartH / 2); ctx.rotate(Math.PI / 2);
    ctx.textAlign = "center"; ctx.fillStyle = "rgba(162,155,254,0.5)"; ctx.font = "11px sans-serif";
    ctx.fillText("UPC (Therms/Customer)", 0, 0); ctx.restore();

    // Draw lines
    series.forEach(({ color, dashed, vals, axis }) => {
      const yFn = axis === "right" ? yPosRight : yPosLeft;
      ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = dashed ? 2 : 2.5;
      ctx.lineJoin = "round"; ctx.setLineDash(dashed ? [8, 5] : []);
      let started = false;
      vals.forEach((v, i) => {
        if (v === null) { started = false; return; }
        const x = xPos(i), y = yFn(v);
        if (!started) { ctx.moveTo(x, y); started = true; } else { ctx.lineTo(x, y); }
      });
      ctx.stroke(); ctx.setLineDash([]);
      vals.forEach((v, i) => {
        if (v === null) return;
        ctx.beginPath(); ctx.arc(xPos(i), yFn(v), 3.5, 0, Math.PI * 2);
        ctx.fillStyle = color; ctx.fill();
      });
    });

    // Legend
    legend.innerHTML = "";
    series.forEach(({ color, label, dashed }) => {
      const item = document.createElement("div");
      item.className = "enduse-legend-item";
      item.style.marginBottom = "8px";
      const sw = document.createElement("canvas");
      sw.className = "enduse-legend-swatch-canvas";
      const swDpr = window.devicePixelRatio || 1;
      sw.width = 36 * swDpr; sw.height = 14 * swDpr;
      sw.style.width = "36px"; sw.style.height = "14px";
      const sc = sw.getContext("2d");
      sc.scale(swDpr, swDpr);
      sc.strokeStyle = color; sc.lineWidth = dashed ? 2 : 2.5;
      sc.setLineDash(dashed ? [6, 4] : []); sc.lineCap = "round";
      sc.beginPath(); sc.moveTo(4, 7); sc.lineTo(32, 7); sc.stroke(); sc.setLineDash([]);
      sc.beginPath(); sc.arc(18, 7, 3, 0, Math.PI * 2); sc.fillStyle = color; sc.fill();
      const span = document.createElement("span");
      span.textContent = label;
      item.appendChild(sw); item.appendChild(span);
      legend.appendChild(item);
    });
  }

  function openTotalDemandOverlay() {
    if (!APP.primaryBundle) return;
    const el = document.getElementById("totalDemandLightbox");
    if (!el) return;
    el.hidden = false;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => drawTotalDemandOverlay(APP.primaryBundle, APP.comparisonBundle));
  }

  function closeTotalDemandOverlay() {
    const el = document.getElementById("totalDemandLightbox");
    if (el) el.hidden = true;
    document.body.style.overflow = "";
  }

  // ── Segment Demand Overlay ────────────────────────────────────────────────

  function drawSegmentDemandOverlay(primaryBundle, compareBundle) {
    const canvas = document.getElementById("segmentDemandCanvas");
    const legend = document.getElementById("segmentDemandLegend");
    const title  = document.getElementById("segmentDemandLightboxTitle");
    if (!canvas) return;

    const primaryName = primaryBundle.scenario.display_name;
    const compareName = compareBundle ? compareBundle.scenario.display_name : null;
    title.textContent = compareName
      ? `Segment Demand — ${primaryName} vs ${compareName}`
      : `Segment Demand — ${primaryName}`;

    function buildSegmentMap(bundle) {
      const map = {};
      (bundle.segment_demand || []).forEach((row) => {
        if (!map[row.segment]) map[row.segment] = [];
        map[row.segment].push({ year: row.year, total_therms: row.total_therms });
      });
      Object.values(map).forEach((arr) => arr.sort((a, b) => a.year - b.year));
      return map;
    }

    const primaryMap = buildSegmentMap(primaryBundle);
    const compareMap = compareBundle ? buildSegmentMap(compareBundle) : null;
    const segments = Array.from(new Set([
      ...Object.keys(primaryMap),
      ...(compareMap ? Object.keys(compareMap) : [])
    ])).sort();

    const SEGMENT_COLORS = ["#4ecdc4", "#f7b731", "#fd79a8", "#a29bfe", "#ff7675", "#81ecec"];

    const allYears = Array.from(new Set([
      ...Object.values(primaryMap).flatMap((arr) => arr.map((r) => r.year)),
      ...(compareMap ? Object.values(compareMap).flatMap((arr) => arr.map((r) => r.year)) : [])
    ])).sort((a, b) => a - b);
    const n = allYears.length;
    if (n === 0) return;

    // Build series: one per segment per scenario
    const series = [];
    segments.forEach((seg, si) => {
      const color = SEGMENT_COLORS[si % SEGMENT_COLORS.length];
      const pRows = primaryMap[seg] || [];
      series.push({
        label: `${seg} (${primaryName})`, color, dashed: false,
        vals: allYears.map((y) => { const r = pRows.find((d) => d.year === y); return r ? r.total_therms : null; })
      });
      if (compareMap) {
        const cRows = compareMap[seg] || [];
        series.push({
          label: `${seg} (${compareName})`, color, dashed: true,
          vals: allYears.map((y) => { const r = cRows.find((d) => d.year === y); return r ? r.total_therms : null; })
        });
      }
    });

    const allVals = series.flatMap((s) => s.vals.filter((v) => v !== null));
    const yMin = Math.max(0, Math.min(...allVals) * 0.9);
    const yMax = Math.max(...allVals) * 1.1 || 1;

    const dpr = window.devicePixelRatio || 1;
    const W = Math.round(Math.min(window.innerWidth * 0.96, 1400) - 64 - 200 - 24);
    const H = Math.round(window.innerHeight * 0.78);
    canvas.width  = W * dpr; canvas.height = H * dpr;
    canvas.style.width = `${W}px`; canvas.style.height = `${H}px`;

    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    const PAD_TOP = 36, PAD_BOT = 52, PAD_LEFT = 80, PAD_RIGHT = 16;
    const chartW = W - PAD_LEFT - PAD_RIGHT;
    const chartH = H - PAD_TOP - PAD_BOT;

    function xPos(i) { return PAD_LEFT + (i / Math.max(n - 1, 1)) * chartW; }
    function yPos(v) { return PAD_TOP + chartH - ((v - yMin) / (yMax - yMin)) * chartH; }

    // Grid
    const yTicks = 6;
    for (let t = 0; t <= yTicks; t++) {
      const y = PAD_TOP + chartH - (t / yTicks) * chartH;
      ctx.strokeStyle = t === 0 ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.06)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(PAD_LEFT, y); ctx.lineTo(PAD_LEFT + chartW, y); ctx.stroke();
      const val = yMin + (yMax - yMin) * t / yTicks;
      ctx.fillStyle = "rgba(232,255,248,0.5)"; ctx.font = "11px sans-serif"; ctx.textAlign = "right";
      ctx.fillText((val / 1e6).toFixed(1) + "M", PAD_LEFT - 8, y + 4);
    }

    ctx.textAlign = "center"; ctx.fillStyle = "rgba(232,255,248,0.5)"; ctx.font = "12px sans-serif";
    allYears.forEach((yr, i) => {
      const x = xPos(i);
      ctx.fillText(String(yr), x, H - PAD_BOT + 20);
      ctx.strokeStyle = "rgba(255,255,255,0.1)"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, PAD_TOP + chartH); ctx.lineTo(x, PAD_TOP + chartH + 5); ctx.stroke();
    });

    ctx.strokeStyle = "rgba(255,255,255,0.22)"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(PAD_LEFT, PAD_TOP); ctx.lineTo(PAD_LEFT, PAD_TOP + chartH); ctx.lineTo(PAD_LEFT + chartW, PAD_TOP + chartH); ctx.stroke();

    ctx.save(); ctx.translate(14, PAD_TOP + chartH / 2); ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center"; ctx.fillStyle = "rgba(232,255,248,0.35)"; ctx.font = "11px sans-serif";
    ctx.fillText("Total Therms", 0, 0); ctx.restore();

    series.forEach(({ color, dashed, vals }) => {
      ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = dashed ? 2 : 2.5;
      ctx.lineJoin = "round"; ctx.setLineDash(dashed ? [8, 5] : []);
      let started = false;
      vals.forEach((v, i) => {
        if (v === null) { started = false; return; }
        const x = xPos(i), y = yPos(v);
        if (!started) { ctx.moveTo(x, y); started = true; } else { ctx.lineTo(x, y); }
      });
      ctx.stroke(); ctx.setLineDash([]);
      vals.forEach((v, i) => {
        if (v === null) return;
        ctx.beginPath(); ctx.arc(xPos(i), yPos(v), 3.5, 0, Math.PI * 2);
        ctx.fillStyle = color; ctx.fill();
      });
    });

    legend.innerHTML = "";
    series.forEach(({ color, label, dashed }) => {
      const item = document.createElement("div");
      item.className = "enduse-legend-item";
      item.style.marginBottom = "8px";
      const sw = document.createElement("canvas");
      sw.className = "enduse-legend-swatch-canvas";
      const swDpr = window.devicePixelRatio || 1;
      sw.width = 36 * swDpr; sw.height = 14 * swDpr;
      sw.style.width = "36px"; sw.style.height = "14px";
      const sc = sw.getContext("2d");
      sc.scale(swDpr, swDpr);
      sc.strokeStyle = color; sc.lineWidth = dashed ? 2 : 2.5;
      sc.setLineDash(dashed ? [6, 4] : []); sc.lineCap = "round";
      sc.beginPath(); sc.moveTo(4, 7); sc.lineTo(32, 7); sc.stroke(); sc.setLineDash([]);
      sc.beginPath(); sc.arc(18, 7, 3, 0, Math.PI * 2); sc.fillStyle = color; sc.fill();
      const span = document.createElement("span");
      span.textContent = label;
      item.appendChild(sw); item.appendChild(span);
      legend.appendChild(item);
    });
  }

  function openSegmentDemandOverlay() {
    if (!APP.primaryBundle) return;
    const el = document.getElementById("segmentDemandLightbox");
    if (!el) return;
    el.hidden = false;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => drawSegmentDemandOverlay(APP.primaryBundle, APP.comparisonBundle));
  }

  function closeSegmentDemandOverlay() {
    const el = document.getElementById("segmentDemandLightbox");
    if (el) el.hidden = true;
    document.body.style.overflow = "";
  }

  function openEndUseOverlay() {
    if (!APP.primaryBundle) return;
    const el = document.getElementById("endUseLightbox");
    if (!el) return;
    el.hidden = false;
    document.body.style.overflow = "hidden";
    // Draw after the element is visible so offsetWidth is correct
    requestAnimationFrame(() => {
      drawEndUseOverlay(APP.primaryBundle, APP.comparisonBundle);
    });
  }

  function closeEndUseOverlay() {
    const el = document.getElementById("endUseLightbox");
    if (el) el.hidden = true;
    document.body.style.overflow = "";
  }

  function wireEndUseOverlay() {
    const closeBtn = document.getElementById("endUseLightboxClose");
    const backdrop = document.getElementById("endUseLightboxBackdrop");
    if (closeBtn) closeBtn.addEventListener("click", closeEndUseOverlay);
    if (backdrop) backdrop.addEventListener("click", closeEndUseOverlay);

    const estUpcCloseBtn = document.getElementById("estUpcLightboxClose");
    const estUpcBackdrop = document.getElementById("estUpcLightboxBackdrop");
    if (estUpcCloseBtn) estUpcCloseBtn.addEventListener("click", closeEstUpcOverlay);
    if (estUpcBackdrop) estUpcBackdrop.addEventListener("click", closeEstUpcOverlay);

    const irpCloseBtn = document.getElementById("irpDeclineLightboxClose");
    const irpBackdrop = document.getElementById("irpDeclineLightboxBackdrop");
    if (irpCloseBtn) irpCloseBtn.addEventListener("click", closeIrpDeclineOverlay);
    if (irpBackdrop) irpBackdrop.addEventListener("click", closeIrpDeclineOverlay);

    const tdCloseBtn = document.getElementById("totalDemandLightboxClose");
    const tdBackdrop = document.getElementById("totalDemandLightboxBackdrop");
    if (tdCloseBtn) tdCloseBtn.addEventListener("click", closeTotalDemandOverlay);
    if (tdBackdrop) tdBackdrop.addEventListener("click", closeTotalDemandOverlay);

    const sdCloseBtn = document.getElementById("segmentDemandLightboxClose");
    const sdBackdrop = document.getElementById("segmentDemandLightboxBackdrop");
    if (sdCloseBtn) sdCloseBtn.addEventListener("click", closeSegmentDemandOverlay);
    if (sdBackdrop) sdBackdrop.addEventListener("click", closeSegmentDemandOverlay);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        const eu = document.getElementById("endUseLightbox");
        if (eu && !eu.hidden) { closeEndUseOverlay(); return; }
        const upc = document.getElementById("estUpcLightbox");
        if (upc && !upc.hidden) { closeEstUpcOverlay(); return; }
        const irp = document.getElementById("irpDeclineLightbox");
        if (irp && !irp.hidden) { closeIrpDeclineOverlay(); return; }
        const td = document.getElementById("totalDemandLightbox");
        if (td && !td.hidden) { closeTotalDemandOverlay(); return; }
        const sd = document.getElementById("segmentDemandLightbox");
        if (sd && !sd.hidden) closeSegmentDemandOverlay();
      }
    });

    window.addEventListener("resize", () => {
      const eu = document.getElementById("endUseLightbox");
      if (eu && !eu.hidden && APP.primaryBundle) drawEndUseOverlay(APP.primaryBundle, APP.comparisonBundle);
      const upc = document.getElementById("estUpcLightbox");
      if (upc && !upc.hidden && APP.primaryBundle) drawEstUpcOverlay(APP.primaryBundle, APP.comparisonBundle);
      const irp = document.getElementById("irpDeclineLightbox");
      if (irp && !irp.hidden && APP.primaryBundle) drawIrpDeclineOverlay(APP.primaryBundle, APP.comparisonBundle);
      const td = document.getElementById("totalDemandLightbox");
      if (td && !td.hidden && APP.primaryBundle) drawTotalDemandOverlay(APP.primaryBundle, APP.comparisonBundle);
      const sd = document.getElementById("segmentDemandLightbox");
      if (sd && !sd.hidden && APP.primaryBundle) drawSegmentDemandOverlay(APP.primaryBundle, APP.comparisonBundle);
    });
  }

  async function init() {
    if (typeof document === "undefined") {
      return;
    }

    if (!document.getElementById(DOM_IDS.presetStrip)) {
      return;
    }

    try {
      cacheDom();

      // Verify critical DOM elements resolved — surface any mismatch immediately
      const missing = Object.entries(dom)
        .filter(([, el]) => el === null)
        .map(([key]) => key);
      if (missing.length) {
        console.error("NWScenarioDashboard: missing DOM elements:", missing);
      }

      APP.lastCommittedPayload = serializePayload(buildConfigPayload(APP.currentState));
      wireEvents();
      wireLightbox();
      wireEndUseOverlay();
      render();
      await checkServerHealth();
      if (APP.serverHealthy) {
        await refreshScenarioCatalog();
      }
    } catch (err) {
      console.error("NWScenarioDashboard init error:", err);
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
