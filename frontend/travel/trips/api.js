// Trips API client — wraps authFetch (auto token refresh, shared with auth).
import { authFetch } from "../../auth/api";
import { unwrap, timeAgo, currencySymbol } from "../../src/shared/api";

export { timeAgo, currencySymbol };

export const tripsApi = {
  plan: async ({ query, session_id, parent_session_id, confirmed_scope }) =>
    unwrap(
      await authFetch("/api/trips/plan", {
        method: "POST",
        body: JSON.stringify({
          query,
          ...(session_id ? { session_id } : {}),
          ...(parent_session_id ? { parent_session_id } : {}),
          ...(confirmed_scope ? { confirmed_scope } : {}),
        }),
      })
    ),
  chat: async (session_id, message) =>
    unwrap(
      await authFetch(`/api/trips/${session_id}/chat`, {
        method: "POST",
        body: JSON.stringify({ message }),
      })
    ),
  history: async (limit = 20) =>
    unwrap(await authFetch(`/api/trips/history?limit=${limit}`)),
  getSession: async (session_id) =>
    unwrap(await authFetch(`/api/trips/${session_id}`)),
  remove: async (session_id) =>
    unwrap(await authFetch(`/api/trips/${session_id}`, { method: "DELETE" })),
  select: async (session_id, kind, item_id) =>
    unwrap(
      await authFetch(`/api/trips/${session_id}/select`, {
        method: "POST",
        body: JSON.stringify({ kind, item_id }),
      })
    ),
};
