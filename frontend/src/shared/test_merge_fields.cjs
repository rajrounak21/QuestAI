/**
 * Guards the universal router's field hand-off.
 *
 * The bug this exists for: the travel forms used to merge router fields and
 * text-parser fields with `routerFields || parseQuery(q) || {}`. That is
 * per-OBJECT, so the moment the router returned anything at all the parser was
 * skipped entirely - and "flights Delhi to Dubai on 2026-01-05" reached the form
 * with origin and destination set and the date blank, even though the date was
 * in the same sentence. mergeFields() merges per FIELD and normalises the key
 * names, so both halves of that sentence survive.
 */
const fs = require("fs");
const path = require("path");

const src = fs.readFileSync(path.join(__dirname, "mergeFields.js"), "utf8");
const js = src.replace(/export function /g, "function ").concat("\nmodule.exports.mergeFields=mergeFields;");
const mod = { exports: {} };
new Function("module", "exports", js)(mod, mod.exports);
const { mergeFields } = mod.exports;

const parseFlightQuery = (q) => {
  // Mirrors travel/shared/parseQuery.js: camelCase keys, dates pulled out.
  const iso = String.raw`\d{4}-\d{2}-\d{2}`;
  const out = {};
  let s = q;
  const rm = s.match(new RegExp(String.raw`\breturning\s+(${iso})\b`, "i"));
  if (rm) { out.returnDate = rm[1]; s = s.replace(rm[0], " "); }
  const dm = s.match(new RegExp(String.raw`\bon\s+(${iso})\b`, "i"));
  if (dm) { out.departureDate = dm[1]; s = s.replace(dm[0], " "); }
  const m = s.match(/^\s*(.+?)\s+to\s+(.+?)\s*$/i);
  if (m) { out.origin = m[1].trim(); out.destination = m[2].trim(); }
  return Object.keys(out).length ? out : null;
};

let fails = 0;
const check = (name, cond) => {
  if (!cond) fails++;
  console.log(`  ${cond ? "PASS" : "FAIL"}  ${name}`);
};

console.log("=== the regression: router dropped the date ===");
// What the backend returns when it gets origin+destination but not the date.
const routerPartial = { origin: "Delhi", destination: "Dubai" };
const parsed = parseFlightQuery("flights Delhi to Dubai on 2026-01-05");

check("parser produced the date", parsed && parsed.departureDate === "2026-01-05");

const merged = mergeFields(routerPartial, parsed);
check("date survives the merge", merged.departure_date === "2026-01-05");
check("camelCase key is normalised", merged.departureDate === undefined);
check("origin kept", merged.origin === "Delhi");
check("destination kept", merged.destination === "Dubai");

console.log("\n=== old behaviour would have dropped it ===");
const oldWay = routerPartial || parseFlightQuery("flights Delhi to Dubai on 2026-01-05") || {};
check("per-object merge loses the date (this is the bug)", oldWay.departure_date === undefined);

console.log("\n=== router wins per field ===");
const both = mergeFields(
  { origin: "Mumbai", destination: "Dubai" },
  { origin: "Delhi", destination: "Dubai", departureDate: "2026-02-01" }
);
check("router overrides its field", both.origin === "Mumbai");
check("parser still fills the router's gap", both.departure_date === "2026-02-01");

console.log("\n=== blanks are dropped, not merged as empty ===");
const blanks = mergeFields({ origin: "Delhi", destination: "" }, { returnDate: "" });
check("empty string dropped", blanks.destination === undefined);
check("real value kept", blanks.origin === "Delhi");

console.log("\n=== jobs aliases: role -> roles, mode -> work_mode ===");
const jobs = mergeFields(
  { roles: ["Python Developer"], locations: ["India"], work_mode: "remote" },
  { role: "Backend Engineer", locations: [], mode: "hybrid" }
);
check("router roles wins", JSON.stringify(jobs.roles) === '["Python Developer"]');
check("parser role does not leak under its own key", jobs.role === undefined);
check("work_mode normalised", jobs.work_mode === "remote");
check("empty parser array does not clobber router", JSON.stringify(jobs.locations) === '["India"]');

console.log("\n=== empty inputs ===");
check("both null", JSON.stringify(mergeFields(null, null)) === "{}");
check("only router", mergeFields({ origin: "Delhi" }, null).origin === "Delhi");
check("only parser", mergeFields(null, { origin: "Delhi" }).origin === "Delhi");

console.log(fails === 0 ? "\nALL CHECKS PASSED" : `\n${fails} CHECK(S) FAILED`);
process.exit(fails === 0 ? 0 : 1);