"use strict";
const $ = (id) => document.getElementById(id);
const labels = { temperature: "온도", vibration: "진동", current: "전류" };
const units = { temperature: "°C", vibration: "mm/s", current: "A" };
const statusLabels = {
  normal: "정상",
  anomaly: "이상 감지",
  waiting: "수신 대기",
};
const state = {
  machine: "press-01",
  metric: "vibration",
  overview: null,
  chart: null,
  busy: false,
  injecting: false,
};
const format = (value, metric) =>
  Number(value).toFixed(metric === "vibration" ? 3 : 1);
const time = (value) =>
  new Date(value).toLocaleTimeString("ko-KR", { hour12: false });
const dateTime = (value) =>
  new Date(value).toLocaleString("ko-KR", { hour12: false });
const pill = (status) =>
  `<span class="pill ${status}">${statusLabels[status]}</span>`;

async function api(path, options) {
  const response = await fetch(path, {
    ...options,
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `요청 오류 (${response.status})`,
    );
  }
  return response.json();
}

function updateOverview(data) {
  state.overview = data;
  $("normal-count").textContent = String(
    data.machines.filter((m) => m.status === "normal").length,
  ).padStart(2, "0");
  const anomalyCount = data.machines.filter(
    (m) => m.status === "anomaly",
  ).length;
  $("anomaly-count").textContent = String(anomalyCount).padStart(2, "0");
  $("anomaly-count").style.color = anomalyCount
    ? "var(--orange)"
    : "var(--text)";
  $("event-count").textContent = data.event_count.toLocaleString();
  const waiting = data.machines.filter((m) => m.status === "waiting").length;
  $("waiting-count").textContent = waiting
    ? `수신 대기 ${waiting}대`
    : "모든 설비 데이터 수신 중";
  $("mode-label").textContent = data.simulator
    ? "SYNTHETIC DEMO"
    : "EXTERNAL INPUT · DEMO BASELINE";
  $("threshold").textContent = data.threshold;
  // Update existing buttons to preserve keyboard focus during one-second polling.
  for (const machine of data.machines) {
    let card = document.querySelector(`[data-machine="${machine.id}"]`);
    if (!card) {
      card = document.createElement("button");
      card.dataset.machine = machine.id;
      card.addEventListener("click", () => {
        state.machine = machine.id;
        updateOverview(state.overview);
      });
      $("machines").append(card);
    }
    card.className = `machine-card${machine.id === state.machine ? " selected" : ""}`;
    card.setAttribute("aria-pressed", machine.id === state.machine);
    card.innerHTML = `<div class="machine-top"><span class="machine-name">${machine.name}</span>${pill(machine.status)}</div><p class="machine-type">${machine.type} / ${machine.id}</p><div class="machine-values">${Object.keys(
      labels,
    )
      .map(
        (metric) =>
          `<div><small>${labels[metric]}</small><strong>${machine.latest ? format(machine.latest[metric], metric) : "—"}<em>${units[metric]}</em></strong></div>`,
      )
      .join("")}</div>`;
  }
  const selected = data.machines.find((m) => m.id === state.machine);
  $("trend-heading").innerHTML = `${selected.name} <span>센서 추이</span>`;
  $("selected-location").textContent = selected.location;
  $("current-value").textContent = selected.latest
    ? format(selected.latest[state.metric], state.metric)
    : "—";
  $("current-unit").textContent = units[state.metric];
  $("chart-status").className = `pill ${selected.status}`;
  $("chart-status").textContent = statusLabels[selected.status];
  $("last-updated").textContent = selected.latest
    ? `마지막 수신 ${time(selected.latest.timestamp)}`
    : "마지막 수신 —";
  $("injection-description").textContent = data.simulator
    ? `${selected.name}의 ${labels[state.metric]}을 ${8 * data.interval}초 동안 8회 높여 탐지 흐름을 시연합니다.`
    : "외부 입력 모드입니다. API로 센서 측정값을 전송하세요.";
  $("inject").disabled =
    !data.simulator || data.simulator_error || state.injecting;
}

function updateChart(items, selectedMachine, selectedMetric) {
  const machine = state.overview.machines.find((m) => m.id === selectedMachine);
  const reference = machine.baseline[selectedMetric];
  const threshold = state.overview.threshold;
  const mean = reference.mean;
  const range = threshold * reference.std;
  $("chart-empty").hidden = items.length > 0;
  const values = items.map((item) => item[selectedMetric]);
  state.chart.data.labels = items.map((item) => time(item.timestamp));
  state.chart.data.datasets = [
    {
      label: labels[selectedMetric],
      data: values,
      borderColor: "#6bdfbd",
      backgroundColor: "#6bdfbd0d",
      borderWidth: 2,
      fill: true,
      tension: 0.25,
      pointRadius: items.map((item) =>
        item.anomalies.includes(selectedMetric) ? 4 : 0,
      ),
      pointHitRadius: 12,
      pointBackgroundColor: items.map((item) =>
        item.anomalies.includes(selectedMetric) ? "#ffb071" : "#6bdfbd",
      ),
    },
    {
      label: "상한",
      data: items.map(() => mean + range),
      borderColor: "#607887",
      borderDash: [5, 5],
      borderWidth: 1,
      pointRadius: 0,
    },
    {
      label: "하한",
      data: items.map(() => mean - range),
      borderColor: "#607887",
      borderDash: [5, 5],
      borderWidth: 1,
      pointRadius: 0,
    },
  ];
  state.chart.options.scales.y.suggestedMin = mean - range * 1.4;
  state.chart.options.scales.y.suggestedMax = mean + range * 1.4;
  state.chart.options.scales.y.title.text = units[selectedMetric];
  state.chart.update("none");
}

