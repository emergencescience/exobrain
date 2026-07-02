# Exobrain Mobile

AI-powered mathematical paper editor as a native Android APK.

Works on **Android** and **HarmonyOS** (Huawei Mate 80, etc.).

## Features

- 📝 Markdown editor with LaTeX math ($...$ and $$...$$)
- 🤖 AI assistant to draft, refine, and verify mathematical documents
- 🔑 **Self-Hosted mode** — bring your own DeepSeek API key, zero dependency
- ☁️ **SaaS mode** — connect to emergence.science for SymPy verification, RAG, cloud storage
- 📱 Native Android APK — install directly, works offline for editing

## Install

1. Go to [Releases](https://github.com/emergencescience/exobrain-mobile/releases)
2. Download the latest APK
3. On your device: Settings → Security → "Install from unknown sources" → Enable
4. Open the APK to install

## Modes

### 🔑 Self-Hosted (Recommended)

Use your own DeepSeek API key. All LLM calls go directly to DeepSeek.

- No account needed
- Your API key stays on device
- Works with any OpenAI-compatible endpoint

### ☁️ Emergence SaaS

Connect to emergence.science for premium features:

- SymPy mathematical verification (check your derivations!)
- RAG-enhanced math knowledge base
- Cloud sync across devices
- Usage credits tracking

## Dev

```bash
# Install
npm install

# Dev server
npx vite

# Build web assets
npx vite build

# Build APK (requires Android SDK)
npx cap add android
npx cap sync
cd android && ./gradlew assembleRelease
```

## License

MIT
