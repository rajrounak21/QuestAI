// Simple API connection for QuestAI Auth (backend on :8000)
export const API_BASE = "http://localhost:8000";

function request(path, options = {}) {
  return fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  })
    .catch(() => {
      throw new Error(`Cannot reach auth server at ${API_BASE}. Start the backend first.`);
    })
    .then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Request failed");
      return data;
    });
}

export const authApi = {
  signup: (email, password, name) =>
    request("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),
  login: (email, password) =>
    request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: (token) =>
    request("/api/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    }),
  refresh: (refreshToken) =>
    request("/api/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
  requestCode: (email) =>
    request("/api/auth/request-code", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  verifyCode: (email, code) =>
    request("/api/auth/verify-code", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    }),
  forgotPassword: (email) =>
    request("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  resetPassword: (email, code, newPassword) =>
    request("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ email, code, new_password: newPassword }),
    }),
  // Google OAuth: just redirect the browser, backend handles the rest
  googleLogin: () => {
    window.location.href = `${API_BASE}/api/auth/google/login`;
  },
};

export const storeToken = (token) => localStorage.setItem("questai_token", token);
export const getToken = () => localStorage.getItem("questai_token");
export const clearToken = () => localStorage.removeItem("questai_token");
export const storeRefresh = (token) => localStorage.setItem("questai_refresh", token);
export const getRefresh = () => localStorage.getItem("questai_refresh");
export const clearAuth = () => {
  localStorage.removeItem("questai_token");
  localStorage.removeItem("questai_refresh");
};

// Auto-refreshing fetch: tries the request, and on 401 silently renews
// the access token with the refresh token and retries once.
//  - { unauthorized: true } -> real auth failure (bad/expired tokens) -> go to login
//  - { networkError: true } -> backend unreachable, tokens untouched -> show retry
async function authedRequest(path, options, json) {
  // headers is pulled out of options and merged explicitly so a caller-supplied
  // headers object can never clobber the Authorization header.
  const { headers: extraHeaders, ...rest } = options;
  const call = (token) =>
    fetch(`${API_BASE}${path}`, {
      ...rest,
      headers: {
        ...(json ? { "Content-Type": "application/json" } : {}),
        ...(extraHeaders || {}),
        Authorization: `Bearer ${token}`,
      },
    });

  let res;
  try {
    res = await call(getToken());
  } catch {
    return { networkError: true };
  }
  if (res.status !== 401) return res;

  try {
    const data = await authApi.refresh(getRefresh());
    storeToken(data.access_token);
    storeRefresh(data.refresh_token);
    try {
      res = await call(data.access_token);
    } catch {
      return { networkError: true };
    }
    if (res.status === 401) return { unauthorized: true };
    return res;
  } catch (err) {
    // refresh() throwing on TypeError = backend down, not bad credentials.
    // request() only throws Error(detail) on HTTP errors vs TypeError on network fail.
    if (err instanceof TypeError || /Cannot reach auth server/.test(err.message || "")) {
      return { networkError: true };
    }
    return { unauthorized: true };
  }
}

export async function authFetch(path, options = {}) {
  return authedRequest(path, options, true);
}

// For multipart/form-data bodies (e.g. resume upload). Content-Type is
// deliberately omitted so the browser can set it with the multipart boundary —
// hardcoding application/json (or setting it manually without a boundary)
// corrupts the upload.
export async function authFetchForm(path, formData, options = {}) {
  return authedRequest(path, { method: "POST", ...options, body: formData }, false);
}

// --- Universal layer -------------------------------------------------------
// These only CHOOSE an agent and pre-extract its form fields. Neither one runs
// a search: the destination page pre-fills and the user presses Search.
//
// authFetch hands back the raw fetch Response (that is the convention every
// other caller unwraps with .json() or unwrap()), so the parsing happens here.
// A Response has no .agent, which is why this must not be skipped.

export async function routeIntent(query) {
  const res = await authFetch("/api/agent/route", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
  if (res.unauthorized || res.networkError) return res; // flag objects, pass through
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Request failed");
  return data;
}

export async function askAssistant(text) {
  const res = await authFetch("/api/assistant/chat", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
  if (res.unauthorized || res.networkError) return res;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Request failed");
  return data;
}
