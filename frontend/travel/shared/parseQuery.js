/**
 * Turns a free-text question into the structured fields the travel forms use.
 *
 * Every one of these is prefill-only. Nothing here searches: the caller fills
 * the form and the user presses the search button themselves. The dashboard
 * hands these queries over via /flights?q=..., /hotels?q=..., /trips?q=...
 *
 * Anything that is not recognised is simply left blank so the user fills the
 * gap — a half-filled form is better than a confidently wrong one.
 */

const ISO = String.raw`\d{4}-\d{2}-\d{2}`;

const stripLead = (s) =>
  s
    .replace(/^\s*(?:please\s+)?(?:find|search|book|show|get|plan|look\s+for|arrange)\s+(?:me\s+)?/i, '')
    .replace(
      /^\s*(?:the\s+)?(?:cheapest|best|cheap(?:est)?|lowest|budget|quick(?:est)?|fastest|direct|non[-\s]?stop|top)\s+/gi,
      ' '
    )
    .replace(/^\s*(?:flights?|tickets?|airfares?|airlines?|hotels?|stays?|resorts?|trips?)\s+(?:from|between|to|in)\s+/i, ' ')
    .replace(/^\s*(?:from|between|to|in)\s+/i, ' ')
    .replace(/^\s*(?:flights?|tickets?|hotels?|stays?|trips?)\s+/i, ' ')
    .trim();

const takeDate = (s, re) => {
  const m = s.match(re);
  if (!m) return [s, null];
  return [s.replace(m[0], ' '), m[1]];
};

/** Drops keys the parser could not fill, so callers can spread the rest safely. */
const clean = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== null && v !== '' && v !== undefined));

/** "Find flights from Delhi to Dubai on 2026-01-05 for 2 passengers" */
export function parseFlightQuery(q) {
  let s = stripLead(String(q || '').trim());
  if (!s) return null;
  const out = {};

  [s, out.returnDate] = takeDate(s, new RegExp(String.raw`\b(?:returning|return\s+on|back\s+on)\s+(${ISO})\b`, 'i'));
  [s, out.departureDate] = takeDate(s, new RegExp(String.raw`\bon\s+(${ISO})\b`, 'i'));

  const pm = s.match(/\bfor\s+(\d+)\s+(?:passengers?|people|adults?|pax|travell?ers?)\b/i);
  if (pm) {
    out.passengers = Math.max(1, parseInt(pm[1], 10));
    s = s.replace(pm[0], ' ');
  }

  const cm = s.match(/\b(?:in|with)\s+([\w-]+)\s+(?:cabin|class)\b/i);
  if (cm) {
    out.cabin = cm[1].toLowerCase().replace(/\s+/g, '_');
    s = s.replace(cm[0], ' ');
  }

  const m = s.match(/^\s*(.+?)\s+to\s+(.+?)\s*$/i);
  if (m) {
    out.origin = m[1].trim();
    out.destination = m[2].trim();
  }
  return Object.keys(clean(out)).length ? clean(out) : null;
}

/** "Hotels in Dubai" */
export function parseHotelQuery(q) {
  let s = stripLead(String(q || '').trim());
  if (!s) return null;
  const out = {};

  [s, out.checkOut] = takeDate(s, new RegExp(String.raw`\bto\s+(${ISO})\b`, 'i'));
  [s, out.checkIn] = takeDate(s, new RegExp(String.raw`\b(?:from|in|on)\s+(${ISO})\b`, 'i'));

  const gm = s.match(/\bfor\s+(\d+)\s+(?:guests?|people|adults?|pax|travell?ers?|nights?)\b/i);
  if (gm) {
    out.guests = Math.max(1, parseInt(gm[1], 10));
    s = s.replace(gm[0], ' ');
  }

  const m = s.match(/\b(?:in|at|near)\s+(.+?)\s*$/i);
  if (m) out.location = m[1].trim();
  else if (s.trim()) out.location = s.trim();

  return Object.keys(clean(out)).length ? clean(out) : null;
}

/** "Plan a 5-day trip from Delhi to Dubai for 2 under 40000" */
export function parseTripQuery(q) {
  let s = String(q || '').trim();
  if (!s) return null;
  const out = {};

  s = s.replace(/^\s*(?:please\s+)?(?:find|search|book|show|get|plan|arrange|make|look\s+for)\s+(?:me\s+)?/i, '');

  // "a 5-day trip from", "5 days trip from", "a trip from", "trip from".
  // Stripped before the X-to-Y split so "a trip" never lands in origin.
  const dur = s.match(
    /^\s*(?:a\s+)?(\d+)[-\s]*(?:days?|nights?)\s*(?:trip|plan|holiday|vacation)?\s*(?:from|between|to)?\s*/i
  );
  if (dur) {
    out.duration_days = Math.max(1, parseInt(dur[1], 10));
    s = s.slice(dur[0].length);
  } else {
    s = s.replace(/^\s*(?:a\s+)?(?:short|long|quick|weekend|holiday|vacation)?\s*trip\s*(?:from|between|to)?\s*/i, ' ');
  }
  s = s.trim();

  [s, out.departure_date] = takeDate(s, new RegExp(String.raw`\bon\s+(${ISO})\b`, 'i'));

  const dm = s.match(/\bfor\s+(\d+)\s+(?:days?|nights?)\b/i);
  if (dm) {
    out.duration_days = Math.max(1, parseInt(dm[1], 10));
    s = s.replace(dm[0], ' ');
  }

  const tm = s.match(/\bfor\s+(\d+)\s+(?:travell?ers?|people|adults?|pax|guests?)\b/i);
  if (tm) {
    out.travelers = Math.max(1, parseInt(tm[1], 10));
    s = s.replace(tm[0], ' ');
  } else if (!out.travelers) {
    // "for 2" with no label — days and budget are already handled, so a
    // remaining bare count is the party size.
    const bare = s.match(/\bfor\s+(\d+)\b/i);
    if (bare) {
      out.travelers = Math.max(1, parseInt(bare[1], 10));
      s = s.replace(bare[0], ' ');
    }
  }

  const bm = s.match(
    /(?:budget|under|below|up\s+to|max|within)\s*(?:of\s*)?(?:rs\.?|inr|₹|\$)?\s*([\d,.]+)\s*(k)?/i
  );
  if (bm) {
    const n = parseFloat(bm[1].replace(/,/g, ''));
    if (Number.isFinite(n)) {
      out.budget_max = bm[2] ? n * 1000 : n;
      s = s.replace(bm[0], ' ');
    }
  }

  const m = s.match(/^\s*(.+?)\s+to\s+(.+?)\s*$/i);
  if (m) {
    out.origin = m[1].trim();
    out.destination = m[2].trim();
  }
  return Object.keys(clean(out)).length ? clean(out) : null;
}
