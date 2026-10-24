export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "siniristi-theme";
const CHANGE_EVENT = "siniristi-theme-change";

// Runs in <head> before the body paints. Storage may be unavailable in private
// or embedded browsing; the system preference still works in that case.
export const THEME_INIT_SCRIPT = `(() => {
  let preference = "system";
  try {
    const saved = localStorage.getItem("${STORAGE_KEY}");
    if (saved === "light" || saved === "dark") preference = saved;
  } catch {}
  const dark = preference === "dark" || (preference === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.documentElement.dataset.themePreference = preference;
})();`;

function applyTheme(preference: ThemePreference) {
  const dark = preference === "dark" || (preference === "system"
    && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.documentElement.dataset.themePreference = preference;
}

export function setThemePreference(preference: ThemePreference) {
  applyTheme(preference);
  try {
    if (preference === "system") localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, preference);
  } catch { /* Keep the current tab functional when storage is unavailable. */ }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function getThemeSnapshot() {
  const { themePreference = "system", theme = "light" } = document.documentElement.dataset;
  return `${themePreference}:${theme}`;
}

export function getServerThemeSnapshot() {
  return "system:light";
}

export function subscribeTheme(onChange: () => void) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const onSystemChange = () => {
    if (document.documentElement.dataset.themePreference === "system") {
      applyTheme("system");
      onChange();
    }
  };
  const onStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY && event.key !== null) return;
    const preference = event.newValue === "light" || event.newValue === "dark" ? event.newValue : "system";
    applyTheme(preference);
    onChange();
  };
  media.addEventListener("change", onSystemChange);
  window.addEventListener("storage", onStorage);
  window.addEventListener(CHANGE_EVENT, onChange);
  return () => {
    media.removeEventListener("change", onSystemChange);
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(CHANGE_EVENT, onChange);
  };
}
