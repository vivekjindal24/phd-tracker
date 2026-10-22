"use client";

import { useEffect, useState } from "react";
import { Button } from "./ui/kit";

const KEY = "anveshan.theme";

function isDark(): boolean {
  const chosen = document.documentElement.dataset.theme;
  if (chosen) return chosen === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeToggle() {
  const [dark, setDark] = useState<boolean | null>(null);
  useEffect(() => setDark(isDark()), []);

  function toggle() {
    const next = isDark() ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // storage blocked: the choice lasts for this page only
    }
    setDark(next === "dark");
  }

  return (
    <Button
      kind="plain"
      className="btn-icon"
      onClick={toggle}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
    >
      <span aria-hidden="true">{dark ? "☀️" : "🌙"}</span>
    </Button>
  );
}
