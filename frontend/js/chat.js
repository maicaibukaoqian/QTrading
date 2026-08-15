/* =========================================================
   问股对话 UI
   依赖：app.js 提供的全局 api() / toast() / $ / $$ / escapeHtml()
   状态挂在 state.chat 上，避免污染全局
   ========================================================= */

function initChatState() {
  if (!state.chat) {
    state.chat = {
      sessions: [],
      currentSid: null,
      currentContext: null,
      isStreaming: false,
      abortController: null,
      streamMsgEl: null,
    };
  }
}

/* === 入口 === */
async function renderChatView(root) {
  initChatState();

  root.innerHTML = `
    <header class="section-head">
      <span class="section-num">贰</span>
      <span class="section-name">问  股</span>
      <span class="section-en">Chat · Ask About One Stock</span>
    </header>
    <div class="section-rule"></div>

    <div class="chat-grid">
      <div class="chat-col chat-col-left">
        <div class="chat-search">
          <input type="text" id="chat-search-input" maxlength="6"
                 placeholder="代码 / 名称" inputmode="numeric">
          <button id="chat-new-btn" title="新会话">＋</button>
        </div>
        <div class="chat-col-body" id="chat-sessions-list">
          <div class="chat-empty">候 讯 中</div>
        </div>
      </div>

      <div class="chat-col chat-col-mid">
        <div class="chat-header-info" id="chat-header">
          <span>请 选 择 一 只 股 票 开 始</span>
        </div>
        <div class="chat-messages" id="chat-messages">
          <div class="chat-empty" style="margin: auto;">
            左 侧 输 入 6 位 代 码<br>或 点 击 旧 会 话
          </div>
        </div>
        <div class="chat-input-area">
          <textarea id="chat-input" rows="1"
                    placeholder="例 ：这只股现在能买吗 ？"
                    disabled></textarea>
          <button id="chat-send-btn" disabled>发  送</button>
        </div>
      </div>

      <div class="chat-col chat-col-right">
        <div class="chat-col-head">实 时 行 情</div>
        <div class="chat-col-body" id="chat-context">
          <div class="context-card-empty">未 选 股</div>
        </div>
      </div>
    </div>
  `;

  // 事件绑定
  const searchInput = $("#chat-search-input");
  const newBtn = $("#chat-new-btn");
  searchInput.addEventListener("input", e => {
    e.target.value = e.target.value.replace(/\D/g, "").slice(0, 6);
  });
  searchInput.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); createFromInput(); }
  });
  newBtn.addEventListener("click", createFromInput);

  $("#chat-send-btn").addEventListener("click", sendCurrent);
  $("#chat-input").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendCurrent();
    }
  });
  $("#chat-input").addEventListener("input", autoResizeTextarea);
  document.addEventListener("keydown", globalEscHandler);

  // 加载会话列表
  await refreshSessions();
  if (state.chat.sessions.length > 0) {
    await selectSession(state.chat.sessions[0].id);
  } else {
    $("#chat-search-input").focus();
  }
}

function autoResizeTextarea() {
  const ta = $("#chat-input");
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
}

function globalEscHandler(e) {
  if (e.key === "Escape" && state.chat?.isStreaming) {
    cancelStream();
  }
}

/* === 会话列表 === */
async function refreshSessions() {
  try {
    const list = await api("/api/chat/sessions");
    state.chat.sessions = list;
    renderSessionsList();
  } catch (e) {
    $("#chat-sessions-list").innerHTML = `<div class="chat-empty">读 取 失 败 ：${escapeHtml(e.message)}</div>`;
  }
}

function renderSessionsList() {
  const el = $("#chat-sessions-list");
  const list = state.chat.sessions;
  if (list.length === 0) {
    el.innerHTML = `<div class="chat-empty">尚 无 会 话</div>`;
    return;
  }
  el.innerHTML = list.map(s => `
    <div class="session-item ${s.id === state.chat.currentSid ? "active" : ""}"
         data-sid="${s.id}">
      <span class="session-item-code">${escapeHtml(s.code)}</span>
      <span class="session-item-title">${escapeHtml(s.title)}</span>
      <button class="session-item-del" data-del="${s.id}" title="删除">×</button>
    </div>
  `).join("");
  el.querySelectorAll(".session-item").forEach(item => {
    item.addEventListener("click", e => {
      if (e.target.dataset.del) return;
      selectSession(item.dataset.sid);
    });
  });
  el.querySelectorAll("[data-del]").forEach(btn => {
    btn.addEventListener("click", async e => {
      e.stopPropagation();
      const sid = btn.dataset.del;
      if (!confirm("删 除 此 会 话 ？")) return;
      try {
        await api(`/api/chat/sessions/${sid}`, { method: "DELETE" });
        if (state.chat.currentSid === sid) {
          state.chat.currentSid = null;
          clearChatView();
        }
        await refreshSessions();
        toast("会 话 已 除", "ok");
      } catch (err) {
        toast(err.message, "err");
      }
    });
  });
}

