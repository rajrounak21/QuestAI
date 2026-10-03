import { useState } from "react";
import { FIELD_ORDER, askFor, fieldLabel } from "./agentFields";
import "./route-receipt.css";

/**
 * One line telling the user what the universal layer did with their sentence.
 *
 * The router silently pre-filled the form, which left the user unable to tell
 * what it had understood from what it had guessed. This shows both, so a wrong
 * inference is visible and correctable rather than buried in the inputs.
 *
 * `prefill` is the hand-off object from Home via useRouterPrefill.
 */

const AGENT_LABELS = {
  research: "Research",
  shopping: "Shopping",
  jobs: "Jobs",
  flights: "Flights",
  hotels: "Hotels",
  trips: "Trips",
};

const isBlank = (v) =>
  v === "" || v === null || v === undefined || (Array.isArray(v) && !v.length);

function pairs(obj) {
  if (!obj) return [];
  return Object.entries(obj)
    .filter(([, v]) => !isBlank(v))
    .sort((a, b) => {
      const ia = FIELD_ORDER.indexOf(a[0]);
      const ib = FIELD_ORDER.indexOf(b[0]);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    })
    .map(([k, v]) => `${fieldLabel(k)}: ${Array.isArray(v) ? v.join(", ") : v}`);
}

export default function RouteReceipt({ prefill }) {
  const [dismissed, setDismissed] = useState(false);
  const receipt = prefill?.receipt;
  if (dismissed || !receipt) return null;

  const understood = pairs(receipt.understood);
  const assumed = pairs(receipt.assumed);
  const missing = receipt.missing || [];
  if (!understood.length && !assumed.length && !missing.length) return null;

  const ask = missing.slice(0, 4).map((f) => askFor(f).question);

  return (
    <div className="route-receipt" role="status">
      <span className="route-receipt-agent">
        {AGENT_LABELS[prefill.agent] || prefill.agent}
      </span>

      {understood.length > 0 && (
        <span className="route-receipt-part">
          <em>understood</em> {understood.join(" · ")}
        </span>
      )}

      {assumed.length > 0 && (
        <span className="route-receipt-part route-receipt-assumed">
          <em>assumed</em> {assumed.join(" · ")}
        </span>
      )}

      {ask.length > 0 && (
        <span className="route-receipt-part route-receipt-missing">
          <em>still needed</em> {ask.join(" ")}
        </span>
      )}

      <button
        type="button"
        className="route-receipt-x"
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        title="Dismiss"
      >
        &times;
      </button>
    </div>
  );
}