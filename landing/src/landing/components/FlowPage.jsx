import { useEffect, useRef, useState } from "react";
import { FLOWS, FlowSvg } from "./AgentFlow.jsx";

const TITLES = {
  research: "Research flow — QuestAI",
  shopping: "Shopping flow — QuestAI",
  travel: "Travel flow — QuestAI",
};

// Zoom is a multiplier over the fitted scale. 1x = whole graph visible,
// centered, no scroll. Zooming in enlarges from the center; the viewport
// scrolls only when zoomed past what fits.
const MIN_ZOOM = 1;
const MAX_ZOOM = 5;
const MAX_FIT = 1.5;

function FlowChart({ graph, accent }) {
  const wrapRef = useRef(null);
  const [box, setBox] = useState({ w: 0, h: 0 });
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      setBox({ w: r.width, h: r.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const fit =
    box.w > 0 && box.h > 0
      ? Math.min(MAX_FIT, Math.min(box.w / graph.w, box.h / graph.h))
      : 0;
  const widthPx = fit > 0 ? Math.max(1, Math.floor(graph.w * fit * zoom)) : undefined;
  const step = (d) =>
    setZoom((z) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, +(z + d).toFixed(2))));

  return (
    <>
      {graph.sectionTitle && <h2 className="aflow-section-title">{graph.sectionTitle}</h2>}
      <div className="aflow-zoombar" role="toolbar" aria-label="Graph zoom">
        <button onClick={() => step(-0.25)} disabled={zoom <= MIN_ZOOM} aria-label="Zoom out">−</button>
        <span>{Math.round(zoom * 100)}%</span>
        <button onClick={() => step(0.25)} disabled={zoom >= MAX_ZOOM} aria-label="Zoom in">+</button>
        <button className="aflow-fit" onClick={() => setZoom(1)}>Fit</button>
      </div>
      <div className="panel aflow-page-chart" ref={wrapRef}>
        {widthPx ? (
          <div className="aflow-canvas">
            <FlowSvg flow={{ ...graph, accent }} widthPx={widthPx} />
          </div>
        ) : null}
      </div>
    </>
  );
}

export default function FlowPage({ flowId }) {
  const flow = FLOWS[flowId];

  useEffect(() => {
    if (flow) document.title = TITLES[flowId] || "QuestAI";
    window.scrollTo(0, 0);
  }, [flow, flowId]);

  if (!flow) return null;

  const charts = flow.sections || [{ ...flow, sectionTitle: null }];

  return (
    <div className="aflow-page">
      <div className="container">
        <a className="aflow-back link-arrow" href="#agents">
          <span aria-hidden="true" style={{ transform: "scaleX(-1)", display: "inline-block" }}>→</span> All agents
        </a>
        <div className="aflow-page-head">
          <span className="eyebrow" style={{ color: flow.accent }}>LangGraph flow</span>
          <h1>{flow.title} — how it runs</h1>
          <p>{flow.subtitle}</p>
          <div className="aflow-stats">
            {flow.stats.map((s) => (
              <span key={s} className="aflow-stat" style={{ borderColor: flow.accent + "44" }}>{s}</span>
            ))}
          </div>
        </div>
        {charts.map((g, i) => (
          <FlowChart key={g.sectionTitle || i} graph={g} accent={flow.accent} />
        ))}
      </div>
    </div>
  );
}
