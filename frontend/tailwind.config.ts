import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Legacy tokens — retained for the untouched Admin dashboard surface.
        crag: {
          correct: "#16A34A",
          ambiguous: "#D97706",
          incorrect: "#DC2626",
          database: "#3B82F6",
        },
        dsh: {
          bg: "#FFFFFF",
          surface: "#F5F5F7",
          surfaceHover: "#EFEFF1",
          border: "#E5E5E8",
          ink: "#0A0A0A",
          muted: "#6B6B70",
          pill: "#0A0A0A",
          pillHover: "#262626",
        },
        // shadcn/ui semantic tokens — power the redesigned AI Chat surface.
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "hsl(var(--sidebar-ring))",
        },
        ink: "var(--ink)",
        "ink-2": "var(--ink-2)",
        "ink-3": "var(--ink-3)",
        surface: "var(--surface)",
        canvas: "var(--canvas)",
        page: "var(--page)",
        inset: "var(--inset)",
        field: "var(--field)",
        hover: "var(--hover)",
        "hover-2": "var(--hover-2)",
        line: "var(--line)",
        "line-strong": "var(--line-strong)",
        "line-soft": "var(--line-soft)",
        "accent-ink": "var(--accent-ink)",
        "accent-tint": "var(--accent-tint)",
        green: "var(--green)",
        "green-tint": "var(--green-tint)",
        orange: "var(--orange)",
        "orange-tint": "var(--orange-tint)",
        red: "var(--red)",
        "red-tint": "var(--red-tint)",
      },
      boxShadow: {
        hairline: "var(--shadow-hairline)",
        btn: "var(--shadow-btn)",
        card: "var(--shadow-card)",
        raised: "var(--shadow-raised)",
        overlay: "var(--shadow-overlay)",
      },
      borderRadius: {
        "4xl": "2rem",
        lg: "var(--radius)",
        md: "calc(var(--radius) - 4px)",
        sm: "calc(var(--radius) - 6px)",
        chip: "6px",
        control: "8px",
        card: "10px",
        window: "14px",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "pixel-on": {
          "0%, 100%": { opacity: "0.15" },
          "18%, 42%": { opacity: "1" },
          "62%": { opacity: "0.15" },
        },
        "shimmer-text": {
          from: { backgroundPosition: "150% center" },
          to: { backgroundPosition: "-50% center" },
        },
        "pop-in": {
          from: { opacity: "0", transform: "scale(0.95)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "caret-blink": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "pixel-on": "pixel-on 650ms ease-in-out infinite",
        "shimmer-text": "shimmer-text 1.4s linear infinite",
        "pop-in": "pop-in 200ms cubic-bezier(0.16,1,0.3,1) both",
        "fade-up": "fade-up 320ms cubic-bezier(0.23,1,0.32,1) both",
        "fade-in": "fade-in 300ms ease-out both",
        "caret-blink": "caret-blink 1s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
