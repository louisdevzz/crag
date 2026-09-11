/**
 * Legal CRAG Assistant V3 — Frontend Client
 * Communicates with FastAPI Gateway to drive CRAG workflow & memory.
 */

const API_BASE = window.location.origin;

// Client State
let clientId = localStorage.getItem("legal_crag_client_id");
if (!clientId) {
  clientId = "client_" + Math.random().toString(36).substring(2, 11);
  localStorage.setItem("legal_crag_client_id", clientId);
}

let sessionId = "session_" + Math.random().toString(36).substring(2, 11);

// DOM Elements
const chatStream = document.getElementById("chat-stream");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const btnSend = document.getElementById("btn-send");
const asOfDateInput = document.getElementById("as-of-date");
const memoryCard = document.getElementById("memory-card");
const docList = document.getElementById("doc-list");
const tracePanel = document.getElementById("trace-panel");
const btnToggleTrace = document.getElementById("btn-toggle-trace");
const btnCloseTrace = document.getElementById("btn-close-trace");
const btnNewChat = document.getElementById("btn-new-chat");

const traceRoute = document.getElementById("trace-route");
const traceAction = document.getElementById("trace-action");
const traceCitation = document.getElementById("trace-citation");
const evidenceList = document.getElementById("evidence-list");

// Initialize on Load
document.addEventListener("DOMContentLoaded", () => {
  fetchDocuments();
  fetchMemoryProfile();
  setupEventListeners();
});

function setupEventListeners() {
  // Chat submit
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    handleSend();
  });

  // Enter to send (Shift+Enter for newline)
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Toggle Trace Panel
  btnToggleTrace.addEventListener("click", () => {
    tracePanel.classList.toggle("active");
  });

  btnCloseTrace.addEventListener("click", () => {
    tracePanel.classList.remove("active");
  });

  // New Chat
  btnNewChat.addEventListener("click", () => {
    sessionId = "session_" + Math.random().toString(36).substring(2, 11);
    chatStream.innerHTML = `
      <div class="welcome-hero">
        <div class="welcome-badge">Phiên làm việc mới đã bắt đầu</div>
        <h1>Trợ lý Tuân thủ & Pháp lý Doanh nghiệp</h1>
        <p>Hệ thống tự động đánh giá chất lượng bằng chứng và tự hiệu chỉnh truy hồi qua 3 nhánh CRAG.</p>
      </div>
    `;
    resetTracePanel();
  });

  // Prompt chips
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const q = chip.getAttribute("data-query");
      if (q) {
        chatInput.value = q;
        handleSend();
      }
    });
  });
}

async function handleSend() {
  const query = chatInput.value.trim();
  if (!query) return;

  const asOfDate = asOfDateInput.value;

  // Append User message
  appendMessage("user", query);
  chatInput.value = "";
  chatInput.style.height = "auto";
  btnSend.disabled = true;

  // Append Assistant loading bubble
  const loadingId = appendLoadingBubble();

  try {
    const resp = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: query,
        client_id: clientId,
        session_id: sessionId,
        as_of_date: asOfDate,
      }),
    });

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
    }

    const data = await resp.json();
    removeLoadingBubble(loadingId);

    // Render Answer
    const answer = data.generation?.answer || "Không nhận được câu trả lời từ hệ thống.";
    appendMessage("assistant", answer, data.citation_report);

    // Update Trace Drawer & Memory
    updateTraceDrawer(data);
    fetchMemoryProfile();
  } catch (err) {
    removeLoadingBubble(loadingId);
    appendMessage("assistant", `Lỗi kết nối hoặc xử lý: ${err.message}`);
  } finally {
    btnSend.disabled = false;
  }
}

function appendMessage(sender, text, citationReport = null) {
  const bubble = document.createElement("div");
  bubble.className = `message-bubble ${sender}`;

  const senderLabel = document.createElement("div");
  senderLabel.className = "bubble-sender";
  senderLabel.textContent = sender === "user" ? "BẠN" : "TRỢ LÝ PHÁP LÝ AI";

  const content = document.createElement("div");
  content.className = "bubble-content";
  content.innerHTML = formatMarkdown(text);

  bubble.appendChild(senderLabel);
  bubble.appendChild(content);
  chatStream.appendChild(bubble);

  // Scroll to bottom
  chatStream.scrollTop = chatStream.scrollHeight;
}

function appendLoadingBubble() {
  const id = "loading_" + Date.now();
  const bubble = document.createElement("div");
  bubble.id = id;
  bubble.className = "message-bubble assistant";
  bubble.innerHTML = `
    <div class="bubble-sender">TRỢ LÝ PHÁP LÝ AI</div>
    <div class="bubble-content" style="color: var(--text-muted); font-style: italic;">
      Đang phân luồng và truy hồi bằng chứng pháp lý...
    </div>
  `;
  chatStream.appendChild(bubble);
  chatStream.scrollTop = chatStream.scrollHeight;
  return id;
}

