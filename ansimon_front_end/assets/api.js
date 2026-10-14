/* ═══════════════════════════════════════════════════════════════
   안심온 — 공통 API 헬퍼
   API_BASE 를 채우면 실 백엔드, 비우면 각 페이지의 MOCK 을 사용합니다.
   응답은 백엔드 공통 포맷 {success, data, error} 를 가정합니다.
   ═══════════════════════════════════════════════════════════════ */
const API_BASE = String(
  window.ANSIMON_API_BASE || new URLSearchParams(location.search).get("api") || "http://localhost:8080"
).replace(/\/$/, "");

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (ch) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
}[ch]));

async function apiRequest(path, { method = "GET", body } = {}) {
  const response = await fetch(API_BASE + path, {
    method,
    headers: {
      Accept: "application/json",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.success === false) {
    const err = new Error(payload.error?.message || `HTTP ${response.status}`);
    err.code = payload.error?.code;
    err.status = response.status;
    err.details = payload.error?.details;
    throw err;
  }
  return "data" in payload ? payload.data : payload;
}

const api = {
  get: (path) => apiRequest(path),
  post: (path, body) => apiRequest(path, { method: "POST", body }),
  patch: (path, body) => apiRequest(path, { method: "PATCH", body }),
  del: (path) => apiRequest(path, { method: "DELETE" }),
};

/* ── 토스트 알림 (모든 페이지 공통 #toast 요소를 사용) ── */
let toastTimer = null;
function notify(message, opts = {}) {
  const toast = $("#toast");
  if (!toast) { console.warn("[안심온]", message); return; }
  toast.textContent = message;
  toast.classList.toggle("error", !!opts.error);
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3400);
}

/* ── 동의 상태 라벨 ── */
const CONSENT_LABEL = { consented: "동의", not_consented: "미동의", withdrawn: "철회" };
const TRISTATE_LABEL = { YES: "예", NO: "아니오", UNKNOWN: "확인 안 됨" };
const CONTACT_LABEL = {
  PENDING: "통화 전", READY_FOR_REVIEW: "발신 준비", SCHEDULED: "발신 예정",
  ANSWERED: "응답 완료", UNCONFIRMED: "미응답", FAILED: "발신 실패",
  ANALYZED: "분석 완료", ACTION_REQUIRED: "조치 필요", COMPLETED: "완료",
};

function avatarText(name) { return String(name || "—").replace(/○/g, "").slice(0, 2); }
