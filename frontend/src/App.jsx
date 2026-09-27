import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import LandingApp from "./landing/App.jsx";
import "./landing/index.css";
import AuthCallback from "../auth/AuthCallback";
import ForgotPassword from "../auth/ForgotPassword";
import Home from "../auth/Home";
import Login from "../auth/Login";
import Signup from "../auth/Signup";
import Research from "../research/Research";
import { applyTheme, getTheme } from "../auth/theme";

// Root: "/" = landing page, auth + app routes below.
// Landing uses hash routing (#/privacy...) internally — coexists with these paths.
export default function App() {
  useEffect(() => {
    applyTheme(getTheme());
  }, []);
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingApp />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/home" element={<Home />} />
        <Route path="/research" element={<Research />} />
        <Route path="/research/:sessionId" element={<Research />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
