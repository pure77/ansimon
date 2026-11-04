/* ═══════════════════════════════════════════════════════════════
   안심온 — 공통 API 헬퍼
   API_BASE 를 채우면 실 백엔드, 비우면 각 페이지의 MOCK 을 사용합니다.
   응답은 백엔드 공통 포맷 {success, data, error} 를 가정합니다.
   ═══════════════════════════════════════════════════════════════ */
/* ?api= override 는 로컬 개발(localhost/127.0.0.1)에서만 받는다.
   운영에서 조작된 링크가 관리자 비밀번호·토큰을 다른 서버로 보내지 못하게 막는다. */
const LOCAL_HOST = location.hostname === "localhost" || location.hostname === "127.0.0.1";
const API_OVERRIDE = LOCAL_HOST ? new URLSearchParams(location.search).get("api") : null;
const API_BASE = String(
  window.ANSIMON_API_BASE || API_OVERRIDE || "http://localhost:8080"
).replace(/\/$/, "");

/* ── 관리자 토큰 ──
   sessionStorage: 탭을 닫으면 사라진다. 공용 PC 에 로그인이 남지 않게 localStorage 를 쓰지 않는다. */
const TOKEN_KEY = "ansimon.accessToken";
const IS_LOGIN_PAGE = /(^|\/)login\.html$/.test(location.pathname);

function getToken() { try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; } }
function setToken(token) { try { sessionStorage.setItem(TOKEN_KEY, token); } catch {} }
function clearToken() { try { sessionStorage.removeItem(TOKEN_KEY); } catch {} }
function authHeaders() { const t = getToken(); return t ? { Authorization: `Bearer ${t}` } : {}; }

/* 다른 사이트로 튕기는 오픈 리다이렉트를 막기 위해, 돌아올 곳은 같은 폴더의 .html 만 허용한다. */
function redirectToLogin() {
  clearToken();
  const here = location.pathname.split("/").pop() + location.search;
  location.href = `login.html?next=${encodeURIComponent(here)}${apiParam("&")}`;
}

/* ?api= 백엔드 override 를 로그인 화면까지 이어 준다(login.html 은 자기 쿼리에서 API_BASE 를 읽는다). */
function apiParam(prefix) {
  return API_OVERRIDE ? `${prefix}api=${encodeURIComponent(API_OVERRIDE)}` : "";
}

if (!IS_LOGIN_PAGE && !getToken()) redirectToLogin();

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
      ...authHeaders(),
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (response.status === 401 && !IS_LOGIN_PAGE) {
    redirectToLogin();
    throw Object.assign(new Error("로그인이 필요합니다."), { status: 401 });
  }
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

/* ── 로그아웃 (nav 오른쪽) ── */
document.addEventListener("DOMContentLoaded", () => {
  if (IS_LOGIN_PAGE) return;
  let navEnd = $(".nav-end");
  if (!navEnd) {
    const nav = $("nav.nav");
    if (!nav) return;
    navEnd = document.createElement("div");
    navEnd.className = "nav-end";
    nav.appendChild(navEnd);
  }
  const button = document.createElement("button");
  button.type = "button";
  button.className = "pill-btn";
  button.textContent = "로그아웃";
  button.addEventListener("click", () => { clearToken(); location.href = `login.html${apiParam("?")}`; });
  navEnd.appendChild(button);
});
