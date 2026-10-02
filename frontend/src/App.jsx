import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import LandingApp from "./landing/App.jsx";
import "./landing/index.css";
import AuthCallback from "../auth/AuthCallback";
import ForgotPassword from "../auth/ForgotPassword";
import Home from "../auth/Home";
import Login from "../auth/Login";
import Signup from "../auth/Signup";
import Research from "../research/Research";
import Shopping from "../shopping/Shopping";
import Flights from "../travel/flights/Flights";
import Hotels from "../travel/hotels/Hotels";
import Trips from "../travel/trips/Trips";
import Jobs from "../jobs/Jobs";
import { applyTheme, getTheme } from "../auth/theme";

// Root: "/" = landing page, auth + app routes below.
// Landing uses hash routing (#/privacy...) internally — coexists with these paths.
function DocumentTitle() {
  const { pathname } = useLocation();
  useEffect(() => {
    if (pathname === "/") return; // landing sets its own title
    const seg = pathname.split("/")[1] || "";
    const name =
      {
        "": "QuestAI",
        home: "Home",
        research: "Research",
        shopping: "Shopping",
        flights: "Flights",
        hotels: "Hotels",
        trips: "Trips",
        jobs: "Jobs",
        login: "Login",
        signup: "Sign up",
        "forgot-password": "Reset password",
        auth: "Signing you in",
      }[seg] || "QuestAI";
    document.title = name === "QuestAI" ? name : `QuestAI — ${name}`;
  }, [pathname]);
  return null;
}

export default function App() {
  useEffect(() => {
    applyTheme(getTheme());
  }, []);
  return (
    <BrowserRouter>
      <DocumentTitle />
      <Routes>
        <Route path="/" element={<LandingApp />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/home" element={<Home />} />
        <Route path="/research" element={<Research />} />
        <Route path="/research/:sessionId" element={<Research />} />
        <Route path="/shopping" element={<Shopping />} />
        <Route path="/shopping/:sessionId" element={<Shopping />} />
        <Route path="/flights" element={<Flights />} />
        <Route path="/flights/:sessionId" element={<Flights />} />
        <Route path="/hotels" element={<Hotels />} />
        <Route path="/hotels/:sessionId" element={<Hotels />} />
        <Route path="/trips" element={<Trips />} />
        <Route path="/trips/:sessionId" element={<Trips />} />
        <Route path="/jobs" element={<Jobs />} />
        <Route path="/jobs/:sessionId" element={<Jobs />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
