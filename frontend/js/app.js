/* ============================================================
   量衡录 · 前端主控
   路由 / API / 视图 / 任务轮讯 / 渲染
   ============================================================ */

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/* === State === */
const state = {
  apiBase: localStorage.getItem("lh.apiBase") || "",
  health: null,
  strategies: [],
  tasks: [],
  dailyDates: [],
  currentTaskPoll: null,
};

const cnNums = ["零","一","二","三","四","五","六","七","八","九"];

/* === API client === */
async function api(path, opts = {}) {
  const base = state.apiBase || "";
  const url = base + path;
  try {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    const ct = res.headers.get("content-type") || "";
    const data = ct.includes("json") ? await res.json() : await res.text();
    if (!res.ok) {
      const err = new Error(data?.error?.message || `HTTP ${res.status}`);
      err.status = res.status;
      err.code   = data?.error?.code;
      err.detail = data?.error?.detail;
      throw err;
    }
    return data;
  } catch (e) {
    if (e.status) throw e;
    throw new Error("通 讯 阻 断  ·  详 ：" + e.message);
  }
}

/* === 印章 SVG 工厂 === */
function seal(chars = "衡", size = "md") {
  const px = size === "lg" ? 120 : size === "sm" ? 48 : 80;
  const fs = size === "lg" ? 28 : size === "sm" ? 11 : 18;
  return `
    <svg viewBox="0 0 100 100" width="${px}" height="${px}" xmlns="http://www.w3.org/2000/svg">
      <rect class="seal-rect" x="6" y="6" width="88" height="88" />
      <rect class="seal-rect" x="11" y="11" width="78" height="78" stroke-width="0.8" />
      <text class="seal-text" x="50" y="${chars.length === 1 ? 65 : 60}" text-anchor="middle"
            font-size="${chars.length === 1 ? fs : fs * 0.7}">${escapeHtml(chars)}</text>
    </svg>
  `;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fmtBytes(n) {
  if (!n) return "0";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return n.toFixed(1) + " " + u[i];
}

function agoCN(iso) {
  if (!iso) return "—";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "方  寸  之  前";
  if (s < 3600) return `${Math.floor(s/60)} 分  前`;
  if (s < 86400) return `${Math.floor(s/3600)} 时  前`;
  return `${Math.floor(s/86400)} 日  前`;
}

/* === Toast === */
function toast(msg, kind = "info", duration = 3500) {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = msg;
  $("#toast-container").appendChild(el);
  setTimeout(() => el.style.opacity = "0", duration - 300);
  setTimeout(() => el.remove(), duration);
}

/* === Status pill === */
function setApiStatus(state_, text) {
  const pill = $("#api-status");
  pill.dataset.state = state_;
  $(".status-text", pill).textContent = text;
}

function setMastheadDate(d = new Date()) {
  const y = d.getFullYear();
  const m = d.getMonth() + 1;
  const day = d.getDate();
  const dayCN = cnNums[day] || day;
  const lunarHint = `星 期 ${"日一二三四五六"[d.getDay()]}`;
  $("#masthead-date").textContent = `${y} 载 ${m} 月 ${dayCN} 日  ·  ${lunarHint}`;
}

/* === 启动时拉健康信息 === */
async function bootstrap() {
  setMastheadDate();
  setApiStatus("connecting", "通 讯 待 接");
  try {
    const [health, strategies, tasks, daily] = await Promise.all([
      api("/api/health").catch(e => ({ error: e.message })),
      api("/api/screen/strategies").catch(() => ({ strategies: [] })),
      api("/api/tasks?status=running").catch(() => []),
      api("/api/daily/reports").catch(() => ({ dates: [] })),
    ]);
    state.health = health.error ? null : health;
    state.strategies = strategies.strategies || [];
    state.tasks = tasks || [];
    state.dailyDates = daily.dates || [];

    if (state.health) {
      setApiStatus("ok", "通 讯 顺 畅");
      $("#masthead-meta").textContent =
        `${state.tasks.length} 工  ·  ` +
        `${state.dailyDates.length} 载 日 报  ·  ` +
        `缓  ${fmtBytes(state.health.cache_size_bytes)}`;
    } else {
      setApiStatus("err", "通 讯 阻 断");
    }
  } catch (e) {
    setApiStatus("err", "通 讯 阻 断");
  }
  updateTaskBadge();
}

/* === 路由 === */
const ROUTES = ["screen", "chat", "weekly", "settings"];

function currentRoute() {
  const hash = location.hash.replace(/^#\//, "") || "screen";
  return ROUTES.includes(hash) ? hash : "screen";
}

window.addEventListener("hashchange", render);

/* === 渲染入口 === */
async function render() {
  const route = currentRoute();
  $$(".toc-item").forEach(a => a.classList.toggle("active", a.dataset.route === route));
  const root = $("#view-root");
  root.innerHTML = `<div class="placeholder loading">载  入  中</div>`;
  try {
    if (route === "screen") await renderScreen(root);
    else if (route === "chat") await renderChat(root);
    else if (route === "weekly") await renderWeekly(root);
    else if (route === "settings") await renderSettings(root);
  } catch (e) {
    root.innerHTML = errorBlock(e);
  }
}

/* ========== 视图：选股 ========== */
async function renderScreen(root) {
  const strategies = (await api("/api/screen/strategies")).strategies;
  state.strategies = strategies;

  const allTasks = await api("/api/tasks").catch(() => []);
  const lastByKey = {};
  for (const t of allTasks) {
    if (!t.type?.startsWith("screen_") || t.type === "screen_all") continue;
    const key = t.type.replace("screen_", "");
    if (!lastByKey[key] || t.created_at > lastByKey[key].created_at) lastByKey[key] = t;
  }

  root.innerHTML = `
    <header class="section-head">
      <span class="section-num">壹</span>
      <span class="section-name">选  股</span>
      <span class="section-en">Screen · Five Strategies</span>
    </header>
    <div class="section-rule"></div>

    <div style="display:flex; gap:16px; margin-bottom: 20px; align-items: center; flex-wrap: wrap;">
      <div style="flex:1; font-family: var(--serif); color: var(--ink-mid); font-size: 13px; letter-spacing: 0.15em;">
        量 衡 录 五 法  ·  各 执 一 端  ·  点 击 启 之
      </div>
      <button class="btn primary" id="btn-screen-all">  全 策 略 共 振  </button>
    </div>

    <div class="cards" id="strategy-cards">
      ${strategies.map(s => renderStrategyCard(s, lastByKey[s.key])).join("")}
    </div>

    <div style="margin-top: 32px">
      <header class="section-head" style="border-bottom-color: var(--bronze)">
        <span class="section-num" style="font-size: 28px; color: var(--bronze)">卷</span>
        <span class="section-name" style="font-size: 20px">选 股 结 果</span>
        <span class="section-en">Results</span>
      </header>

      <div class="filter-bar">
        <div class="field"><label>果  卷  <span class="hint">file</span></label>
          <select id="res-file">
            <option value="screen_all">screen_all · 全 策 略 共 振</option>
            <option value="value">value · 价 值</option>
            <option value="520">520 · 五 二 零</option>
            <option value="dividend">dividend · 高 股 息</option>
            <option value="doublelow">doublelow · 双 低</option>
            <option value="xiaoyang">xiaoyang · 小 阳</option>
          </select>
        </div>
        <div class="field"><label>命 中 ≥ <span class="hint">min_hits</span></label>
          <input type="number" id="res-minhits" min="1" max="5" placeholder="不 限"></div>
        <div class="field"><label>本 益 ≤ <span class="hint">max_pe</span></label>
          <input type="number" id="res-maxpe" min="0" step="0.1" placeholder="不 限"></div>
        <div class="field"><label>含 策 略 <span class="hint">strategy</span></label>
          <input type="text" id="res-strategy" placeholder="例 : 价 值"></div>
        <div class="field" style="min-width: 100px; flex: 0">
          <label>&nbsp;</label>
          <button class="btn sm" id="btn-res-load">查  询  →</button>
        </div>
      </div>

      <div id="results-table">${resultsPlaceholder()}</div>
      <div id="results-pager"></div>
    </div>
  `;

  $$(".btn-run-strategy").forEach(btn => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.key;
      const params = collectStrategyParams(key);
      runScreenSingle(key, params);
    });
  });

  $("#btn-screen-all").addEventListener("click", () => runScreenAll());

  $$(".strategy-card").forEach(card => {
    card.addEventListener("click", e => {
      if (e.target.closest("button") || e.target.closest("input,select")) return;
      $(".strategy-params", card)?.classList.toggle("collapsed");
    });
  });

  const loadResults = () => loadScreenResults();
  $("#btn-res-load").addEventListener("click", loadResults);
  $("#res-file").addEventListener("change", loadResults);

  loadScreenResults();
}

