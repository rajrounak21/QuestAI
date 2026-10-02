/**
 * Verifies the contract Home depends on: every non-auto option has a real path,
 * and the ids match what the backend router returns.
 */
const fs = require("fs");
const path = require("path");

const src = fs.readFileSync(
  path.join(__dirname, "agents.js"),
  "utf8"
);

// crude ESM->CJS so this can run under plain node
const js = src
  .replace(/export const /g, "const ")
  .replace(/export default /g, "module.exports.default = ");
const mod = { exports: {} };
new Function("module", "exports", js + "\nmodule.exports.AGENT_OPTIONS=AGENT_OPTIONS;module.exports.AGENT_BY_ID=AGENT_BY_ID;module.exports.DEFAULT_AGENT_ID=DEFAULT_AGENT_ID;")(mod, mod.exports);
const { AGENT_OPTIONS, AGENT_BY_ID, DEFAULT_AGENT_ID } = mod.exports;

const BACKEND_AGENTS = ["research", "shopping", "jobs", "flights", "hotels", "trips", "assistant"];

let fails = 0;
const check = (name, cond) => {
  if (!cond) fails++;
  console.log(`  ${cond ? "PASS" : "FAIL"}  ${name}`);
};

console.log("=== option integrity ===");
check("default agent id exists", !!AGENT_BY_ID[DEFAULT_AGENT_ID]);
check("auto has no path (router decides)", AGENT_BY_ID[DEFAULT_AGENT_ID].path === null);
check("ids are unique", new Set(AGENT_OPTIONS.map((o) => o.id)).size === AGENT_OPTIONS.length);
check("every option has label + hint", AGENT_OPTIONS.every((o) => o.label && o.hint));
check("every non-auto option has a path", AGENT_OPTIONS.every((o) => o.id === "auto" || o.path));
check("paths start with /", AGENT_OPTIONS.every((o) => !o.path || o.path.startsWith("/")));

console.log();
console.log("=== covers every backend agent (except assistant) ===");
for (const a of BACKEND_AGENTS) {
  if (a === "assistant") continue;
  check(`${a} selectable`, !!AGENT_BY_ID[a]);
}

console.log();
console.log("=== paths match the backend router ===");
const BACKEND_PATHS = {
  research: "/research",
  shopping: "/shopping",
  jobs: "/jobs",
  flights: "/flights",
  hotels: "/hotels",
  trips: "/trips",
};
for (const [id, want] of Object.entries(BACKEND_PATHS)) {
  check(`${id} -> ${want}`, AGENT_BY_ID[id].path === want);
}

console.log();
console.log("=== no stray 'Travel' agent id (it was a 3-way guess) ===");
check("no 'travel' id", !AGENT_BY_ID.travel);
check("no 'Travel' label", !AGENT_OPTIONS.some((o) => o.label === "Travel"));

console.log();
console.log(fails === 0 ? "ALL CHECKS PASSED" : `${fails} CHECK(S) FAILED`);
process.exit(fails ? 1 : 0);