function removeLoadingBubble(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function formatMarkdown(text) {
  if (!text) return "";
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Bold **text**
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  // Italic *text*
  html = html.replace(/\*(.*?)\*/g, "<em>$1</em>");
  // Newlines
  html = html.replace(/\n/g, "<br/>");
  // Citations [DOC_...] or [EXT_...]
  html = html.replace(/\[([A-Z0-9_\-]+)\]/g, `<span class="citation-tag">[$1]</span>`);

  return html;
}

function updateTraceDrawer(data) {
  // Route
  const route = data.route || "rag";
  traceRoute.textContent = route.toUpperCase();
  traceRoute.className = `trace-value badge-${route === "database" ? "database" : "neutral"}`;

  // Action
  const action = (data.crag_action || "CORRECT").toUpperCase();
  traceAction.textContent = action;
  if (action === "CORRECT") {
    traceAction.className = "trace-value badge-correct";
  } else if (action === "AMBIGUOUS") {
    traceAction.className = "trace-value badge-ambiguous";
  } else if (action === "INCORRECT") {
    traceAction.className = "trace-value badge-incorrect";
  } else {
    traceAction.className = "trace-value badge-neutral";
  }

  // Citation Report
  const citeOk = data.citation_report?.ok;
  if (citeOk) {
    const acc = Math.round((data.citation_report?.citation_accuracy || 1.0) * 100);
    traceCitation.textContent = `HỢP LỆ (${acc}%)`;
    traceCitation.className = "trace-value badge-correct";
  } else {
    const errCount = data.citation_report?.errors?.length || 1;
    traceCitation.textContent = `CẢNH BÁO (${errCount} lỗi)`;
    traceCitation.className = "trace-value badge-incorrect";
  }

  // Evidence List
  const evidence = data.evidence || [];
  if (evidence.length === 0) {
    evidenceList.innerHTML = `<div class="evidence-empty">Không có trích đoạn bằng chứng nào.</div>`;
    return;
  }

  evidenceList.innerHTML = evidence
    .map((ev) => {
      const sid = ev.strip_id || ev.locator || ev.evidence_id || "EV";
      const heading = ev.heading || "Điều khoản";
      const score = ev.score !== undefined ? `${(ev.score * 100).toFixed(1)}%` : "N/A";
      const text = ev.text || "";

      return `
        <div class="evidence-card">
          <div class="evidence-meta">
            <span class="evidence-id">${sid}</span>
            <span class="evidence-score">Điểm: ${score}</span>
          </div>
          <div class="evidence-heading">${heading}</div>
          <div class="evidence-text">${text}</div>
        </div>
      `;
    })
    .join("");
}

function resetTracePanel() {
  traceRoute.textContent = "—";
  traceRoute.className = "trace-value badge-neutral";
  traceAction.textContent = "—";
  traceAction.className = "trace-value badge-neutral";
  traceCitation.textContent = "—";
  traceCitation.className = "trace-value badge-neutral";
  evidenceList.innerHTML = `<div class="evidence-empty">Chưa có truy vấn nào được thực hiện.</div>`;
}

async function fetchDocuments() {
  try {
    const resp = await fetch(`${API_BASE}/api/documents`);
    if (!resp.ok) return;
    const docs = await resp.json();

    if (docs.length === 0) {
      docList.innerHTML = `<div class="doc-loading">Chưa nạp văn bản nào.</div>`;
      return;
    }

    docList.innerHTML = docs
      .slice(0, 5)
      .map(
        (d) => `
      <div class="doc-item">
        <span class="doc-num">${d.document_number}</span>
        <span class="doc-title">${d.title}</span>
      </div>
    `
      )
      .join("");
  } catch (e) {
    docList.innerHTML = `<div class="doc-loading">Không thể tải CSDL.</div>`;
  }
}

async function fetchMemoryProfile() {
  try {
    const resp = await fetch(`${API_BASE}/api/memory/${clientId}`);
    if (!resp.ok) return;
    const data = await resp.json();
    const mems = data.memories || {};

    const keys = Object.keys(mems);
    if (keys.length === 0) {
      memoryCard.innerHTML = `<div class="memory-placeholder">Chưa ghi nhận bối cảnh doanh nghiệp. Hãy nêu thông tin công ty để AI ghi nhớ.</div>`;
      return;
    }

    const labels = {
      business_type: "Loại hình:",
      province: "Địa bàn:",
      industry: "Ngành nghề:",
      frequent_topic: "Chủ đề:",
      preferred_answer: "Phong cách:",
    };

    memoryCard.innerHTML = keys
      .map(
        (k) => `
      <div class="memory-item">
        <span class="memory-key">${labels[k] || k}</span>
        <span class="memory-val">${mems[k]}</span>
      </div>
    `
      )
      .join("");
  } catch (e) {
    // Ignore error
  }
}
