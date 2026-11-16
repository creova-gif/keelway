import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "@/styles/tokens.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Keelway Dev App mount failed: missing #root element in index.html");
}

createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
