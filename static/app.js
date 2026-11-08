const $ = (selector) => document.querySelector(selector);
const chartInstances = {};
const REQUIRED = ["temp_c", "rainfall_mm", "yield_kg_ha", "ag_land_pct"];
const showToast = (message) => {
  const toast = $("#toast"); toast.textContent = message; toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 5000);
};
const showMessage = (message, kind = "info") => {
  const box = $("#dataset-message"); box.textContent = message; box.className = `dataset-message ${kind}`; box.hidden = !message;
};
const display = (selector, value, suffix = "") => {
  const missing = value == null || (typeof value === "number" && !Number.isFinite(value));
  $(selector).textContent = missing ? "—" : `${value}${suffix}`;
};
function addCountryOptions(countries) {
  const select = $("#country"); const selected = select.value;
  select.innerHTML = '<option value="ALL">All available Eurasia</option>';
  countries.forEach(({ iso3, name }) => {
    const option = document.createElement("option"); option.value = iso3; option.textContent = name; select.append(option);
  });
  if (countries.some((country) => country.iso3 === selected)) select.value = selected;
}
async function getJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}
async function loadData() {
  const data = await getJson(`/api/data?country=${encodeURIComponent($("#country").value)}`);
  const meta = await getJson("/api/metadata");
  addCountryOptions(meta.countries || []);
  render(data.rows || [], data.summary || {});
  $("#updated").textContent = data.metadata?.updated ? `Updated ${new Date(data.metadata.updated).toLocaleDateString()}` : "No dataset loaded";
  renderMissing(data.summary?.missing || {}, data.metadata?.source_errors || [], (data.rows || []).length > 0);
  if (!data.summary?.available) showMessage(data.summary?.message || "No observations are available. Refresh the dataset to load source data.");
  else if ((data.metadata?.source_errors || []).length) showMessage(`Loaded available source records. ${data.metadata.source_errors.length} source request(s) failed; see the missing data summary below.`, "warning");
  else showMessage("");
}
function renderMissing(missing, errors, hasRows) {
  const labels = { temp_c: "Temperature", rainfall_mm: "Annual precipitation", humidity_pct: "Relative humidity", yield_kg_ha: "Cereal yield", ag_land_pct: "Agricultural land" };
  const entries = hasRows ? Object.entries(labels).map(([key, label]) => `${label}: ${missing[key] == null ? "unavailable" : `${missing[key]} missing`}`).join(" · ") : "Missing data statistics unavailable until source observations are loaded.";
  const errorText = errors.length ? ` Upstream errors: ${errors.slice(0, 4).join(" | ")}${errors.length > 4 ? ` (+${errors.length - 4} more)` : ""}` : "";
  $("#missing-statistics").textContent = entries ? `Missing required values in the selected panel: ${entries}.${errorText}` : "";
}
function render(rows, summary) {
  const hasData = Boolean(summary.available) && rows.length > 0;
  display("#m-region", "Eurasia");
  $("#period").textContent = summary.year_start != null ? `${summary.year_start} — ${summary.year_end}` : "Historical panel";
  if (!hasData) {
    ["#m-countries", "#m-years", "#m-rows", "#m-temp", "#m-rain", "#m-yield", "#m-land", "#nrows", "#year-range"].forEach((id) => { $(id).textContent = "—"; });
    Object.keys(chartInstances).forEach(destroyChart); setEmptyCharts("No complete country-year source observations are available yet."); return;
  }
  display("#m-countries", summary.countries);
  display("#m-years", summary.years);
  $("#year-range").textContent = `${summary.year_start}–${summary.year_end}`;
  display("#m-rows", Number(summary.observations).toLocaleString());
  display("#nrows", Number(summary.observations).toLocaleString());
  display("#m-temp", summary.mean_temp_c, "°C");
  display("#m-rain", summary.mean_annual_precip_mm == null ? null : Number(summary.mean_annual_precip_mm).toLocaleString(), " mm");
  display("#m-yield", summary.mean_yield_kg_ha == null ? null : Math.round(summary.mean_yield_kg_ha).toLocaleString(), " kg/ha");
  display("#m-land", summary.mean_ag_land_pct, "%");
  const complete = rows.filter((row) => REQUIRED.every((key) => row[key] != null));
  const yearlyMean = (key) => {
    const groups = new Map();
    rows.forEach((row) => { if (row[key] != null) { const values = groups.get(row.year) || []; values.push(Number(row[key])); groups.set(row.year, values); } });
    return [...groups.entries()].sort((a, b) => a[0] - b[0]).map(([year, values]) => ({ x: Number(year), y: values.reduce((sum, value) => sum + value, 0) / values.length }));
  };
  drawChart("temperatureChart", "line", [{ label: "Temperature (°C)", data: yearlyMean("temp_c"), borderColor: "#d9954b", backgroundColor: "#d9954b", pointRadius: 0, borderWidth: 2, tension: 0.2 }], "°C");
  drawChart("precipitationChart", "line", [{ label: "Annual precipitation (mm)", data: yearlyMean("rainfall_mm"), borderColor: "#5b9c7e", backgroundColor: "#5b9c7e", pointRadius: 0, borderWidth: 2, tension: 0.2 }], "mm/year");
  const byCountry = new Map();
  rows.filter((row) => row.yield_kg_ha != null).forEach((row) => {
    const current = byCountry.get(row.iso3);
    if (!current || row.year > current.year) byCountry.set(row.iso3, row);
  });
  const yieldRows = [...byCountry.values()].sort((a, b) => Number(b.yield_kg_ha) - Number(a.yield_kg_ha));
  drawChart("yieldCountryChart", "bar", [{ label: "Latest cereal yield (kg/ha)", data: yieldRows.map((row) => Number(row.yield_kg_ha)), backgroundColor: "#5b9c7e", borderRadius: 4 }], "kg/ha", "category", "Country", yieldRows.map((row) => row.country));
  drawChart("landChart", "line", [{ label: "Agricultural land (%)", data: yearlyMean("ag_land_pct"), borderColor: "#588b71", backgroundColor: "rgba(88,139,113,.12)", pointRadius: 0, borderWidth: 2, tension: 0.2, fill: true }], "% of land area");
  const points = complete.map((row) => ({ x: Number(row.temp_c), y: Number(row.yield_kg_ha), country: row.country, year: row.year, land: Number(row.ag_land_pct) }));
  drawChart("sustainabilityChart", "scatter", [{ label: "Country-year observations", data: points, backgroundColor: "rgba(56,135,98,.55)", pointRadius: 3 }], "Yield (kg/ha)", "linear", "Temperature (°C)");
}
const chartOptions = (unit, xType = "linear", xTitle = "Year") => ({
  responsive: true, maintainAspectRatio: false,
  interaction: { mode: "nearest", intersect: true },
  plugins: { legend: { display: false }, tooltip: { backgroundColor: "#173a35", callbacks: { label: (ctx) => {
    const raw = ctx.raw || {}; const x = raw.x; const y = raw.y;
    return raw.country ? `${raw.country}, ${raw.year}: ${Number(y).toLocaleString()} kg/ha; land ${raw.land}%` : `${Number(y).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}${raw.year ? ` (${raw.year})` : ""}`;
  } } } },
  scales: {
    x: { type: xType, title: { display: true, text: xTitle, color: "#83948c", font: { size: 10 } }, grid: { display: false }, ticks: { maxTicksLimit: 10, color: "#91a099", font: { size: 9 } } },
    y: { title: { display: true, text: unit, color: "#83948c", font: { size: 10 } }, grid: { color: "#edf1ee" }, ticks: { color: "#91a099", font: { size: 9 } } },
  },
});
function destroyChart(id) { if (chartInstances[id]) { chartInstances[id].destroy(); delete chartInstances[id]; } }
function drawChart(id, type, datasets, unit, xType = "linear", xTitle = "Year", labels = []) {
  if (typeof Chart === "undefined") { setEmptyCharts("Chart.js could not load. Check the network or CDN access."); return; }
  destroyChart(id); const canvas = document.getElementById(id); canvas.style.display = "block";
  canvas.closest(".chart-wrap").querySelector(".chart-placeholder")?.remove();
  chartInstances[id] = new Chart(canvas, { type, data: { labels, datasets }, options: chartOptions(unit, xType, xTitle) });
}
function setEmptyCharts(message) {
  document.querySelectorAll(".chart-wrap").forEach((wrap) => {
    const canvas = wrap.querySelector("canvas"); if (canvas) canvas.style.display = "none";
    let placeholder = wrap.querySelector(".chart-placeholder"); if (!placeholder) { placeholder = document.createElement("div"); placeholder.className = "chart-placeholder"; wrap.append(placeholder); }
    placeholder.textContent = message;
  });
}
$("#country").addEventListener("change", () => loadData().catch((error) => showMessage(error.message, "error")));
$("#temp-delta").addEventListener("input", (event) => { const value = Number(event.target.value); $("#temp-out").textContent = `${value > 0 ? "+" : ""}${value} °C`; });
$("#rain-delta").addEventListener("input", (event) => { const value = Number(event.target.value); $("#rain-out").textContent = `${value > 0 ? "+" : ""}${value}%`; });
$("#run").addEventListener("click", async () => {
  const button = $("#run"); button.disabled = true;
  try {
    if ($("#country").value === "ALL") throw new Error("Choose a country with valid observations before running a scenario.");
    const data = await getJson("/api/predict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ country: $("#country").value, temp_delta: Number($("#temp-delta").value), rain_delta_pct: Number($("#rain-delta").value) }) });
    const changeClass = data.change >= 0 ? "down" : "up"; const sign = data.change > 0 ? "+" : "";
    $("#result").innerHTML = `<span class="eyebrow">MODEL ESTIMATE · ${data.country} BASE YEAR ${data.year}</span><div class="result-main"><strong>${Math.round(data.scenario).toLocaleString()}</strong><span class="${changeClass}">${sign}${data.change_pct}%</span></div><small>Estimated cereal yield · kg/ha (baseline ${Math.round(data.baseline).toLocaleString()} kg/ha)</small>`;
    $("#explain").hidden = false;
    const max = Math.max(...data.explanations.map((item) => Math.abs(item.delta_yield)), 1);
    $("#explain-bars").innerHTML = data.explanations.map((item) => `<div class="barrow"><span>${item.feature.replaceAll("_", " ")}</span><div class="bartrack"><div class="barfill ${item.delta_yield < 0 ? "neg" : ""}" style="width:${Math.abs(item.delta_yield) / max * 100}%"></div></div><b>${item.delta_yield > 0 ? "+" : ""}${item.delta_yield} kg/ha</b></div>`).join("");
    $("#quality").textContent = `Temporal holdout (${data.metrics.test_start}–${data.metrics.test_end}): MAE ${data.metrics.mae} kg/ha${data.metrics.r2 == null ? "" : ` · R² ${data.metrics.r2}`}. Train ${data.metrics.n_train} observations; test ${data.metrics.n_test}.`;
  } catch (error) { showToast(error.message); }
  finally { button.disabled = false; }
});
$("#refresh").addEventListener("click", async () => {
  const button = $("#refresh"); button.disabled = true; button.textContent = "Fetching source data…"; showMessage("Fetching World Bank agricultural series and NASA POWER climate records. This can take several minutes.");
  try {
    const result = await getJson("/api/refresh", { method: "POST" });
    await loadData();
    showToast(`Loaded ${Number(result.valid_observations).toLocaleString()} valid observations across ${result.countries} countries (${result.year_start}–${result.year_end}).`);
  } catch (error) { showMessage(error.message, "error"); showToast(error.message); }
  finally { button.disabled = false; button.textContent = "↻ Load / refresh data"; }
});
loadData().catch((error) => { showMessage(`Could not load dashboard data: ${error.message}`, "error"); setEmptyCharts("Dashboard data request failed."); });
