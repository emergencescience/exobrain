// Copyright (c) 2026 Julian. All rights reserved.

export type ExobrainRouteMode = "engine" | "orchestrator";

/** Engine serves `/api/documents`. Orchestrator gateway is already `/api/play/exobrain`. */
export function exobrainApiUrl(base: string, mode: ExobrainRouteMode, path: string): string {
  const trimmed = base.replace(/\/$/, "");
  const rest = path.replace(/^\//, "");
  if (mode === "orchestrator") return `${trimmed}/${rest}`;
  return `${trimmed}/api/${rest}`;
}

export type ExobrainAuthHeaders = Record<string, string>;
