// Graph maps below mirror the real backends 1:1 — every box is a real node,
// every arrow a real edge, ↻ curves are the real re-run loops.
// Research: backend/agents/research/graph/graph.py + services (topic_check,
// complexity) + api/router.py routes. Shopping:
// backend/agents/shopping/graph/graph.py. Jobs:
// backend/agents/job/graph/graph.py (add_node / add_conditional_edges at
// graph.py:643-668).

const INK = "#f2f5fa";
const MUTED = "#9aa3b5";
const EDGE = "#4b5568";
const NODE_BG = "#151b24";
const LABEL_BG = "#0b0e14";
const CYAN = "#56e1d5";

function tagColor(tag, accent) {
  if (tag === "LLM") return accent;
  if (tag === "API" || tag === "2× API") return CYAN;
  if (tag === "MongoDB") return "#56d9a0";
  return MUTED; // rule, logic
}

export const FLOWS = {
  research: {
    id: "research",
    title: "Research",
    subtitle: "Deep research LangGraph — boxes are real nodes, arrows are real edges",
    accent: "#5b7cff",
    stats: ["9 graph nodes", "2 re-run loops", "~8–12 LLM calls"],
    w: 640,
    h: 1520,
    nodes: {
      start: { x: 230, y: 20, w: 180, h: 40, kind: "pill", title: "User query" },
      session: { x: 220, y: 100, w: 200, h: 100, title: "Session check", tag: "LLM", lines: ["Topic continuity: same →", "continue, else fresh / ask"] },
      complex: { x: 220, y: 240, w: 200, h: 100, title: "Complexity classifier", tag: "LLM", lines: ["Cheapest sufficient route:", "direct · evidence · full"] },
      route: { x: 220, y: 380, w: 200, h: 110, kind: "diamond", title: "Route?" },
      direct: { x: 20, y: 530, w: 170, h: 100, title: "Direct answer", tag: "LLM", lines: ["1 fast answer ·", "no search, no graph"] },
      planner: { x: 225, y: 530, w: 190, h: 100, title: "Planner", tag: "LLM", lines: ["4–8 queries: Google,", "Scholar, News"] },
      evidence: { x: 450, y: 530, w: 170, h: 100, title: "Evidence route", tag: "LLM", lines: ["Synth + validate on", "cached evidence"] },
      router: { x: 225, y: 670, w: 190, h: 64, title: "Router", tag: "logic", lines: ["pass-through"] },
      collector: { x: 225, y: 774, w: 190, h: 100, title: "Collector", tag: "API", lines: ["5 parallel workers ·", "raw results"] },
      evaluator: { x: 225, y: 914, w: 190, h: 64, title: "Evaluator", tag: "logic", lines: ["extract evidence"] },
      gap: { x: 225, y: 1018, w: 190, h: 100, title: "Gap analyzer", tag: "LLM", lines: ["covered / weak /", "missing?"] },
      synth: { x: 225, y: 1158, w: 190, h: 100, title: "Synthesizer", tag: "LLM", lines: ["summary · findings ·", "comparison · sources"] },
      validator: { x: 225, y: 1298, w: 190, h: 100, title: "Validator", tag: "LLM", lines: ["each claim vs", "cited evidence"] },
      save: { x: 170, y: 1438, w: 300, h: 44, kind: "pill", dashed: true, title: "Format + save session", tag: "MongoDB" },
    },
    edges: [
      { from: "start", to: "session" },
      { from: "session", to: "complex" },
      { from: "complex", to: "route" },
      { from: "route", fromSide: "left", to: "direct", label: "direct", lx: 232, ly: 462 },
      { from: "route", to: "planner", label: "full", lx: 328, ly: 508 },
      { from: "route", fromSide: "right", to: "evidence", label: "evidence", lx: 432, ly: 474 },
      { from: "planner", to: "router" },
      { from: "router", to: "collector" },
      { from: "collector", to: "evaluator" },
      { from: "evaluator", to: "gap" },
      { from: "gap", to: "synth" },
      { from: "synth", to: "validator" },
      { from: "validator", to: "save" },
      { from: "gap", fromSide: "right", to: "collector", toSide: "right", loop: "right", dashed: true, color: CYAN, label: ["gaps remain", "≤ max rounds"], lx: 632, anchor: "end", ly: 944 },
      { from: "validator", fromSide: "left", to: "synth", toSide: "left", loop: "left", dashed: true, color: CYAN, label: ["issues found", "1 retry max"], lx: 105, anchor: "middle", ly: 1274 },
      { from: "direct", to: "save", toSide: "left", via: [[60, 630], [60, 1460]] },
      { from: "evidence", to: "save", toSide: "right", via: [[535, 1460]] },
    ],
  },
  shopping: {
    id: "shopping",
    title: "Shopping",
    subtitle: "Product comparison graph — fast, deterministic, zero LLM calls",
    accent: "#f3c96a",
    stats: ["3 graph nodes", "0 LLM calls", "2 live APIs"],
    w: 640,
    h: 700,
    nodes: {
      start: { x: 230, y: 20, w: 180, h: 40, kind: "pill", title: "Query + country" },
      extract: { x: 220, y: 100, w: 200, h: 100, title: "Extract params", tag: "rule", lines: ["deterministic ·", "0 LLM calls"] },
      validate: { x: 220, y: 240, w: 200, h: 64, title: "Validate", tag: "rule", lines: ["empty / too short?"] },
      valid: { x: 220, y: 344, w: 200, h: 100, kind: "diamond", title: "Valid?" },
      followup: { x: 30, y: 484, w: 170, h: 100, dashed: true, title: "Ask follow-up", lines: ["too short →", "stop here"] },
      search: { x: 220, y: 484, w: 200, h: 100, title: "Search", tag: "2× API", lines: ["Google + Amazon parallel", "normalize → dedupe"] },
      save: { x: 170, y: 624, w: 300, h: 44, kind: "pill", dashed: true, title: "Save session + search", tag: "MongoDB" },
    },
    edges: [
      { from: "start", to: "extract" },
      { from: "extract", to: "validate" },
      { from: "validate", to: "valid" },
      { from: "valid", fromSide: "left", to: "followup", label: "no", lx: 167, ly: 440 },
      { from: "valid", to: "search", label: "yes", lx: 328, ly: 470 },
      { from: "search", to: "save" },
    ],
  },
  jobs: {
    id: "jobs",
    title: "Jobs",
    subtitle: "Resume-matched job search — boxes are real nodes, arrows are real edges",
    accent: "#56d9a0",
    stats: ["8 graph nodes", "1 conditional branch"],
    w: 640,
    // Must clear the last node: save sits at y 1160 with h 40, so the bottom
    // edge is 1200. Anything under that clips the pill in the viewBox itself,
    // which reads as "the bottom of the graph is hidden".
    h: 1220,
    nodes: {
      start: { x: 210, y: 20, w: 220, h: 40, kind: "pill", title: "Query + resume bytes?" },
      // route_after_input always returns resume_vision_parser unless the graph
      // already errored or has a follow_up_question, which exits to END.
      // This is the first of the two nodes that can ask the user something
      // (graph.py:86 asks for a role when neither query nor resume is usable).
      errIn: { x: 20, y: 100, w: 170, h: 100, kind: "diamond", dashed: true, title: "Error / follow-up?" },
      parse: { x: 210, y: 180, w: 220, h: 110, title: "Resume parser", tag: "LLM", lines: ["bytes → parse · none →", "load stored profile"] },
      query: { x: 210, y: 330, w: 220, h: 100, title: "Query analyzer", tag: "rule", lines: ["role · location ·", "work mode (typo → LLM)"] },
      build: { x: 210, y: 470, w: 220, h: 100, title: "Profile builder", tag: "rule", lines: ["merge resume + query", "into one profile"] },
      valid: { x: 210, y: 610, w: 220, h: 100, kind: "diamond", title: "Profile ok?" },
      ask: { x: 20, y: 750, w: 170, h: 100, dashed: true, title: "Ask follow-up", lines: ["no role? no place?", "ends the run"] },
      plan: { x: 210, y: 750, w: 220, h: 100, title: "Search planner", tag: "rule", lines: ["roles × locations =", "≤ 4 requests, 0 LLM"] },
      search: { x: 210, y: 890, w: 220, h: 100, title: "Google Jobs", tag: "API", lines: ["SerpApi ·", "normalise + dedupe"] },
      match: { x: 210, y: 1030, w: 220, h: 100, title: "Match + rank", tag: "rule", lines: ["skill overlap →", "freshest, 0% honest"] },
      save: { x: 160, y: 1160, w: 320, h: 40, kind: "pill", dashed: true, title: "Session + search saved", tag: "MongoDB" },
    },
    edges: [
      { from: "start", to: "errIn" },
      { from: "errIn", fromSide: "left", to: "save", label: "stop", lx: 100, ly: 700 },
      { from: "errIn", to: "parse" },
      { from: "parse", to: "query" },
      { from: "query", to: "build" },
      { from: "build", to: "valid" },
      { from: "valid", fromSide: "left", to: "ask", label: "no", lx: 145, ly: 720 },
      { from: "valid", to: "plan", label: "yes", lx: 328, ly: 726 },
      { from: "plan", to: "search" },
      { from: "search", to: "match" },
      { from: "match", to: "save" },
    ],
  },
  travel: {
    id: "travel",
    title: "Travel",
    subtitle: "Flights, hotels + trip planner — three graphs verified against backend/agents/travel",
    accent: "#56e1d5",
    stats: ["3 graphs", "14 graph nodes", "5 LLM calls"],
    sections: [
      {
        sectionTitle: "Flight search",
        w: 640,
        h: 700,
        nodes: {
          start: { x: 230, y: 20, w: 180, h: 40, kind: "pill", title: "Delhi → Dubai + date" },
          extract: { x: 220, y: 100, w: 200, h: 100, title: "Extract params", tag: "LLM", lines: ["origin · destination ·", "dates · cabin · pax"] },
          validate: { x: 220, y: 240, w: 200, h: 64, title: "Validate", tag: "rule", lines: ["origin + destination + date?"] },
          valid: { x: 220, y: 344, w: 200, h: 100, kind: "diamond", title: "Valid?" },
          followup: { x: 30, y: 484, w: 170, h: 100, dashed: true, title: "Ask follow-up", lines: ["origin? destination?", "date?"] },
          search: { x: 220, y: 484, w: 200, h: 100, title: "Search flights", tag: "API", lines: ["Google Flights ·", "normalize"] },
          save: { x: 170, y: 624, w: 300, h: 44, kind: "pill", dashed: true, title: "Save session", tag: "MongoDB" },
        },
        edges: [
          { from: "start", to: "extract" },
          { from: "extract", to: "validate" },
          { from: "validate", to: "valid" },
          { from: "valid", fromSide: "left", to: "followup", label: "no", lx: 167, ly: 440 },
          { from: "valid", to: "search", label: "yes", lx: 328, ly: 470 },
          { from: "search", to: "save" },
        ],
      },
      {
        sectionTitle: "Hotel search",
        w: 640,
        h: 700,
        nodes: {
          start: { x: 230, y: 20, w: 180, h: 40, kind: "pill", title: "City + check-in/out" },
          extract: { x: 220, y: 100, w: 200, h: 100, title: "Extract params", tag: "LLM", lines: ["location · check-in/out ·", "guests · rooms"] },
          validate: { x: 220, y: 240, w: 200, h: 64, title: "Validate", tag: "rule", lines: ["location + dates?"] },
          valid: { x: 220, y: 344, w: 200, h: 100, kind: "diamond", title: "Valid?" },
          followup: { x: 30, y: 484, w: 170, h: 100, dashed: true, title: "Ask follow-up", lines: ["location?", "check-in/out dates?"] },
          search: { x: 220, y: 484, w: 200, h: 100, title: "Search hotels", tag: "API", lines: ["Google Hotels ·", "budget filter"] },
          save: { x: 170, y: 624, w: 300, h: 44, kind: "pill", dashed: true, title: "Save session", tag: "MongoDB" },
        },
        edges: [
          { from: "start", to: "extract" },
          { from: "extract", to: "validate" },
          { from: "validate", to: "valid" },
          { from: "valid", fromSide: "left", to: "followup", label: "no", lx: 167, ly: 440 },
          { from: "valid", to: "search", label: "yes", lx: 328, ly: 470 },
          { from: "search", to: "save" },
        ],
      },
      {
        sectionTitle: "Trip planner",
        w: 640,
        h: 1790,
        nodes: {
          start: { x: 230, y: 20, w: 180, h: 40, kind: "pill", title: "New / follow-up msg" },
          extract: { x: 220, y: 100, w: 200, h: 100, title: "Extract params", tag: "LLM", lines: ["params + intent:", "new_trip / follow-up"] },
          pok: { x: 220, y: 240, w: 200, h: 100, kind: "diamond", title: "Params ok?" },
          validate: { x: 220, y: 380, w: 200, h: 100, title: "Validate", tag: "LLM", lines: ["clarifying questions", "if details missing"] },
          qd: { x: 220, y: 520, w: 200, h: 100, kind: "diamond", title: "Questions?" },
          merge: { x: 225, y: 660, w: 190, h: 64, title: "Merge answers", tag: "logic", lines: ["attach user answers"] },
          impact: { x: 225, y: 764, w: 190, h: 100, title: "Detect impact", tag: "LLM", lines: ["which agents affected?", "flights/hotels/research"] },
          load: { x: 225, y: 904, w: 190, h: 64, title: "Load session", tag: "DB", lines: ["create / resume trip"] },
          update: { x: 220, y: 1008, w: 200, h: 100, title: "Update state", tag: "logic", lines: ["apply changes ·", "recompute hashes"] },
          need: { x: 220, y: 1148, w: 200, h: 100, kind: "diamond", title: "Agents needed?" },
          dispatch: { x: 225, y: 1288, w: 190, h: 100, title: "Dispatch agents", tag: "logic", lines: ["runs affected sub-graphs", "see 3 calls below"] },
          dFlights: { x: 30, y: 1428, w: 150, h: 100, title: "Flights search", tag: "API", lines: ["full flight graph ·", "skip if hash same"] },
          dHotels: { x: 190, y: 1428, w: 150, h: 100, title: "Hotels search", tag: "API", lines: ["full hotel graph ·", "skip if hash same"] },
          dResearch: { x: 350, y: 1428, w: 150, h: 100, title: "Dest research", tag: "LLM", lines: ["places + itinerary", "skip if hash same"] },
          synth: { x: 225, y: 1568, w: 190, h: 100, title: "Synthesize", tag: "logic", lines: ["itinerary + budget ·", "cheapest / best picks"] },
          save: { x: 170, y: 1708, w: 300, h: 44, kind: "pill", dashed: true, title: "Save trip", tag: "MongoDB" },
        },
        edges: [
          { from: "start", to: "extract" },
          { from: "extract", to: "pok" },
          { from: "pok", to: "validate", label: "valid", lx: 328, ly: 364 },
          { from: "pok", fromSide: "left", to: "synth", toSide: "left", via: [[80, 290], [80, 1618]], label: "error", lx: 86, ly: 880 },
          { from: "validate", to: "qd" },
          { from: "qd", to: "merge", label: "continue", lx: 328, ly: 644 },
          { from: "qd", fromSide: "right", to: "synth", toSide: "right", toY: 1610, via: [[520, 570], [520, 1610]], label: "ask user", lx: 519, anchor: "end", ly: 860 },
          { from: "merge", to: "impact" },
          { from: "impact", to: "load" },
          { from: "load", to: "update" },
          { from: "update", to: "need" },
          { from: "need", to: "dispatch", label: "run agents", lx: 328, ly: 1272 },
          { from: "need", fromSide: "right", to: "synth", toSide: "right", toY: 1590, via: [[575, 1198], [575, 1590]], label: "none", lx: 581, ly: 1330 },
          { from: "dispatch", to: "dFlights", via: [[320, 1408], [105, 1408]] },
          { from: "dispatch", to: "dHotels" },
          { from: "dispatch", to: "dResearch", via: [[320, 1408], [425, 1408]] },
          { from: "dFlights", to: "synth", toSide: "top", via: [[105, 1548], [270, 1548]] },
          { from: "dHotels", to: "synth" },
          { from: "dResearch", to: "synth", toSide: "top", via: [[425, 1548], [370, 1548]] },
          { from: "synth", to: "save" },
        ],
      },
    ],
  },
};

