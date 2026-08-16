# Exobrain frontend

Light academic editor. This package is the **only** Exobrain UI source.

## Hosts

| Host | Route | API |
| --- | --- | --- |
| OSS (`src/app/page.tsx`) | `/` | `http://localhost:8080/api/*` (`routeMode: "engine"`) |
| emergence.science | `/{lang}/exobrain` | `/api/play/exobrain/*` (`routeMode: "orchestrator"`) |

The portal copies these components with `npm run sync:exobrain-editor`. Do not edit the copy.

SaaS passes `embedChrome={false}`, JWT headers, and `onAuthRequired` for ConnectModal. Chat and verify still require login; anonymous drafts use `exobrain_anon_pending_v1`.
