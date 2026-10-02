import { useCallback, useEffect, useState } from "react";
import Navbar from "./components/Navbar.jsx";
import Hero from "./components/Hero.jsx";
import Marquee from "./components/Marquee.jsx";
import Agents from "./components/Agents.jsx";
import HowItWorks from "./components/HowItWorks.jsx";
import Universal from "./components/Universal.jsx";
import Examples from "./components/Examples.jsx";
import JobAlerts from "./components/JobAlerts.jsx";
import Closing from "./components/Closing.jsx";
import LegalPage from "./components/LegalPage.jsx";
import FlowPage from "./components/FlowPage.jsx";

function routeFromHash() {
  const h = window.location.hash;
  if (h.startsWith("#/privacy")) return "privacy";
  if (h.startsWith("#/terms")) return "terms";
  if (h.startsWith("#/about")) return "about";
  if (h.startsWith("#/flow/research")) return "flow-research";
  if (h.startsWith("#/flow/shopping")) return "flow-shopping";
  if (h.startsWith("#/flow/travel")) return "flow-travel";
  return "home";
}

const TITLES = {
  home: "QuestAI — One AI Superapp. Four specialized agents.",
  privacy: "Privacy Policy — QuestAI",
  terms: "Terms of Service — QuestAI",
  about: "About Us — QuestAI",
  "flow-research": "Research flow — QuestAI",
  "flow-shopping": "Shopping flow — QuestAI",
  "flow-travel": "Travel flow — QuestAI",
};

export default function App() {
  const [route, setRoute] = useState(routeFromHash);

  const sync = useCallback(() => {
    const r = routeFromHash();
    setRoute((prev) => {
      if (prev !== r) {
        if (r === "home") {
          // coming back (e.g. flow page → #agents): land on the anchor
          const id = window.location.hash.replace("#", "");
          if (id) requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView());
          else window.scrollTo(0, 0);
        } else {
          window.scrollTo(0, 0);
        }
      } else if (r === "home") {
        // same-page anchor (e.g. back from legal via #top): scroll to it
        const id = window.location.hash.replace("#", "");
        if (id) requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView());
      }
      return r;
    });
  }, []);

  useEffect(() => {
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, [sync]);

  useEffect(() => {
    document.title = TITLES[route];
  }, [route]);

  if (route !== "home") {
    if (route === "flow-research") return <div className="landing-scope"><FlowPage flowId="research" /></div>;
    if (route === "flow-shopping") return <div className="landing-scope"><FlowPage flowId="shopping" /></div>;
    if (route === "flow-travel") return <div className="landing-scope"><FlowPage flowId="travel" /></div>;
    return <div className="landing-scope"><LegalPage doc={route} /></div>;
  }

  return (
    <div className="landing-scope">
      <a href="#explore" style={{
        position: "absolute", left: -9999, top: 0, background: "#fff",
        color: "#000", padding: 10, zIndex: 100,
      }}
        onFocus={(e) => { e.currentTarget.style.left = 8; }}
        onBlur={(e) => { e.currentTarget.style.left = -9999; }}>
        Skip to content
      </a>
      <div className="bg-grid" aria-hidden="true" />
      <div className="bg-glow" aria-hidden="true" />
      <div className="bg-glow-b" aria-hidden="true" />
      <Navbar />
      <main id="top">
        <Hero />
        <Marquee />
        <Agents />
        <HowItWorks />
        <Universal />
        <Examples />
        <JobAlerts />
        <Closing />
      </main>
    </div>
  );
}