function pt(n, side) {
  if (side === "top") return { x: n.x + n.w / 2, y: n.y };
  if (side === "left") return { x: n.x, y: n.y + n.h / 2 };
  if (side === "right") return { x: n.x + n.w, y: n.y + n.h / 2 };
  return { x: n.x + n.w / 2, y: n.y + n.h }; // bottom
}

function edgePath(e, N) {
  const p1 = pt(N[e.from], e.fromSide || "bottom");
  const a2 = pt(N[e.to], e.toSide || "top");
  const p2 = e.toY !== undefined ? { x: a2.x, y: e.toY } : a2;
  if (e.loop) {
    const dx = e.loop === "right" ? 90 : -90;
    return `M ${p1.x} ${p1.y} C ${p1.x + dx} ${p1.y} ${p2.x + dx} ${p2.y} ${p2.x} ${p2.y}`;
  }
  if (e.via) {
    return `M ${p1.x} ${p1.y} ` + e.via.map((p) => `L ${p[0]} ${p[1]}`).join(" ") + ` L ${p2.x} ${p2.y}`;
  }
  if (p1.x === p2.x) return `M ${p1.x} ${p1.y} L ${p2.x} ${p2.y}`;
  const m = (p1.y + p2.y) / 2;
  return `M ${p1.x} ${p1.y} L ${p1.x} ${m} L ${p2.x} ${m} L ${p2.x} ${p2.y}`;
}

