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
export async function authFetch(path, options = {}) {
  const call = (token) =>
    fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}), Authorization: `Bearer ${token}` },
      ...options,
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
