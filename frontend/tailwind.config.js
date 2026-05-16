/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: {
          50:  "#f0f0ff",
          100: "#e2e1ff",
          200: "#cac8ff",
          300: "#a9a6ff",
          400: "#8780ff",
          500: "#6b5fff",
          600: "#5b3ef5",
          700: "#4e2ed8",
          800: "#4027b0",
          900: "#382490",
          950: "#211561",
        },
        accent: {
          blue:   "#00d4ff",
          purple: "#9747ff",
          pink:   "#ff47b8",
          green:  "#00ff87",
        },
        glass: {
          light: "rgba(255,255,255,0.08)",
          dark:  "rgba(0,0,0,0.35)",
          border: "rgba(255,255,255,0.15)",
        },
      },
      fontFamily: {
        sans:  ["Inter", "system-ui", "sans-serif"],
        mono:  ["JetBrains Mono", "Fira Code", "monospace"],
        display: ["Outfit", "Inter", "sans-serif"],
      },
      backdropBlur: {
        xs: "2px",
        sm: "4px",
        md: "12px",
        lg: "24px",
        xl: "48px",
      },
      animation: {
        "gradient-x": "gradient-x 8s ease infinite",
        "gradient-y": "gradient-y 8s ease infinite",
        "float":       "float 6s ease-in-out infinite",
        "pulse-glow":  "pulse-glow 2s cubic-bezier(0.4,0,0.6,1) infinite",
        "scan-line":   "scan-line 2s linear infinite",
        "slide-in":    "slide-in 0.3s cubic-bezier(0.16,1,0.3,1)",
        "fade-in":     "fade-in 0.4s ease-out",
      },
      keyframes: {
        "gradient-x": {
          "0%,100%": { backgroundPosition: "0% 50%" },
          "50%":     { backgroundPosition: "100% 50%" },
        },
        "gradient-y": {
          "0%,100%": { backgroundPosition: "50% 0%" },
          "50%":     { backgroundPosition: "50% 100%" },
        },
        float: {
          "0%,100%": { transform: "translateY(0px)" },
          "50%":     { transform: "translateY(-10px)" },
        },
        "pulse-glow": {
          "0%,100%": { boxShadow: "0 0 20px rgba(107,95,255,0.3)" },
          "50%":     { boxShadow: "0 0 40px rgba(107,95,255,0.7)" },
        },
        "scan-line": {
          "0%":   { top: "0%" },
          "100%": { top: "100%" },
        },
        "slide-in": {
          "0%":   { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
      backgroundImage: {
        "mesh-dark": `
          radial-gradient(at 20% 20%, rgba(107,95,255,0.25) 0px, transparent 50%),
          radial-gradient(at 80% 10%, rgba(0,212,255,0.15) 0px, transparent 50%),
          radial-gradient(at 60% 80%, rgba(151,71,255,0.2) 0px, transparent 50%),
          linear-gradient(135deg, #0a0a1a 0%, #0f0a2a 50%, #0a0f1a 100%)
        `,
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
  ],
};