function Chip({ cx, y, text, color }) {
  const w = text.length * 7 + 20;
  return (
    <g>
      <rect x={cx - w / 2} y={y} width={w} height={18} rx={9} fill={color} fillOpacity={0.12} stroke={color} strokeOpacity={0.5} />
      <text x={cx} y={y + 13} textAnchor="middle" fontSize={9} fontWeight={800} letterSpacing={1} fill={color}>
        {text.toUpperCase()}
      </text>
    </g>
  );
}

function NodeShape({ n, accent }) {
  const cx = n.x + n.w / 2;
  if (n.kind === "pill") {
    const titleW = n.title.length * 7;
    let tx = cx;
    let chip = null;
    if (n.tag) {
      const c = tagColor(n.tag, accent);
      const chipW = n.tag.length * 7 + 20;
      const total = titleW + 10 + chipW;
      tx = cx - total / 2;
      chip = (
        <g>
          <rect x={tx + titleW + 10} y={n.y + n.h / 2 - 9} width={chipW} height={18} rx={9} fill={c} fillOpacity={0.12} stroke={c} strokeOpacity={0.5} />
          <text x={tx + titleW + 10 + chipW / 2} y={n.y + n.h / 2 + 4.5} textAnchor="middle" fontSize={9} fontWeight={800} letterSpacing={1} fill={c}>
            {n.tag.toUpperCase()}
          </text>
        </g>
      );
    }
    return (
      <g>
        <rect x={n.x} y={n.y} width={n.w} height={n.h} rx={n.h / 2} fill={NODE_BG}
          stroke={n.dashed ? MUTED : accent} strokeOpacity={n.dashed ? 0.6 : 0.7}
          strokeWidth={1.5} strokeDasharray={n.dashed ? "6 5" : undefined} />
        <text x={tx} y={n.y + n.h / 2 + 4.5} textAnchor={n.tag ? "start" : "middle"} fontSize={13} fontWeight={700} fill={INK}>{n.title}</text>
        {chip}
      </g>
    );
  }
  if (n.kind === "diamond") {
    const { x, y, w, h } = n;
    const cy = y + h / 2;
    return (
      <g>
        <polygon points={`${cx},${y} ${x + w},${cy} ${cx},${y + h} ${x},${cy}`} fill={NODE_BG} stroke={accent} strokeWidth={1.5} />
        <text x={cx} y={cy + 5} textAnchor="middle" fontSize={14} fontWeight={800} fill={INK}>{n.title}</text>
      </g>
    );
  }
  const c = n.tag ? tagColor(n.tag, accent) : MUTED;
  const lines = n.lines || [];
  return (
    <g>
      <rect x={n.x} y={n.y} width={n.w} height={n.h} rx={12} fill={NODE_BG} stroke={c} strokeOpacity={0.45} strokeWidth={1.5} />
      {n.tag && <Chip cx={cx} y={n.y + 10} text={n.tag} color={c} />}
      <text x={cx} y={n.y + (lines.length ? 44 : n.h / 2 + 5)} textAnchor="middle" fontSize={13} fontWeight={700} fill={INK}>
        {n.title}
      </text>
      {lines.map((l, i) => (
        <text key={i} x={cx} y={n.y + 62 + i * 15} textAnchor="middle" fontSize={10.5} fill={MUTED}>{l}</text>
      ))}
    </g>
  );
}

