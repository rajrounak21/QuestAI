// Flights API client — wraps authFetch (auto token refresh, shared with auth).
import { authFetch } from "../../auth/api";
import { unwrap, timeAgo, currencySymbol } from "../../src/shared/api";

export { timeAgo, currencySymbol };

export const flightsApi = {
  search: async ({ query, session_id }) =>
    unwrap(
      await authFetch("/api/flights/search", {
        method: "POST",
        body: JSON.stringify({
          query,
          ...(session_id ? { session_id } : {}),
        }),
      })
    ),
  history: async (limit = 20) =>
    unwrap(await authFetch(`/api/flights/history?limit=${limit}`)),
  getSession: async (session_id) =>
    unwrap(await authFetch(`/api/flights/${session_id}`)),
  searchAgain: async (session_id, query) =>
    unwrap(
      await authFetch(`/api/flights/${session_id}/search`, {
        method: "POST",
        body: JSON.stringify({ ...(query ? { query } : {}) }),
      })
    ),
  remove: async (session_id) =>
    unwrap(await authFetch(`/api/flights/${session_id}`, { method: "DELETE" })),
  bookingOptions: async (payload) =>
    unwrap(
      await authFetch("/api/flights/booking-options", {
        method: "POST",
        body: JSON.stringify(payload),
      })
    ),
};
