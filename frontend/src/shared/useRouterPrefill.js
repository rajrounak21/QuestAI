import { useLocation } from "react-router-dom";

/**
 * Reads the pre-extracted fields the universal layer handed over during
 * navigation.
 *
 * The Home page calls the intent router, which returns both a specialist and
 * the fields for that specialist's form. Those travel in React Router's
 * `location.state`, NOT the URL, for two reasons: the URL stays clean, and the
 * hand-off dies with the navigation — so a refresh cannot re-apply values the
 * user has since edited. On refresh the page falls back to its own `?q=`
 * parser instead.
 *
 * Returns null when there is no hand-off, which is the normal case for a
 * direct visit, a bookmark, or a refresh.
 */
export function useRouterPrefill(expectedAgent) {
  const location = useLocation();
  const prefill = location.state?.prefill;
  if (!prefill || typeof prefill !== "object") return null;
  if (expectedAgent && prefill.agent && prefill.agent !== expectedAgent) return null;
  return prefill;
}
