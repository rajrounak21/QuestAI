// Hotels API client — wraps authFetch (auto token refresh, shared with auth).
import { authFetch } from "../../auth/api";
import { unwrap, timeAgo, currencySymbol } from "../../src/shared/api";

export { timeAgo, currencySymbol };

export const hotelsApi = {
  search: async ({ query, session_id }) =>
    unwrap(
      await authFetch("/api/hotels/search", {
        method: "POST",
        body: JSON.stringify({
          query,
          ...(session_id ? { session_id } : {}),
        }),
      })
    ),
  history: async (limit = 20) =>
    unwrap(await authFetch(`/api/hotels/history?limit=${limit}`)),
  getSession: async (session_id) =>
    unwrap(await authFetch(`/api/hotels/${session_id}`)),
  searchAgain: async (session_id, query) =>
    unwrap(
      await authFetch(`/api/hotels/${session_id}/search`, {
        method: "POST",
        body: JSON.stringify({ ...(query ? { query } : {}) }),
      })
    ),
  remove: async (session_id) =>
    unwrap(await authFetch(`/api/hotels/${session_id}`, { method: "DELETE" })),
};