function renderStrategyCard(s, lastTask) {
  const params = s.default_params;
  const paramList = Object.entries(params).map(([k, v]) =>
    `<div class="param"><span class="pname">${k}</span><span class="pval">${v}</span></div>`
  ).join("");

  const isRunning = lastTask?.status === "running" || lastTask?.status === "pending";
  const statusText = lastTask
    ? `${lastTask.status === "success" ? "已 竟" : lastTask.status === "failed" ? "失 败" : lastTask.status === "running" ? "执 行" : "—" }  ·  ${agoCN(lastTask.finished_at || lastTask.started_at || lastTask.created_at)}`
    : "未  启  ·  候  令";

  return `
    <div class="strategy-card ${isRunning ? "running" : ""}" data-key="${s.key}">
      <div class="strategy-head">
        <div class="seal sm">${seal(s.cn_name, "sm")}</div>
        <div>
          <div class="strategy-cn">${escapeHtml(s.cn_name)} 法</div>
          <div class="strategy-key">${s.key}</div>
        </div>
      </div>
      <div class="strategy-desc">${escapeHtml(s.description)}</div>
      <div class="strategy-params">
        ${paramList}
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
        <div style="font-family: var(--serif); font-size: 11px; color: var(--ink-soft); letter-spacing: 0.15em;">${statusText}</div>
        <button class="btn sm primary btn-run-strategy" data-key="${s.key}" ${isRunning ? "disabled" : ""}>
          ${isRunning ? "执 行 中" : "启  令"}
        </button>
      </div>
    </div>
  `;
}

