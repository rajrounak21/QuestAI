import { useState } from "react";
import { useReducedMotion } from "framer-motion";
import { useTilt } from "../hooks.js";
import { AGENTS } from "../data.jsx";
import { AGENT_ICONS } from "../assets/agentIcons.js";

/**
 * Living architecture visual:
 *   YOUR REQUEST → AI CORE → Research / Travel / Shopping / Jobs
 * 3D tilt wrapper + animated SVG flows + selectable agent nodes.
 */
export default function Architecture3D({ onSelect }) {
  const reduce = useReducedMotion();
  const { ref, onMove, onLeave, style } = useTilt(7);
  const [selected, setSelected] = useState("jobs");

  const active = AGENTS.find((a) => a.id === selected);

  function pick(id) {
    setSelected(id);
    onSelect?.(id);
  }

  // Short labels per agent for the SVG request box (fits 200px width)
  const REQUEST_LABELS = {
    research: "Research RAG tools",
    travel: "Delhi to Dubai under $50",
    shopping: "Compare Samsung phones",
    jobs: "Find AI internships...",
  };

  // Node layout in a 760x380 viewBox
  const nodes = [
    { id: "research", x: 40, label: "Research" },
    { id: "travel", x: 220, label: "Travel" },
    { id: "shopping", x: 400, label: "Shopping" },
    { id: "jobs", x: 580, label: "Jobs" },
  ];

  return (
    <div className="stage-3d">
      <div
        ref={ref} className="tilt arch-card" style={reduce ? undefined : style}
        onMouseMove={onMove} onMouseLeave={onLeave}
      >
        <div className="arch-inner">
          <div className="arch-top">
            <span className="eyebrow">Live routing visual</span>
            <span className="live-dot"><i />AI Core · online</span>
          </div>

          <svg className="arch-svg" viewBox="0 0 760 400" role="img"
            aria-label="Diagram: your request flows into the AI core, which routes to Research, Travel, Shopping or Jobs agents">
            <defs>
              <linearGradient id="qgrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0" stopColor="#5b7cff" />
                <stop offset="1" stopColor="#7c5cff" />
              </linearGradient>
              <filter id="soft" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation="10" result="b" />
                <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>

            {/* request → core */}
            <line x1="380" y1="86" x2="380" y2="128" stroke="url(#qgrad)" strokeWidth="2"
              className={reduce ? undefined : "flow-line"} />
            {!reduce && (
              <circle r="4" fill="#fff" filter="url(#soft)">
                <animateMotion dur="1.4s" repeatCount="indefinite" path="M380,86 L380,128" />
              </circle>
            )}

            {/* core → agents */}
            {nodes.map((n) => {
              const cx = n.x + 70;
              const isOn = n.id === selected;
              return (
                <g key={n.id}>
                  <path
                    d={`M380,208 C380,250 ${cx},250 ${cx},292`}
                    fill="none"
                    stroke={isOn ? "url(#qgrad)" : "rgba(255,255,255,0.16)"}
                    strokeWidth={isOn ? 2.4 : 1.5}
                    className={reduce ? undefined : "flow-line"}
                  />
                  {!reduce && isOn && (
                    <circle r="4" fill={active.accent} filter="url(#soft)">
                      <animateMotion dur="1.2s" repeatCount="indefinite"
                        path={`M380,208 C380,250 ${cx},250 ${cx},292`} />
                    </circle>
                  )}
                </g>
              );
            })}

            {/* YOUR REQUEST node */}
            <g className="node" transform="translate(280,20)">
              <rect className="node-box" width="200" height="56" rx="13" fill="#151b24"
                stroke="rgba(255,255,255,0.14)" />
              <text x="100" y="25" textAnchor="middle" fill="#9aa3b5" fontSize="10"
                letterSpacing="2" fontWeight="700">YOUR REQUEST</text>
              <text x="100" y="44" textAnchor="middle" fill="#f2f5fa" fontSize="13"
                fontWeight="600">"{REQUEST_LABELS[selected]}"</text>
            </g>

            {/* AI CORE node */}
            <g>
              {!reduce && (
                <ellipse cx="380" cy="168" rx="86" ry="42" fill="none"
                  stroke="rgba(91,124,255,0.35)" className="node-pulse" />
              )}
              <g transform="translate(290,128)">
                <rect className="node-box" width="180" height="80" rx="16" fill="rgba(91,124,255,0.13)"
                  stroke="rgba(91,124,255,0.55)" strokeWidth="1.6" />
                <text x="90" y="34" textAnchor="middle" fill="#fff" fontSize="17" fontWeight="700">AI CORE</text>
                <text x="90" y="56" textAnchor="middle" fill="#b9c4ff" fontSize="11"
                  fontFamily="JetBrains Mono, monospace">universal layer</text>
              </g>
            </g>

            {/* agent nodes */}
            {nodes.map((n) => {
              const a = AGENTS.find((x) => x.id === n.id);
              const isOn = n.id === selected;
              return (
                <g key={n.id} className={`node${isOn ? " selected" : ""}`}
                  transform={`translate(${n.x},292)`}
                  onClick={() => pick(n.id)} role="button" tabIndex={0}
                  aria-label={`Route to ${a.title} agent`}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(n.id); } }}
                >
                  <rect className="node-box" width="140" height="76" rx="13"
                    fill={isOn ? a.soft : "#11161e"}
                    stroke={isOn ? a.line : "rgba(255,255,255,0.1)"} />
                  <image
                    href={AGENT_ICONS[n.id]}
                    x="55" y="8" width="30" height="30"
                    preserveAspectRatio="xMidYMid meet"
                  />
                  <text x="70" y="54" textAnchor="middle" fill={isOn ? "#fff" : "#9aa3b5"}
                    fontSize="13" fontWeight="700">{a.title}</text>
                  {isOn && (
                    <text x="70" y="90" textAnchor="middle" fill={a.accent} fontSize="12" fontWeight="800">✓ routed</text>
                  )}
                </g>
              );
            })}
          </svg>

          <p className="arch-caption">
            One request → the right specialized intelligence.{" "}
            <code>{active.title} agent {selected === "jobs" ? "· demo query preselected" : "· selected"}</code>
          </p>
          <div>
            <span className="routed-hint">
              “{requestFor(selected)}” → {active.title} ✓ · others bypassed
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function requestFor(id) {
  return {
    research: "Research open-source RAG tools",
    travel: "Delhi → Dubai under ₹20,000",
    shopping: "Compare Samsung phones",
    jobs: "Find AI Engineer internships in India",
  }[id];
}
