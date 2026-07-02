import { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.emergence.exobrain",
  appName: "Exobrain",
  webDir: "dist",
  bundledWebRuntime: false,
  server: {
    // No remote server — fully self-contained offline app
    androidScheme: "https",
  },
  android: {
    allowMixedContent: false,
  },
};

export default config;
