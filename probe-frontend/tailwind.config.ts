import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {
    colors: { ink: "#09090b", paper: "#f2f1e8", muted: "#9f9f9c", violet: "#7344ff", acid: "#d9ff46", edge: "#2d2d30" },
    fontFamily: { sans: ["Suisse Intl", "Inter Tight", "Helvetica Neue", "system-ui", "sans-serif"], mono: ["Suisse Intl Mono", "IBM Plex Mono", "SFMono-Regular", "monospace"] },
    animation: { pulseSlow: "pulse 5s ease-in-out infinite" }
  } },
  plugins: []
};
export default config;
