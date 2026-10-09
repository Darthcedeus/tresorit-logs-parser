"use strict";
(() => {
  const key = "tresorit-theme";
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  let preference;
  try { preference = localStorage.getItem(key); } catch { /* Storage may be disabled. */ }
  if (!["light", "dark"].includes(preference)) preference = null;

  function apply(theme) {
    document.documentElement.dataset.theme = theme;
    const toggle = document.getElementById("theme-toggle");
    if (toggle) toggle.setAttribute("aria-pressed", String(theme === "dark"));
  }

  // Set the palette before styles load to avoid a flash of the opposite theme.
  apply(preference || (system.matches ? "dark" : "light"));
  document.addEventListener("DOMContentLoaded", () => {
    apply(document.documentElement.dataset.theme);
    document.getElementById("theme-toggle").addEventListener("click", () => {
      preference = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      apply(preference);
      try { localStorage.setItem(key, preference); } catch { /* Keep the choice for this page. */ }
    });
  });
  system.addEventListener("change", event => {
    if (!preference) apply(event.matches ? "dark" : "light");
  });
})();
