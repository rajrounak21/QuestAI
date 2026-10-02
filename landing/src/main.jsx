import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import LandingApp from "./landing/App.jsx";
import "./landing/index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <LandingApp />
  </StrictMode>
);
