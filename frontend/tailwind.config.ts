import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        crag: {
          blue: "#2563EB",
          correct: "#16A34A",
          ambiguous: "#D97706",
          incorrect: "#DC2626",
          database: "#3B82F6",
        },
      },
    },
  },
  plugins: [],
};

export default config;
