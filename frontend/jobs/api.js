// Jobs API — authenticated via the main app's JWT.
// Auth identity comes from the Bearer token, so there is no session_id to manage.
import { authFetch, authFetchForm, getToken } from "../auth/api";
import { unwrap } from "../src/shared/api";

// ---- profile / onboarding ----

export async function getProfile() {
  return unwrap(await authFetch("/api/jobs/profile"));
}

// Fetches the stored PDF as a Blob. The panel turns it into an object URL —
// the browser's PDF viewer needs a real URL, and this keeps the Bearer token
// out of the URL entirely.
export async function fetchResumePdf() {
  const res = await authFetch("/api/jobs/profile/resume");
  if (!res || res.unauthorized || res.networkError) return null;
  if (!res.ok) return null;
  return res.blob();
}

// One-time resume upload. Multipart, so it must not set Content-Type itself.
export async function uploadResume(file) {
  const form = new FormData();
  form.append("resume", file);
  return unwrap(await authFetchForm("/api/jobs/profile", form));
}

export async function updatePreferences({ target_roles, locations, work_mode }) {
  return unwrap(
    await authFetch("/api/jobs/profile", {
      method: "PATCH",
      body: JSON.stringify({ target_roles, locations, work_mode }),
    })
  );
}

export async function deleteProfile() {
  return unwrap(await authFetch("/api/jobs/profile", { method: "DELETE" }));
}

// ---- search ----

// Resume is optional. After onboarding the server reuses the stored skills,
// so this is normally a text-only query.
export async function searchJobs({ query, resumeFile, locations, sessionId }) {
  const form = new FormData();
  if (query) form.append("query", query);
  if (resumeFile) form.append("resume", resumeFile);
  if (locations) form.append("locations", locations);
  if (sessionId) form.append("session_id", sessionId);
  return unwrap(await authFetchForm("/api/jobs/search", form));
}

export async function getHistory(limit = 20) {
  return unwrap(await authFetch(`/api/jobs/history?limit=${limit}`));
}

export async function getSession(sessionId) {
  return unwrap(await authFetch(`/api/jobs/${sessionId}`));
}

export async function searchAgain(sessionId, { query, locations }) {
  return unwrap(
    await authFetch(`/api/jobs/${sessionId}/search`, {
      method: "POST",
      body: JSON.stringify({ query, locations }),
    })
  );
}

export async function deleteSession(sessionId) {
  return unwrap(await authFetch(`/api/jobs/${sessionId}`, { method: "DELETE" }));
}

// ---- job alerts ----
// One alert per user, stored in Mongo, scoped by the caller's JWT. The scheduled
// routes (GET /alerts/due, POST /alerts/{id}/run) are service-key only and are
// never called from the browser — the browser has no way to trigger a run, so
// n8n owns that entirely.

export async function createAlert(payload) {
  return unwrap(await authFetch("/api/jobs/alerts", {
    method: "POST",
    body: JSON.stringify(payload),
  }));
}

export async function getAlerts() {
  return unwrap(await authFetch("/api/jobs/alerts"));
}

export async function getAlert(alertId) {
  return unwrap(await authFetch(`/api/jobs/alerts/${alertId}`));
}

// Edit the existing alert. Roles, locations, email, time, frequency and the
// paused state can change; alert_id and `sent` never do.
export async function patchAlert(payload) {
  return unwrap(await authFetch("/api/jobs/alerts", {
    method: "PATCH",
    body: JSON.stringify(payload),
  }));
}

// Owner-scoped delete — no id, so it can never reach another user's alert.
export async function deleteAlert() {
  return unwrap(await authFetch("/api/jobs/alerts", { method: "DELETE" }));
}

export async function getDueAlerts(now) {
  return unwrap(await authFetch(`/api/jobs/alerts/due${now ? `?now=${encodeURIComponent(now)}` : ""}`));
}
