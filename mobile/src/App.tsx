import React, { useState, useEffect } from "react";
import { loadConfig } from "./config";
import ApiKeySettings from "./components/ApiKeySettings";
import ExobrainEditor from "./components/ExobrainEditor";

export default function App() {
  const cfg = loadConfig();
  const [showSettings, setShowSettings] = useState(!cfg.setupDone);

  // Apply theme on mount and when settings change
  useEffect(() => {
    const current = loadConfig();
    document.documentElement.setAttribute("data-theme", current.theme || "dark");
  }, [showSettings]);

  if (showSettings) {
    return <ApiKeySettings onComplete={() => setShowSettings(false)} />;
  }

  return <ExobrainEditor onSettings={() => setShowSettings(true)} />;
}
