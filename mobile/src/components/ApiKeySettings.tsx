import React, { useState } from "react";
import { AppConfig, loadConfig, saveConfig } from "../config";

interface Props {
  onComplete: () => void;
}

export default function ApiKeySettings({ onComplete }: Props) {
  const [cfg, setCfg] = useState<AppConfig>(loadConfig);
  const [showKey, setShowKey] = useState(false);

  const handleSave = () => {
    if (cfg.mode === "self" && !cfg.apiKey.trim()) {
      return; // require API key in self mode
    }
    const updated = { ...cfg, setupDone: true };
    saveConfig(updated);
    onComplete();
  };

  return (
    <div style={{
      minHeight: "100dvh", background: "#0a0a0a", color: "#e0e0e0",
      paddingTop: "max(24px, env(safe-area-inset-top, 0px))",
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", padding: 24, fontFamily: "system-ui, sans-serif",
    }}>
      <div style={{ maxWidth: 400, width: "100%" }}>
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ fontSize: 48, marginBottom: 8 }}>🧠</div>
          <h1 style={{
            fontSize: 28, fontWeight: "bold",
            background: "linear-gradient(135deg, #a855f7, #06b6d4)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            marginBottom: 8,
          }}>
            Exobrain
          </h1>
          <p style={{ fontSize: 14, color: "#666" }}>
            AI-powered mathematical paper editor
          </p>
        </div>

        {/* Mode selector */}
        <div style={{
          display: "flex", borderRadius: 12, overflow: "hidden",
          border: "1px solid #333", marginBottom: 20,
        }}>
          <button
            onClick={() => setCfg({ ...cfg, mode: "self" })}
            style={{
              flex: 1, padding: "10px 0", border: "none",
              background: cfg.mode === "self" ? "#a855f720" : "transparent",
              color: cfg.mode === "self" ? "#a855f7" : "#666",
              fontSize: 13, fontWeight: cfg.mode === "self" ? "bold" : "normal",
              cursor: "pointer",
            }}
          >
            🔑 Self-Hosted
          </button>
          <button
            onClick={() => setCfg({ ...cfg, mode: "saas" })}
            style={{
              flex: 1, padding: "10px 0", border: "none",
              background: cfg.mode === "saas" ? "#06b6d420" : "transparent",
              color: cfg.mode === "saas" ? "#06b6d4" : "#666",
              fontSize: 13, fontWeight: cfg.mode === "saas" ? "bold" : "normal",
              cursor: "pointer",
            }}
          >
            ☁️ Emergence
          </button>
        </div>

        {/* Self-hosted settings */}
        {cfg.mode === "self" && (
          <>
            <label style={{ fontSize: 12, color: "#888", marginBottom: 4, display: "block" }}>
              DeepSeek API Key
            </label>
            <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
              <input
                type={showKey ? "text" : "password"}
                value={cfg.apiKey}
                onChange={(e) => setCfg({ ...cfg, apiKey: e.target.value })}
                placeholder="sk-..."
                style={{
                  flex: 1, padding: "10px 12px", borderRadius: 8,
                  background: "#1a1a1a", border: "1px solid #333",
                  color: "#e0e0e0", fontSize: 14, outline: "none",
                }}
              />
              <button
                onClick={() => setShowKey(!showKey)}
                style={{
                  padding: "10px", borderRadius: 8, border: "1px solid #333",
                  background: "#1a1a1a", color: "#888", cursor: "pointer",
                  fontSize: 16,
                }}
              >
                {showKey ? "🙈" : "👁"}
              </button>
            </div>

            <label style={{ fontSize: 12, color: "#888", marginBottom: 4, display: "block" }}>
              API Base URL
            </label>
            <input
              value={cfg.baseUrl}
              onChange={(e) => setCfg({ ...cfg, baseUrl: e.target.value })}
              placeholder="https://api.deepseek.com"
              style={{
                width: "100%", padding: "10px 12px", borderRadius: 8,
                background: "#1a1a1a", border: "1px solid #333",
                color: "#e0e0e0", fontSize: 14, outline: "none", marginBottom: 16,
              }}
            />

            <label style={{ fontSize: 12, color: "#888", marginBottom: 4, display: "block" }}>
              Model
            </label>
            <input
              value={cfg.model}
              onChange={(e) => setCfg({ ...cfg, model: e.target.value })}
              placeholder="deepseek-chat"
              style={{
                width: "100%", padding: "10px 12px", borderRadius: 8,
                background: "#1a1a1a", border: "1px solid #333",
                color: "#e0e0e0", fontSize: 14, outline: "none", marginBottom: 16,
              }}
            />
          </>
        )}

        {/* SaaS info */}
        {cfg.mode === "saas" && (
          <div style={{
            padding: 16, borderRadius: 8, background: "#06b6d410",
            border: "1px solid #06b6d420", marginBottom: 20, fontSize: 13,
            color: "#888", lineHeight: 1.6,
          }}>
            <p style={{ marginBottom: 8, color: "#06b6d4", fontWeight: "bold" }}>
              ☁️ Emergence SaaS Mode
            </p>
            <p>Connects to api.emergence.science using your Emergence account.</p>
            <p style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
              Features: SymPy verification, RAG, cloud storage, credits tracking.
            </p>
            <p style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
              Login happens in-browser on first use.
            </p>
          </div>
        )}

        {/* Save button */}
        <button
          onClick={handleSave}
          disabled={cfg.mode === "self" && !cfg.apiKey.trim()}
          style={{
            width: "100%", padding: "14px", borderRadius: 12, border: "none",
            background: (cfg.mode === "self" && !cfg.apiKey.trim())
              ? "#333"
              : "linear-gradient(135deg, #a855f7, #06b6d4)",
            color: "#fff", fontSize: 16, fontWeight: "bold",
            cursor: (cfg.mode === "self" && !cfg.apiKey.trim()) ? "not-allowed" : "pointer",
            opacity: (cfg.mode === "self" && !cfg.apiKey.trim()) ? 0.5 : 1,
            marginTop: 8,
          }}
        >
          {cfg.mode === "self" ? "Start Editing" : "Continue"}
        </button>

        <p style={{ textAlign: "center", marginTop: 24, fontSize: 12, color: "#444" }}>
          Settings can be changed anytime in the editor.
        </p>
      </div>
    </div>
  );
}