/* === 新建会话 === */
async function createFromInput() {
  const code = $("#chat-search-input").value.trim();
  if (!/^\d{6}$/.test(code)) {
    toast("须 为 六 位 数 代 码", "warn");
    return;
  }
  if (state.chat.isStreaming) cancelStream();
  $("#chat-new-btn").disabled = true;
  try {
    const s = await api("/api/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ code, title: `关于 ${code} 的对话` }),
    });
    $("#chat-search-input").value = "";
    await refreshSessions();
    await selectSession(s.id);
  } catch (e) {
    toast(e.message, "err");
  } finally {
    $("#chat-new-btn").disabled = false;
  }
}

/* === 选中会话 === */
async function selectSession(sid) {
  if (state.chat.isStreaming) cancelStream();
  state.chat.currentSid = sid;
  renderSessionsList();

  try {
    const data = await api(`/api/chat/sessions/${sid}`);
    const code = data.session.code;
    $("#chat-header").innerHTML = `
      <span><span class="code">${escapeHtml(code)}</span>  ${escapeHtml(data.session.title)}</span>
      <span style="color: var(--ink-soft)">${data.messages.length} 条 往 复</span>
    `;
    renderMessages(data.messages);
    await loadContext(code);
    enableInput();
  } catch (e) {
    toast(e.message, "err");
  }
}

function clearChatView() {
  $("#chat-header").innerHTML = `<span>请 选 择 一 只 股 票 开 始</span>`;
  $("#chat-messages").innerHTML = `<div class="chat-empty" style="margin:auto;">左 侧 输 入 6 位 代 码<br>或 点 击 旧 会 话</div>`;
  $("#chat-context").innerHTML = `<div class="context-card-empty">未 选 股</div>`;
  state.chat.currentContext = null;
  $("#chat-input").disabled = true;
  $("#chat-send-btn").disabled = true;
}

function enableInput() {
  $("#chat-input").disabled = false;
  $("#chat-send-btn").disabled = false;
  $("#chat-input").focus();
}

/* === 行情卡 === */
async function loadContext(code) {
  const el = $("#chat-context");
  el.innerHTML = `<div class="context-card-empty">候 讯 中</div>`;
  try {
    // 行情 + 风险评分并行拉
    const [ctx, risk] = await Promise.all([
      api(`/api/stock/${code}/context`),
      api(`/api/stock/${code}/risk`).catch(() => null),
    ]);
    state.chat.currentContext = ctx;
    state.chat.currentRisk = risk;
    renderContextCard(ctx, risk);
  } catch (e) {
    el.innerHTML = `<div class="context-card-empty">读 取 失 败</div>`;
  }
}

function renderStars(n) {
  const filled = "★".repeat(n);
  const empty = "☆".repeat(5 - n);
  return filled + empty;
}

function renderContextCard(ctx, risk) {
  const fmt = (v, suf = "", d = 2) => {
    if (v == null) return "—";
    if (typeof v === "number") return v.toFixed(d) + suf;
    return v + suf;
  };
  const changeCls = ctx.change_pct > 0 ? "up" : ctx.change_pct < 0 ? "down" : "";
  const changeStr = ctx.change_pct != null
    ? `${ctx.change_pct > 0 ? "+" : ""}${fmt(ctx.change_pct, "%")}`
    : "—";

  // 风险卡 HTML（容错：risk 为 null 时跳过）
  let riskHtml = "";
  if (risk) {
    const stars = Number(risk.stars) || 0;
    const level = risk.level || "—";
    const warnings = Array.isArray(risk.warnings) ? risk.warnings : [];
    const dimLabels = {
      valuation: "估 值",
      leverage: "负 债",
      profitability: "盈 利",
      st_status: "ST 标",
      size: "规 模",
      policy: "政 策",
      liquidity: "流 动",
    };
    const dimBars = Object.entries(risk.dimensions || {})
      .map(([k, v]) => {
        const score = v?.score ?? 3;
        const fillPct = (score / 5) * 100;
        return `
          <div class="risk-dim" title="${escapeHtml(v?.reason || "")}">
            <span class="risk-dim-name">${dimLabels[k] || k}</span>
            <span class="risk-dim-bar"><span class="risk-dim-bar-fill" data-level="${score}" style="width:${fillPct}%"></span></span>
            <span class="risk-dim-score">${score}</span>
          </div>`;
      })
      .join("");
    const warningList = warnings.length
      ? `<ul class="risk-warnings">${warnings.map(w => `<li>⚠ ${escapeHtml(w)}</li>`).join("")}</ul>`
      : `<div class="risk-warnings-empty">✓ 暂无显著风险点</div>`;
    riskHtml = `
      <div class="context-card-risk">
        <div class="risk-stars">
          <span class="risk-stars-glyphs" aria-label="${stars} 星安全度">${renderStars(stars)}</span>
          <span class="risk-level">${escapeHtml(level)}</span>
        </div>
        <div class="risk-dims">${dimBars}</div>
        ${warningList}
      </div>
    `;
  }

  $("#chat-context").innerHTML = `
    <div class="context-card">
      <div class="context-card-name">${escapeHtml(ctx.name || "—")}</div>
      <div class="context-card-code">${escapeHtml(ctx.code)}  ·  ${escapeHtml(ctx.industry || "—")}</div>
      <div class="context-card-row">
        <span class="context-card-label">现  价</span>
        <span class="context-card-value ${changeCls}">${fmt(ctx.current_price)}  ${changeStr}</span>
      </div>
      <div class="context-card-row">
        <span class="context-card-label">PE</span>
        <span class="context-card-value">${fmt(ctx.pe)}</span>
      </div>
      <div class="context-card-row">
        <span class="context-card-label">PB</span>
        <span class="context-card-value">${fmt(ctx.pb)}</span>
      </div>
      <div class="context-card-row">
        <span class="context-card-label">ROE</span>
        <span class="context-card-value">${fmt(ctx.latest_roe, "%")}</span>
      </div>
      <div class="context-card-row">
        <span class="context-card-label">5 日 线</span>
        <span class="context-card-value">${fmt(ctx.ma5)}</span>
      </div>
      <div class="context-card-row">
        <span class="context-card-label">乖 离 率</span>
        <span class="context-card-value ${ctx.bias_ma5 > 2 ? "up" : ctx.bias_ma5 < -2 ? "down" : ""}">${fmt(ctx.bias_ma5, "%")}</span>
      </div>
      ${riskHtml}
    </div>
  `;
}