function collectStrategyParams(key) {
  const s = state.strategies.find(x => x.key === key);
  return s ? { ...s.default_params } : {};
}

async function runScreenSingle(key, params) {
  try {
    const r = await api(`/api/screen/${key}`, { method: "POST", body: JSON.stringify(params) });
    toast(`「${key}」 令 已 传  ·  ${r.task_id.slice(0, 8)}`, "ok");
    openTaskModal(r.task_id, `选 股 · ${key.toUpperCase()}`);
  } catch (e) {
    toast(e.message, "err");
  }
}

async function runScreenAll() {
  try {
    const r = await api(`/api/screen/all`, { method: "POST", body: JSON.stringify({}) });
    toast(`全 策 略 共 振 已 启  ·  ${r.task_id.slice(0, 8)}`, "ok");
    openTaskModal(r.task_id, "全 策 略 共 振");
  } catch (e) {
    toast(e.message, "err");
  }
}

let _resultsState = { file: "screen_all", page: 1, size: 20 };

async function loadScreenResults() {
  const root = $("#results-table");
  if (!root) return;
  const file = $("#res-file").value;
  const min_hits = $("#res-minhits").value ? Number($("#res-minhits").value) : undefined;
  const max_pe = $("#res-maxpe").value ? Number($("#res-maxpe").value) : undefined;
  const strategy = $("#res-strategy").value || undefined;

  _resultsState = { file, page: 1, size: 20, min_hits, max_pe, strategy };
  root.innerHTML = `<div class="loading" style="padding: 24px; display:block; text-align: center">查  询  中</div>`;

  try {
    const qs = new URLSearchParams({ file, size: 20, page: 1 });
    if (min_hits) qs.set("min_hits", min_hits);
    if (max_pe) qs.set("max_pe", max_pe);
    if (strategy) qs.set("strategy", strategy);
    const data = await api("/api/screen/results?" + qs);
    renderResultsTable(root, data);
  } catch (e) {
    root.innerHTML = errorBlock(e);
  }
}

