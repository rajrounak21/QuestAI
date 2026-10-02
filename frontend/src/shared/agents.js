// Each specialist is one destination. "Auto" means "let the router choose".
// Keeping a single list means the dropdown, the routing in submit() and the
// suggestion cards can never drift apart.
export const AGENT_OPTIONS = [
  { id: "auto", label: "Auto", hint: "pick for me", path: null },
  { id: "research", label: "Research", hint: "sources and evidence", path: "/research" },
  { id: "shopping", label: "Shopping", hint: "products and prices", path: "/shopping" },
  { id: "jobs", label: "Jobs", hint: "roles and alerts", path: "/jobs" },
  { id: "flights", label: "Flights", hint: "fare search", path: "/flights" },
  { id: "hotels", label: "Hotels", hint: "stays and rooms", path: "/hotels" },
  { id: "trips", label: "Trips", hint: "full itinerary", path: "/trips" },
];

export const AGENT_BY_ID = Object.fromEntries(
  AGENT_OPTIONS.map((o) => [o.id, o])
);

export const DEFAULT_AGENT_ID = "auto";
