/**
 * Guards the trip budget currency decision.
 *
 * The bug: buildQuery() appended the literal word "dollars", so a rupee budget
 * reached the graph as a dollar budget and filtered against dollar prices - 83x
 * too generous. A bare "under 40000" carries no currency, so it is never guessed:
 * the ladder is explicit symbol, then the dropdown, then the origin city, then a
 * default the UI shows.
 */
const fs = require("fs");
const path = require("path");

const src = fs.readFileSync(path.join(__dirname, "..", "..", "travel", "shared", "parseQuery.js"), "utf8");
const js = src.replace(/export function /g, "function ").concat("\nmodule.exports.parseTripQuery=parseTripQuery;");
const mod = { exports: {} };
new Function("module", "exports", js)(mod, mod.exports);
const { parseTripQuery } = mod.exports;

let fails = 0;
const check = (name, cond) => {
  if (!cond) fails++;
  console.log(`  ${cond ? "PASS" : "FAIL"}  ${name}`);
};

console.log("=== an explicit symbol is captured, not discarded ===");
const rupee = parseTripQuery("trip from Delhi to Dubai under \u20b940000");
check("rupee symbol recognised", rupee.budget_currency === "INR");
check("amount still parsed", rupee.budget_max === 40000);
check("origin not polluted by the symbol", rupee.origin === "Delhi");

const usd = parseTripQuery("trip from London to Tokyo under $3000");
check("dollar symbol recognised", usd.budget_currency === "USD");
check("amount still parsed", usd.budget_max === 3000);

const spelled = parseTripQuery("trip from Delhi to Dubai under Rs 40000");
check("Rs recognised", spelled.budget_currency === "INR");

const suffixed = parseTripQuery("trip from Delhi to Dubai under 40000 INR");
check("trailing ISO code recognised", suffixed.budget_currency === "INR");

console.log("\n=== a bare number carries no currency ===");
const bare = parseTripQuery("trip from Delhi to Dubai under 40000");
check("no symbol means no budget_currency", bare.budget_currency === undefined);
check("amount still parsed", bare.budget_max === 40000);
check("origin clean", bare.origin === "Delhi");
check("destination clean", bare.destination === "Dubai");

console.log("\n=== k suffix ===");
const k = parseTripQuery("trip from Delhi to Dubai under 40k");
check("40k means 40000", k.budget_max === 40000);

console.log(fails === 0 ? "\nALL CHECKS PASSED" : `\n${fails} CHECK(S) FAILED`);
process.exit(fails === 0 ? 0 : 1);