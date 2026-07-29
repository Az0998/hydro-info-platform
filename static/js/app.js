/* HydroInfo dashboard */

const statusMap = {
  normal: { label: "正常", cls: "ok" },
  warn: { label: "注意", cls: "warn" },
  alert: { label: "警戒", cls: "alert" },
};

const chartSeries = echarts.init(document.getElementById("chartSeries"));
const chartForecast = echarts.init(document.getElementById("chartForecast"));
const chartRating = echarts.init(document.getElementById("chartRating"));

const daysSelect = document.getElementById("daysSelect");
const stationSelect = document.getElementById("stationSelect");
const rangeLabel = document.getElementById("rangeLabel");
const asOfLabel = document.getElementById("asOfLabel");

function axisStyle() {
  return {
    axisLine: { lineStyle: { color: "rgba(120,190,210,0.25)" } },
    axisLabel: { color: "#8fb3c0" },
    splitLine: { lineStyle: { color: "rgba(120,190,210,0.08)" } },
  };
}

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(url);
  return res.json();
}

function renderKPI(stations) {
  const row = document.getElementById("kpiRow");
  row.innerHTML = stations
    .map((s) => {
      const st = statusMap[s.status] || statusMap.normal;
      const delta =
        s.delta_q == null
          ? "—"
          : `${s.delta_q > 0 ? "+" : ""}${s.delta_q} cfs`;
      return `
        <div class="kpi">
          <div class="label">${s.name} · ${s.id}</div>
          <div class="value">${s.q_cfs?.toLocaleString?.() ?? "—"} <small style="font-size:14px;color:#8fb3c0">cfs</small></div>
          <div class="meta">
            <span>水位 ${s.stage_ft ?? "—"} ft · Δ ${delta}</span>
            <span class="badge ${st.cls}">${st.label}</span>
          </div>
        </div>`;
    })
    .join("");
}

function fillStations(stations) {
  const cur = stationSelect.value;
  stationSelect.innerHTML = stations
    .map((s) => `<option value="${s.id}">${s.name}</option>`)
    .join("");
  if (cur && [...stationSelect.options].some((o) => o.value === cur)) {
    stationSelect.value = cur;
  }
}

function renderSeries(data) {
  chartSeries.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    legend: { textStyle: { color: "#8fb3c0" }, top: 0 },
    grid: { left: 50, right: 40, top: 40, bottom: 40 },
    xAxis: { type: "category", data: data.dates, ...axisStyle() },
    yAxis: [
      { type: "value", name: "cfs", nameTextStyle: { color: "#8fb3c0" }, ...axisStyle() },
      { type: "value", name: "mm", nameTextStyle: { color: "#8fb3c0" }, ...axisStyle() },
    ],
    series: [
      {
        name: "流量",
        type: "line",
        showSymbol: false,
        data: data.q_cfs,
        lineStyle: { width: 2, color: "#2ec4b6" },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(46,196,182,0.35)" },
            { offset: 1, color: "rgba(46,196,182,0.02)" },
          ]),
        },
        markLine: {
          symbol: "none",
          data: [
            { yAxis: data.warn_q, name: "注意", lineStyle: { color: "#e9a825", type: "dashed" } },
            { yAxis: data.alert_q, name: "警戒", lineStyle: { color: "#e4572e", type: "dashed" } },
          ],
          label: { color: "#8fb3c0" },
        },
      },
      {
        name: "降水",
        type: "bar",
        yAxisIndex: 1,
        data: data.precip_mm,
        itemStyle: { color: "rgba(61,139,253,0.45)" },
      },
    ],
  });
}

function renderForecast(data) {
  const dates = data.path.map((p) => p.date);
  const qs = data.path.map((p) => p.q_cfs);
  chartForecast.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    grid: { left: 50, right: 20, top: 30, bottom: 40 },
    xAxis: { type: "category", data: dates, ...axisStyle() },
    yAxis: { type: "value", name: "cfs", nameTextStyle: { color: "#8fb3c0" }, ...axisStyle() },
    series: [
      {
        name: "预报流量",
        type: "line",
        data: qs,
        smooth: true,
        showSymbol: true,
        symbolSize: 8,
        lineStyle: { width: 2.5, color: "#3d8bfd" },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(61,139,253,0.3)" },
            { offset: 1, color: "rgba(61,139,253,0.02)" },
          ]),
        },
      },
    ],
  });

  const chips = (data.backtest || [])
    .map((b) => {
      const nse = b.persistence?.nse;
      const nseTxt = nse == null ? "—" : nse.toFixed(3);
      return `<div class="chip">${b.horizon_day} 日 Persistence NSE <strong>${nseTxt}</strong></div>`;
    })
    .join("");
  document.getElementById("forecastMetrics").innerHTML =
    `<div class="chip">起报 ${data.as_of} · 最新 ${data.latest_q?.toLocaleString?.()} cfs</div>` + chips;
}

function renderRating(data) {
  const pts = data.q_cfs.map((q, i) => [q, data.stage_ft[i]]);
  chartRating.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "item", formatter: (p) => `Q ${p.value[0]} cfs<br/>Z ${p.value[1]} ft` },
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: { type: "value", name: "Q (cfs)", nameTextStyle: { color: "#8fb3c0" }, ...axisStyle() },
    yAxis: { type: "value", name: "Z (ft)", nameTextStyle: { color: "#8fb3c0" }, ...axisStyle() },
    series: [
      {
        type: "scatter",
        data: pts,
        symbolSize: 6,
        itemStyle: { color: "rgba(46,196,182,0.65)" },
      },
    ],
  });
}

function renderQC(payload) {
  const list = document.getElementById("qcList");
  list.innerHTML = (payload.reports || [])
    .map((r) => {
      const st = statusMap[r.status] || statusMap.normal;
      const flags =
        r.flags?.length
          ? `<ul>${r.flags.map((f) => `<li>${f.msg}</li>`).join("")}</ul>`
          : `<ul><li>无明显异常</li></ul>`;
      return `
        <div class="qc-item">
          <div class="row">
            <strong>${r.name}</strong>
            <span class="badge ${st.cls}">${st.label}</span>
          </div>
          ${flags}
        </div>`;
    })
    .join("");
}

async function refresh() {
  const days = daysSelect.value;
  const station = stationSelect.value || "01646500";
  rangeLabel.textContent = daysSelect.options[daysSelect.selectedIndex].text;

  const [overview, series, forecast, rating, qc] = await Promise.all([
    getJSON(`/api/overview?days=${days}`),
    getJSON(`/api/series?days=${days}&station=${station}`),
    getJSON(`/api/forecast?horizon=7`),
    getJSON(`/api/rating`),
    getJSON(`/api/qc?days=${days}`),
  ]);

  fillStations(overview.stations);
  if (!stationSelect.value) stationSelect.value = overview.stations[0]?.id || "01646500";
  renderKPI(overview.stations);
  asOfLabel.textContent = `数据截止 ${overview.summary.date_end || "—"}`;
  renderSeries(series);
  renderForecast(forecast);
  renderRating(rating);
  renderQC(qc);
}

daysSelect.addEventListener("change", refresh);
stationSelect.addEventListener("change", refresh);
window.addEventListener("resize", () => {
  chartSeries.resize();
  chartForecast.resize();
  chartRating.resize();
});

refresh().catch((err) => {
  console.error(err);
  document.getElementById("kpiRow").innerHTML =
    `<div class="kpi"><div class="label">加载失败</div><div class="value" style="font-size:16px">请检查后端是否启动</div></div>`;
});
