/**
 * Merges the universal router's extracted fields with the frontend text parser.
 *
 * Two things this has to get right, both of which used to go wrong:
 *
 * 1. MERGE PER FIELD, NOT PER OBJECT. The router usually gets most of a query but
 *    not all of it - "flights Delhi to Dubai on 2026-01-05" reliably yields the
 *    two cities and drops the date. Picking one whole source and discarding the
 *    other threw away a field that was sitting in the same sentence.
 *
 * 2. AGREE ON KEY NAMES. The router emits snake_case; the text parsers emit a
 *    mix (parseFlightQuery returns departureDate, parseTripQuery returns
 *    departure_date). Everything is normalised to snake_case here, because that
 *    is what the forms read.
 *
 * The router wins per field, but only where it actually has a value.
 */

/** departureDate -> departure_date, returnDate -> return_date, and so on. */
const toSnake = (key) => key.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase();

/** Source keys that mean something different from their normalised name. */
const ALIASES = {
  // jobs/parseQuery.js returns role (singular string) and mode; the router
  // returns roles (array) and work_mode.
  role: 'roles',
  mode: 'work_mode',
};

const isEmpty = (v) =>
  v === null ||
  v === undefined ||
  v === '' ||
  (Array.isArray(v) && v.length === 0);

/**
 * @param {object} routerFields  from /api/agent/route - wins where populated
 * @param {object|null} parsedFields  from parseFlightQuery / parseHotelQuery / ...
 * @returns {object} snake_case fields with no blank values
 */
export function mergeFields(routerFields, parsedFields) {
  const out = {};

  const collect = (source) => {
    for (const [rawKey, value] of Object.entries(source || {})) {
      const snake = toSnake(rawKey);
      const key = ALIASES[rawKey] || ALIASES[snake] || snake;
      if (isEmpty(value)) continue;
      out[key] = value;
    }
  };

  collect(parsedFields);
  collect(routerFields);
  return out;
}