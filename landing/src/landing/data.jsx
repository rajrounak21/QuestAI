import { AGENT_ICONS } from "./assets/agentIcons.js";

export const AGENTS = [
  {
    id: "research",
    index: "01",
    icon: <img src={AGENT_ICONS.research} alt="" aria-hidden="true" style={{ width: 28, height: 28, objectFit: "contain" }} />,
    title: "Research",
    desc: "Turn complex questions into structured, evidence-backed research.",
    caps: ["Web research", "Source discovery", "Evidence validation", "Structured reports"],
    cta: "Explore Research",
    accent: "#5b7cff",
    soft: "rgba(91,124,255,0.13)",
    line: "rgba(91,124,255,0.35)",
  },
  {
    id: "travel",
    index: "02",
    icon: <img src={AGENT_ICONS.travel} alt="" aria-hidden="true" style={{ width: 28, height: 28, objectFit: "contain" }} />,
    title: "Travel",
    desc: "Find flights, hotels and build smarter trips without switching between tools.",
    caps: ["Flights", "Hotels", "Trip planning", "Travel research"],
    cta: "Explore Travel",
    accent: "#56e1d5",
    soft: "rgba(86,225,213,0.10)",
    line: "rgba(86,225,213,0.35)",
  },
  {
    id: "shopping",
    index: "03",
    icon: <img src={AGENT_ICONS.shopping} alt="" aria-hidden="true" style={{ width: 28, height: 28, objectFit: "contain" }} />,
    title: "Shopping",
    desc: "Discover products and compare prices across multiple sources.",
    caps: ["Product discovery", "Price comparison", "Store comparison", "Product links"],
    cta: "Explore Shopping",
    accent: "#f3c96a",
    soft: "rgba(243,201,106,0.10)",
    line: "rgba(243,201,106,0.35)",
  },
  {
    id: "jobs",
    index: "04",
    icon: <img src={AGENT_ICONS.jobs} alt="" aria-hidden="true" style={{ width: 28, height: 28, objectFit: "contain" }} />,
    title: "Jobs",
    desc: "Find relevant opportunities, match them with your resume and prepare applications.",
    caps: ["Job search", "Resume matching", "Tailored CV", "Automated alerts"],
    cta: "Explore Jobs",
    accent: "#56d9a0",
    soft: "rgba(86,217,160,0.10)",
    line: "rgba(86,217,160,0.35)",
  },
];

export const EXAMPLES = [
  { q: "Research the latest open-source RAG evaluation tools.", badge: "Research", color: "#5b7cff" },
  { q: "Find a flight from Delhi to Dubai under $50.", badge: "Travel", color: "#56e1d5" },
  { q: "Compare Samsung phones under ₹30,000.", badge: "Shopping", color: "#f3c96a" },
  { q: "Find AI Engineer internships in India.", badge: "Jobs", color: "#56d9a0" },
];

export const STEPS = [
  { n: "ASK", title: "Tell us what you need", desc: "Describe the task in natural language — a question, a trip, a product, a role." },
  { n: "ROUTE", title: "We pick the right agent", desc: "The system identifies the specialized agent built for that exact task." },
  { n: "DELIVER", title: "Get a usable result", desc: "The agent researches, searches, compares or prepares a structured answer." },
];

export const STACK = ["Python", "FastAPI", "LangGraph", "LLMs", "SerpApi", "MongoDB", "n8n"];
