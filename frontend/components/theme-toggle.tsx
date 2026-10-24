"use client";

import { useSyncExternalStore } from "react";
import { getServerThemeSnapshot, getThemeSnapshot, setThemePreference, subscribeTheme } from "../lib/theme";
import styles from "./site-nav.module.css";

export default function ThemeToggle() {
  const [preference, theme] = useSyncExternalStore(subscribeTheme, getThemeSnapshot, getServerThemeSnapshot).split(":");
  const nextTheme = theme === "dark" ? "light" : "dark";

  return <div className={styles.themeControls} role="group" aria-label="Color theme">
    <button type="button" className={styles.themeButton}
      aria-label={`Switch to ${nextTheme} theme`} title={`Switch to ${nextTheme} theme`}
      onClick={() => setThemePreference(nextTheme)}>
      <svg className={styles.sun} aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" />
      </svg>
      <svg className={styles.moon} aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round">
        <path d="M20.5 14A8.5 8.5 0 0 1 10 3.5 8.5 8.5 0 1 0 20.5 14Z" />
      </svg>
    </button>
    <button type="button" className={styles.themeButton} aria-label="Use system theme"
      aria-pressed={preference === "system"} title="Use system theme"
      onClick={() => setThemePreference("system")}>
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="13" rx="2" /><path d="M8 21h8m-4-4v4" />
      </svg>
    </button>
  </div>;
}
