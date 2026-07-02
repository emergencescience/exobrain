import React, { useState } from "react";
import { loadConfig } from "./config";
import ApiKeySettings from "./components/ApiKeySettings";
import ExobrainEditor from "./components/ExobrainEditor";

export default function App() {
  const cfg = loadConfig();
  const [showSettings, setShowSettings] = useState(!cfg.setupDone);

  if (showSettings) {
    return <ApiKeySettings onComplete={() => setShowSettings(false)} />;
  }

  return <ExobrainEditor onSettings={() => setShowSettings(true)} />;
}