function EdgeShape({ e, N }) {
  const d = edgePath(e, N);
  const color = e.color || EDGE;
  const marker = e.color ? "url(#aflow-arr-c)" : "url(#aflow-arr)";
  const labels = e.label ? (Array.isArray(e.label) ? e.label : [e.label]) : [];
  return (
    <g>
      <path d={d} fill="none" stroke={color} strokeWidth={1.8}
        strokeDasharray={e.dashed ? "5 4" : undefined} markerEnd={marker} />
      {labels.map((l, i) => (
        <text key={i} x={e.lx} y={(e.ly || 0) + i * 15} textAnchor={e.anchor || "start"}
          fontSize={10.5} fontWeight={700} fill={MUTED}
          stroke={LABEL_BG} strokeWidth={4} paintOrder="stroke">{l}</text>
      ))}
    </g>
  );
}

export function FlowSvg({ flow, widthPx }) {
  const style = widthPx
    ? { width: widthPx, height: "auto", display: "block" }
    : { width: "100%", minWidth: 520, height: "auto", display: "block" };
  return (
    <svg viewBox={`0 0 ${flow.w} ${flow.h}`} style={style} role="img" aria-label={`${flow.title} LangGraph diagram`}>
      <defs>
        <marker id="aflow-arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 1 L 9 5 L 0 9" fill="none" stroke={EDGE} strokeWidth={1.8} />
        </marker>
        <marker id="aflow-arr-c" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 1 L 9 5 L 0 9" fill="none" stroke={CYAN} strokeWidth={1.8} />
        </marker>
      </defs>
      {flow.edges.map((e, i) => <EdgeShape key={i} e={e} N={flow.nodes} />)}
      {Object.entries(flow.nodes).map(([id, n]) => <NodeShape key={id} n={n} accent={flow.accent} />)}
    </svg>
  );
}