/* === 消息渲染 === */
function renderMessages(messages) {
  const el = $("#chat-messages");
  if (messages.length === 0) {
    el.innerHTML = `<div class="chat-empty" style="margin:auto;">发 出 第 一 问</div>`;
    return;
  }
  el.innerHTML = "";
  for (const m of messages) {
    appendMessageEl(m.role, m.content, m.id);
  }
  scrollToBottom();
}

function appendMessageEl(role, content, messageId = null) {
  const el = document.createElement("div");
  el.className = `chat-msg chat-msg-${role}`;
  el.textContent = content;
  if (messageId) el.dataset.messageId = messageId;
  $("#chat-messages").appendChild(el);
  scrollToBottom();
  return el;
}

function scrollToBottom() {
  const el = $("#chat-messages");
  el.scrollTop = el.scrollHeight;
}

/* === 发送 + 流式 === */
async function sendCurrent() {
  if (!state.chat.currentSid) return;
  const ta = $("#chat-input");
  const content = ta.value.trim();
  if (!content) return;
  if (state.chat.isStreaming) return;

  appendMessageEl("user", content);
  ta.value = "";
  autoResizeTextarea();
  ta.disabled = true;
  $("#chat-send-btn").disabled = true;
  $("#chat-send-btn").textContent = "取  消";
  $("#chat-send-btn").classList.add("cancel");
  $("#chat-send-btn").onclick = cancelStream;

  state.chat.isStreaming = true;
  state.chat.abortController = new AbortController();
  state.chat.streamMsgEl = appendMessageEl("assistant", "");
  state.chat.streamMsgEl.classList.add("streaming");

  try {
    const resp = await fetch(`/api/chat/sessions/${state.chat.currentSid}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
      signal: state.chat.abortController.signal,
    });

    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${errText.slice(0, 100)}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullText = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop();
      for (const evt of events) {
        const m = evt.match(/^data: (.+)$/m);
        if (!m) continue;
        let data;
        try { data = JSON.parse(m[1]); } catch { continue; }
        if (data.chunk) {
          fullText += data.chunk;
          state.chat.streamMsgEl.textContent = fullText;
          scrollToBottom();
        } else if (data.done) {
          state.chat.streamMsgEl.dataset.messageId = data.message_id;
        } else if (data.error) {
          throw new Error(data.error);
        }
      }
    }
  } catch (e) {
    if (e.name === "AbortError") {
      state.chat.streamMsgEl.textContent =
        (state.chat.streamMsgEl.textContent || "") + " [已 中 断]";
      toast("已 撤 回 流 式 输 出", "warn");
    } else {
      state.chat.streamMsgEl.textContent = "× " + e.message;
      state.chat.streamMsgEl.classList.remove("streaming");
      state.chat.streamMsgEl.classList.add("chat-msg-system");
      toast("出 错 ：" + e.message, "err");
    }
  } finally {
    finalizeStream();
  }
}

function cancelStream() {
  if (state.chat.abortController) {
    state.chat.abortController.abort();
  }
}

function finalizeStream() {
  if (state.chat.streamMsgEl) {
    state.chat.streamMsgEl.classList.remove("streaming");
  }
  state.chat.streamMsgEl = null;
  state.chat.abortController = null;
  state.chat.isStreaming = false;
  const ta = $("#chat-input");
  ta.disabled = false;
  $("#chat-send-btn").disabled = false;
  $("#chat-send-btn").textContent = "发  送";
  $("#chat-send-btn").classList.remove("cancel");
  $("#chat-send-btn").onclick = sendCurrent;
  ta.focus();
}
