/**
 * What each field means, in one place, so the receipt and the asker cannot
 * describe the same field differently.
 *
 * `order` controls how a receipt reads - the order the user actually said it in,
 * not alphabetical.
 */

export const FIELD_LABELS = {
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

export const FIELD_ORDER = [
  "roles", "locations", "work_mode",
  "origin", "destination", "departure_date", "return_date",
  "location", "check_in", "check_out",
  "duration_days", "travelers", "budget_max",
  "guests", "passengers", "cabin",
  "query",
];

export const fieldLabel = (k) => FIELD_LABELS[k] || String(k).replace(/_/g, " ");

/**
 * How to ask for a missing field. `inputType: "date"` because a typed date is
 * the one field where guessing is worse than asking - the router will not resolve
 * "next friday", and an invented date runs a search nobody asked for.
 */
export const FIELD_ASKS = {
  origin: { question: "Where are you flying from?" },
  destination: { question: "Where are you flying to?" },
  departure_date: {
    question: "What date do you want to travel?",
    why: "Flights need an exact date.",
    inputType: "date",
  },
  return_date: {
    question: "Coming back when?",
    inputType: "date",
  },
  check_in: {
    question: "What date do you check in?",
    why: "Hotels are priced per night, so this sets the search.",
    inputType: "date",
  },
  check_out: {
    question: "What date do you check out?",
    inputType: "date",
  },
  location: { question: "Which city or area?" },
  roles: { question: "What role are you looking for?" },
  locations: { question: "Any preferred locations?", options: ["India", "Remote"] },
  budget_max: {
    question: "What budget?",
    why: "The planner filters options by it.",
    placeholder: "e.g. 2500 or 'mid-range'",
  },
};

export const askFor = (field) =>
  FIELD_ASKS[field] || { question: `Tell me ${fieldLabel(field)}.` };

/** Builds the Clarifying question list for a set of missing field names. */
export function asksFor(missing = []) {
  return missing.slice(0, 4).map((field) => ({ field, ...askFor(field) }));
}