function updateEvents(items) {
  $("event-scope").textContent =
    `${$("event-filter").value === "all" ? "전체 설비" : "선택 설비"} · 최근 8건`;
  $("event-rows").innerHTML = items.length
    ? items
        .map((item) => {
          const name = state.overview.machines.find(
            (m) => m.id === item.machine_id,
          ).name;
          return `<tr><td>${dateTime(item.timestamp)}</td><td>${name}</td><td class="event-sensor">${item.anomalies.map((metric) => `${labels[metric]} ${format(item[metric], metric)} ${units[metric]}`).join(" · ")}</td><td class="score">${Math.max(...Object.values(item.scores)).toFixed(2)}σ</td><td>${item.source === "simulator" ? "시뮬레이터" : "외부 입력"}</td></tr>`;
        })
        .join("")
    : '<tr><td colspan="5" class="empty">아직 기록된 이상 이벤트가 없습니다. 이상 주입으로 탐지를 확인해 보세요.</td></tr>';
}

async function refresh() {
  if (state.busy) return;
  state.busy = true;
  try {
    const overview = await api("/api/overview");
    updateOverview(overview);
    const machine = state.machine,
      metric = state.metric,
      filter = $("event-filter").value;
    const eventQuery = filter === "selected" ? `&machine_id=${machine}` : "";
    const [history, events] = await Promise.all([
      api(`/api/readings/${machine}?limit=60`),
      api(`/api/events?limit=8${eventQuery}`),
    ]);
    // Ignore responses from a selection that changed while requests were in flight.
    if (machine === state.machine && metric === state.metric)
      updateChart(history.items, machine, metric);
    if (machine === state.machine && filter === $("event-filter").value)
      updateEvents(events.items);
    if (overview.simulator_error)
      throw new Error("시뮬레이터가 중지되었습니다. 서버 로그를 확인하세요.");
    $("connection").className = "connection online";
    $("connection").innerHTML = "<i></i>서버 연결됨";
    $("error").hidden = true;
  } catch (error) {
    $("connection").className = "connection offline";
    $("connection").innerHTML = "<i></i>연결 확인 필요";
    $("inject").disabled = true;
    $("error").textContent =
      `데이터 갱신 실패 — 이전 수신값이 표시될 수 있습니다. ${error.message}`;
    $("error").hidden = false;
  } finally {
    state.busy = false;
  }
}

document.querySelectorAll("[data-metric]").forEach((button) =>
  button.addEventListener("click", () => {
    state.metric = button.dataset.metric;
    document.querySelectorAll("[data-metric]").forEach((b) => {
      b.classList.toggle("active", b === button);
      b.setAttribute("aria-pressed", b === button);
    });
    if (state.overview) updateOverview(state.overview);
    refresh();
  }),
);
$("event-filter").addEventListener("change", refresh);
$("inject").addEventListener("click", async () => {
  const machine = state.machine,
    metric = state.metric;
  state.injecting = true;
  $("inject").disabled = true;
  try {
    await api("/api/demo/anomaly", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ machine_id: machine, metric }),
    });
    $("feedback").textContent =
      `${machine} · ${labels[metric]} 이상 주입을 요청했습니다. 다음 8개 측정값에 반영됩니다.`;
  } catch (error) {
    $("feedback").textContent = `요청 실패: ${error.message}`;
  } finally {
    state.injecting = false;
    refresh();
  }
});

try {
  Chart.defaults.font.family =
    '-apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif';
  Chart.defaults.color = "#8fa1ae";
  state.chart = new Chart($("sensor-chart"), {
    type: "line",
    data: { labels: [], datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: "#21323d", padding: 12 },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { maxTicksLimit: 8, maxRotation: 0, font: { size: 9 } },
          border: { display: false },
        },
        y: {
          grid: { color: "#26353f" },
          border: { display: false },
          title: {
            display: true,
            text: units[state.metric],
            font: { size: 9 },
          },
          ticks: { maxTicksLimit: 5, font: { size: 9 } },
        },
      },
    },
  });
  refresh();
  setInterval(refresh, 1000);
} catch (error) {
  $("error").hidden = false;
  $("error").textContent = `그래프 초기화 실패: ${error.message}`;
}