function renderResultsTable(root, data) {
  if (data.total === 0) {
    root.innerHTML = emptyState("无 果", `${data.file} 卷 中 尚 无 合 用 股`);
    $("#results-pager").innerHTML = "";
    return;
  }
  const cols = data.rows[0] ? Object.keys(data.rows[0]) : [];
  const labelMap = {
    code: "代  码", name: "名  称", pe: "本 益", pb: "净 值",
    latest_roe: "ROE", dividend_yield: "股 息 率", latest_close: "收  价",
    "命中策略数": "命 中 数", "命中策略": "命 中 策 略",
    hit_count: "命 中 数", hit_strategies: "命 中 策 略",
  };
  const numCols = new Set(["pe", "pb", "latest_roe", "dividend_yield", "latest_close", "命中策略数", "hit_count"]);

  root.innerHTML = `
    <div style="padding: 8px 16px; font-family: var(--serif); font-size: 12px; color: var(--ink-mid); letter-spacing: 0.15em; background: var(--paper-deep); border: 1px solid var(--paper-edge); border-bottom: 0;">
      卷 ：<strong>${data.file}.csv</strong>  ·  计 ：<strong>${data.total}</strong> 只  ·  未 过 滤 ：${data.total_before_filter}  ·  现 第 <strong>${data.page}</strong> 页
    </div>
    <div class="table-wrap">
      <table class="listing">
        <thead>
          <tr>${cols.map(c => `<th>${labelMap[c] || c}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${data.rows.map(r => `<tr>${
            cols.map(c => {
              const v = r[c];
              const cls = c === "code" ? "code" : (numCols.has(c) ? "num" : "");
              const display = v === null || v === undefined || v === "" ? "—" : v;
              return `<td class="${cls}">${escapeHtml(String(display))}</td>`;
            }).join("")
          }</tr>`).join("")}
        </tbody>
      </table>
    </div>
  `;

  const totalPages = Math.max(1, Math.ceil(data.total / data.size));
  $("#results-pager").innerHTML = `
    <div class="pager">
      <button id="pg-prev" ${data.page <= 1 ? "disabled" : ""}>← 上 页</button>
      <span class="page-info">第 ${data.page} 页  /  共 ${totalPages} 页</span>
      <button id="pg-next" ${data.page >= totalPages ? "disabled" : ""}>下 页 →</button>
    </div>
  `;
  $("#pg-prev")?.addEventListener("click", () => { _resultsState.page = Math.max(1, _resultsState.page - 1); loadResultsPage(_resultsState); });
  $("#pg-next")?.addEventListener("click", () => { _resultsState.page = _resultsState.page + 1; loadResultsPage(_resultsState); });
}

async function loadResultsPage(st) {
  const root = $("#results-table");
  root.innerHTML = `<div class="loading" style="padding: 24px; text-align:center; display:block">查  询  中</div>`;
  try {
    const qs = new URLSearchParams({ file: st.file, size: st.size, page: st.page });
    if (st.min_hits) qs.set("min_hits", st.min_hits);
    if (st.max_pe) qs.set("max_pe", st.max_pe);
    if (st.strategy) qs.set("strategy", st.strategy);
    const data = await api("/api/screen/results?" + qs);
    renderResultsTable(root, data);
  } catch (e) {
    root.innerHTML = errorBlock(e);
  }
}

function resultsPlaceholder() {
  return `<div class="empty-state" style="padding: 24px;">
    <div class="empty-seal">${seal("待", "sm")}</div>
    <div class="empty-sub">选 择 果 卷  ·  或 启 令 后 自 动 载 入</div>
  </div>`;
}

/* ========== 视图：问股 ========== */
async function renderChat(root) {
  if (typeof renderChatView === "function") {
    return renderChatView(root);
  }
  root.innerHTML = `
    <div class="empty-state">
      <div class="empty-seal">${seal("误", "md")}</div>
      <div class="empty-title">chat.js 未 载 入</div>
      <div class="empty-sub">请 刷 新 页 面  ·  或 检 查 控 制 台</div>
    </div>
  `;
}

/* ========== 视图：量衡录 ========== */
async function renderWeekly(root) {
  const dates = (await api("/api/daily/reports")).dates || [];
  state.dailyDates = dates;
  const latest = dates[0];

  root.innerHTML = `
    <header class="section-head">
      <span class="section-num">叁</span>
      <span class="section-name">量 衡 录</span>
      <span class="section-en">Almanac · Daily & Weekly Notes</span>
    </header>
    <div class="section-rule"></div>

    <div style="font-family: var(--serif); color: var(--ink-mid); font-size: 13px; letter-spacing: 0.15em; margin-bottom: 20px;">
      共  <strong style="color: var(--vermillion)">${dates.length}</strong>  载  ·  最 新  ${latest || "—"}
      <span style="color: var(--ink-soft); margin-left: 12px;">·  新 载 由 编 印 者 周 度 手 制</span>
    </div>

    ${dates.length === 0 ? emptyState("尚 无 刊 物", "候 首 期 出 印  ·  静 待 周 度 编 印") : `
    <div class="split">
      <div class="date-list" id="date-list">
        ${dates.map((d, i) => `
          <div class="date-item ${i === 0 ? "active" : ""}" data-date="${d}">
            ${d.slice(5).replace("-", " 月 ") + " 日"}
            <span class="date-en">${d}</span>
          </div>
        `).join("")}
      </div>
      <div id="daily-content">${dailyLoading()}</div>
    </div>
    `}
  `;

  if (dates.length) {
    $$(".date-item").forEach(el => {
      el.addEventListener("click", () => {
        $$(".date-item").forEach(x => x.classList.remove("active"));
        el.classList.add("active");
        loadDailyContent(el.dataset.date);
      });
    });
    loadDailyContent(latest);
  }
}

function loadDailyContent(date) {
  const root = $("#daily-content");
  root.innerHTML = dailyLoading();
  api(`/api/daily/reports/${date}`)
    .then(r => {
      root.innerHTML = `
        <div style="margin-bottom: 8px; font-family: var(--serif); font-size: 12px; color: var(--ink-soft); letter-spacing: 0.2em;">
          载 期 ：${date}  ·  字  ${r.markdown.length}
        </div>
        <div class="article">${marked.parse(r.markdown || "（ 卷 中 无 字 ）")}</div>
      `;
    })
    .catch(e => root.innerHTML = errorBlock(e));
}

function dailyLoading() {
  return `<div class="loading" style="padding: 48px; text-align:center; display:block">展  卷  中</div>`;
}

/* ========== 视图：任务 ========== */
async function renderTasks(root) {
  const tasks = await api("/api/tasks");
  state.tasks = tasks;
  const running = tasks.filter(t => t.status === "running" || t.status === "pending");
  const done    = tasks.filter(t => t.status === "success" || t.status === "failed" || t.status === "cancelled");

  root.innerHTML = `
    <div class="metrics" style="grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));">
      <div class="metric"><div class="metric-label">候  命</div><div class="metric-value">${tasks.filter(t => t.status === "pending").length}</div></div>
      <div class="metric"><div class="metric-label">执 行</div><div class="metric-value" style="color: var(--running)">${tasks.filter(t => t.status === "running").length}</div></div>
      <div class="metric"><div class="metric-label">成  功</div><div class="metric-value" style="color: var(--ok)">${tasks.filter(t => t.status === "success").length}</div></div>
      <div class="metric"><div class="metric-label">失 败</div><div class="metric-value" style="color: var(--err)">${tasks.filter(t => t.status === "failed").length}</div></div>
      <div class="metric"><div class="metric-label">撤 回</div><div class="metric-value">${tasks.filter(t => t.status === "cancelled").length}</div></div>
    </div>

    <header class="section-head" style="margin-top: 24px;">
      <span class="section-num" style="font-size: 28px; color: var(--running)">现</span>
      <span class="section-name" style="font-size: 20px;">候  讯  中</span>
    </header>
    ${running.length === 0
      ? emptyState("当 前 寂 静", "无 工 程 在 候")
      : `<div class="task-list">${running.map(renderTaskRow).join("")}</div>`}

    <header class="section-head" style="margin-top: 24px;">
      <span class="section-num" style="font-size: 28px; color: var(--bronze)">往</span>
      <span class="section-name" style="font-size: 20px;">往  载</span>
    </header>
    ${done.length === 0
      ? emptyState("尚 无 旧 载", "启 令 后 将 落 此 处")
      : `<div class="task-list">${done.slice(0, 20).map(renderTaskRow).join("")}</div>`}
  `;

  $$(".task-row").forEach(row => {
    row.addEventListener("click", () => openTaskModal(row.dataset.tid, row.dataset.ttype));
  });
}

function renderTaskRow(t) {
  return `
    <div class="task-row" data-tid="${t.id}" data-ttype="${t.type}">
      <span class="tid">${t.id.slice(0, 8)}</span>
      <span class="ttype">${escapeHtml(t.type)}</span>
      <span class="tstep">${escapeHtml(t.step || "—")}  ${t.progress ? `· ${t.progress}%` : ""}</span>
      <span class="taction"><span class="badge ${t.status}">${t.status}</span></span>
    </div>
  `;
}

function renderTaskList(tasks) {
  return `<div class="task-list">${tasks.map(renderTaskRow).join("")}</div>`;
}

async function openTaskCenter() {
  const root = $("#task-center-content");
  root.innerHTML = `<div class="loading" style="padding: 32px; text-align:center; display:block">候  讯  中</div>`;
  $("#task-center").hidden = false;
  await renderTasks(root);
}

function closeTaskCenter() {
  $("#task-center").hidden = true;
}

function updateTaskBadge() {
  const running = (state.tasks || []).filter(t => t.status === "running" || t.status === "pending");
  const badge = $("#task-badge");
  if (!badge) return;
  if (running.length > 0) {
    badge.hidden = false;
    $("#task-badge-count").textContent = running.length;
    badge.classList.toggle("has-running", true);
  } else {
    badge.hidden = true;
    badge.classList.toggle("has-running", false);
  }
}

/* ========== 视图：设置 ========== */
async function renderSettings(root) {
  const health = await api("/api/health").catch(() => null);
  const strategies = await api("/api/screen/strategies").catch(() => ({ strategies: [] }));
  const ai = await api("/api/settings/ai").catch(() => null);

  root.innerHTML = `
    <header class="section-head">
      <span class="section-num">陆</span>
      <span class="section-name">设  置</span>
      <span class="section-en">Settings · Configuration</span>
    </header>
    <div class="section-rule"></div>

    <div class="cards" style="grid-template-columns: 1fr;">
      <div class="strategy-card">
        <div style="display:flex; align-items:center; gap: 16px;">
          <div class="seal sm">${seal("模", "sm")}</div>
          <div>
            <div class="strategy-cn">大 模 型 API</div>
            <div class="strategy-key">AI 点 评 之 源  ·  OpenAI 兼 容 端 点</div>
          </div>
        </div>
        <div class="field">
          <label>API 网 址 <span class="hint">api_base</span></label>
          <input type="text" id="set-ai-base" placeholder="例 : https://api.deepseek.com/v1/chat/completions">
        </div>
        <div class="field">
          <label>模 型 名 <span class="hint">model</span></label>
          <input type="text" id="set-ai-model" placeholder="例 : deepseek-chat">
        </div>
        <div class="field">
          <label>API 密 钥 <span class="hint">api_key</span></label>
          <input type="password" id="set-ai-key" placeholder="${ai?.has_key ? "已 存 " + ai.key_masked + "  ·  留 空 表 不 换" : "尚 未 配 置"}" autocomplete="off">
          <div style="font-family: var(--serif); font-size: 11px; color: var(--ink-soft); margin-top: 4px; letter-spacing: 0.15em;">
            存 于 根 目 录 .env  ·  即 时 生 效  ·  密 钥 只 显 掩 码
          </div>
        </div>
        <div class="btn-row">
          <button class="btn primary" id="btn-save-ai">存  入</button>
          <button class="btn ghost" id="btn-test-ai">联  通</button>
          ${ai?.has_key ? `<button class="btn ghost" id="btn-clear-ai">清 除 密 钥</button>` : ""}
        </div>
        <div id="ai-test-result" style="font-family: var(--serif); font-size: 13px; letter-spacing: 0.15em; margin-top: 8px;"></div>
      </div>

      <div class="strategy-card">
        <div style="display:flex; align-items:center; gap: 16px;">
          <div class="seal sm">${seal("知", "sm")}</div>
          <div>
            <div class="strategy-cn">系 统 资 讯</div>
            <div class="strategy-key">system info</div>
          </div>
        </div>
        <div class="strategy-params" style="grid-template-columns: 1fr 1fr;">
          <div class="param"><span class="pname">AI 点 评</span><span class="pval">${health?.ai_enabled ? "已 启" : "未 启"}</span></div>
          <div class="param"><span class="pname">缓 存 体 积</span><span class="pval">${fmtBytes(health?.cache_size_bytes || 0)}</span></div>
          <div class="param"><span class="pname">执 行 中</span><span class="pval">${health?.running_tasks || 0} 件</span></div>
          <div class="param"><span class="pname">策 略 数</span><span class="pval">${strategies.strategies?.length || 0} 件</span></div>
          <div class="param"><span class="pname">服 务 版</span><span class="pval">${health?.version || "—"}</span></div>
          <div class="param"><span class="pname">报 名</span><span class="pval">量 衡 录</span></div>
        </div>
      </div>

      <div class="strategy-card" style="background: var(--paper-deep);">
        <div style="display:flex; align-items:center; gap: 16px;">
          <div class="seal sm" style="opacity: 0.6">${seal("嘱", "sm")}</div>
          <div>
            <div class="strategy-cn" style="color: var(--vermillion)">编 者 嘱</div>
            <div class="strategy-key">disclaimer</div>
          </div>
        </div>
        <div style="font-family: var(--serif); font-size: 14px; color: var(--ink-mid); line-height: 2.2; letter-spacing: 0.1em;">
          本 报 数 据 源 于  <strong>baostock  ·  AkShare  ·  efinance</strong>  三 库 互 核 ，
          凡 错 漏 之 处  ·  概 与 沪 深 两 所 无 涉 。
          选 股 之 法  ·  皆 承 多 策 略 量 化 框 架  ·  过 往 业 绩 不 预 将 来 ；
          入 市 须 慎  ·  风 险 自 担 。
        </div>
      </div>
    </div>
  `;

  if (ai) {
    $("#set-ai-base").value = ai.ai_api_base || "";
    $("#set-ai-model").value = ai.ai_model_name || "";
  }
  const aiForm = () => ({
    ai_api_base: $("#set-ai-base").value.trim() || undefined,
    ai_model_name: $("#set-ai-model").value.trim() || undefined,
    ai_api_key: $("#set-ai-key").value.trim() || undefined,
  });
  $("#btn-save-ai").addEventListener("click", async () => {
    try {
      await api("/api/settings/ai", { method: "PUT", body: JSON.stringify(aiForm()) });
      toast("已 存  ·  即 时 生 效", "ok");
      bootstrap();
      render();
    } catch (e) {
      toast(e.message, "err");
    }
  });
  $("#btn-test-ai").addEventListener("click", async () => {
    const out = $("#ai-test-result");
    out.style.color = "var(--ink-soft)";
    out.textContent = "联 通 中 …";
    try {
      const r = await api("/api/settings/ai/test", { method: "POST", body: JSON.stringify(aiForm()) });
      out.style.color = r.ok ? "var(--ok)" : "var(--err)";
      out.textContent = (r.ok ? "○ " : "× ") + r.message + (r.latency_ms != null ? `  ·  ${r.latency_ms}ms` : "");
    } catch (e) {
      out.style.color = "var(--err)";
      out.textContent = "× " + e.message;
    }
  });
  $("#btn-clear-ai")?.addEventListener("click", async () => {
    try {
      await api("/api/settings/ai", { method: "PUT", body: JSON.stringify({ clear_key: true }) });
      toast("密 钥 已 除  ·  AI 点 评 已 停", "warn");
      bootstrap();
      render();
    } catch (e) {
      toast(e.message, "err");
    }
  });
}

/* ========== 任务 modal ========== */
function openTaskModal(taskId, typeLabel) {
  state.currentTaskPoll = { taskId, type: typeLabel, logOffset: 0, done: false };
  $("#task-modal").hidden = false;
  $("#task-modal-title").textContent = `工 程  ·  ${typeLabel}`;
  $("#task-modal-pct").textContent = "0%";
  $("#task-modal-fill").style.width = "0%";
  $("#task-modal-step").textContent = "已 入 候  ·  候 讯";
  $("#task-modal-log").textContent = "（ 日 志 待 载 ）";
  pollTask();
}

function closeTaskModal() {
  $("#task-modal").hidden = true;
  if (state.currentTaskPoll?.timer) clearInterval(state.currentTaskPoll.timer);
  state.currentTaskPoll = null;
}

async function pollTask() {
  const ctx = state.currentTaskPoll;
  if (!ctx) return;
  if (ctx.timer) clearInterval(ctx.timer);
  const tick = async () => {
    try {
      const t = await api(`/api/tasks/${ctx.taskId}`);
      $("#task-modal-pct").textContent = (t.progress ?? 0) + "%";
      $("#task-modal-fill").style.width = (t.progress ?? 0) + "%";
      $("#task-modal-step").textContent = t.step || "— · 候 讯 —";
      try {
        const lr = await api(`/api/tasks/${ctx.taskId}/logs?offset=${ctx.logOffset}`);
        if (lr.logs && lr.logs.length) {
          const stream = $("#task-modal-log");
          stream.textContent += (stream.textContent === "（ 日 志 待 载 ）" ? "" : "\n") + lr.logs.join("\n");
          stream.scrollTop = stream.scrollHeight;
          ctx.logOffset = lr.next_offset;
        }
      } catch {}
      if (["success", "failed", "cancelled"].includes(t.status)) {
        clearInterval(ctx.timer);
        ctx.done = true;
        const tag = t.status === "success" ? "已 竟  ·  功 成" : t.status === "failed" ? "已 竟  ·  失 败" : "已 撤 回";
        $("#task-modal-step").textContent = tag;
        if (t.status === "success") toast(`${ctx.type}  ·  功 成`, "ok");
        else if (t.status === "failed") toast(`${ctx.type}  ·  失 败 : ${t.error || "—"}`, "err");
        setTimeout(() => {
          closeTaskModal();
          bootstrap();
          render();
        }, 1500);
      }
    } catch (e) {
      $("#task-modal-step").textContent = "候 讯 失 败  ·  " + e.message;
    }
  };
  tick();
  ctx.timer = setInterval(tick, 2000);
}

/* ========== Helpers ========== */
function errorBlock(e) {
  const code = e.code || "error";
  return `
    <div class="empty-state">
      <div class="empty-seal">${seal("误", "md")}</div>
      <div class="empty-title" style="color: var(--err)">${escapeHtml(e.message || "错  误")}</div>
      <div class="empty-sub">code: ${escapeHtml(code)}</div>
    </div>
  `;
}

function emptyState(title, sub) {
  return `
    <div class="empty-state">
      <div class="empty-seal">${seal("空", "sm")}</div>
      <div class="empty-title">${escapeHtml(title)}</div>
      <div class="empty-sub">${escapeHtml(sub)}</div>
    </div>
  `;
}

/* === modal close === */
document.addEventListener("click", e => {
  if (e.target.matches("[data-close]")) closeTaskModal();
  if (e.target.id === "task-modal") closeTaskModal();
  if (e.target.matches("[data-close-task-center]")) closeTaskCenter();
  if (e.target.id === "task-center") closeTaskCenter();
});

/* === task badge click === */
$("#task-badge")?.addEventListener("click", openTaskCenter);
$("#task-modal-cancel").addEventListener("click", async () => {
  const ctx = state.currentTaskPoll;
  if (!ctx || ctx.done) return;
  try {
    await api(`/api/tasks/${ctx.taskId}`, { method: "DELETE" });
    toast("撤 回 令 已 传", "warn");
  } catch (e) {
    toast(e.message, "err");
  }
});

/* === 启动 === */
bootstrap().then(render);
setInterval(bootstrap, 30000);
