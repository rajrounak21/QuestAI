import { useState } from "react";
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

const FIELD_LABELS = {
  origin: "from",
  destination: "to",
  departure_date: "leaves",
  return_date: "returns",
  check_in: "check-in",
  check_out: "check-out",
  location: "location",
  guests: "guests",
  passengers: "passengers",
  travelers: "travelers",
  cabin: "cabin",
  budget_max: "budget",
  duration_days: "nights",
  roles: "roles",
  locations: "locations",
  work_mode: "work mode",
  query: "query",
};

const AGENT_LABELS = {
  research: "Research",
  shopping: "Shopping",
  jobs: "Jobs",
  flights: "Flights",
  hotels: "Hotels",
  trips: "Trips",
};

// Order the receipt reads the way the request did, not alphabetically.
const ORDER = [
  "roles", "locations", "work_mode",
  "origin", "destination", "departure_date", "return_date",
  "location", "check_in", "check_out",
  "duration_days", "travelers", "budget_max",
  "guests", "passengers", "cabin",
  "query",
];

const label = (k) => FIELD_LABELS[k] || k.replace(/_/g, " ");

function pairs(obj) {
  if (!obj) return [];
  return Object.entries(obj)
    .filter(([, v]) => v !== "" && v !== null && v !== undefined && !(Array.isArray(v) && !v.length))
    .sort((a, b) => {
      const ia = ORDER.indexOf(a[0]);
      const ib = ORDER.indexOf(b[0]);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    })
    .map(([k, v]) => `${label(k)}: ${Array.isArray(v) ? v.join(", ") : v}`);
}

const FIELD_QUESTIONS = {
  origin: "Where are you flying from?",
  destination: "Where are you flying to?",
  departure_date: "What date do you want to travel?",
  return_date: "What date do you want to come back?",
  check_in: "What date do you check in?",
  check_out: "What date do you check out?",
  location: "Which city or area?",
  roles: "What role are you looking for?",
  locations: "Any preferred locations?",
};

export default function RouteReceipt({ prefill }) {
  const [dismissed, setDismissed] = useState(false);
  const receipt = prefill?.receipt;
  if (dismissed || !receipt) return null;

  const understood = pairs(receipt.understood);
  const assumed = pairs(receipt.assumed);
  const missing = receipt.missing || [];
  if (!understood.length && !assumed.length && !missing.length) return null;

  const ask = missing.map((f) => FIELD_QUESTIONS[f] || `Tell me ${label(f)}.`);

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