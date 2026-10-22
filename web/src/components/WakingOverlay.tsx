"use client";

import { useEffect, useState } from "react";
import { onWaking } from "@/lib/api";
import { Owl } from "./brand/Owl";
import "./waking.css";

/** Free-tier cold start (15–60 s): the sleeping owl instead of a frozen page (ARCHITECTURE.md §11). */
export function WakingOverlay() {
  const [waking, setWaking] = useState(false);
  useEffect(() => onWaking(setWaking), []);
  if (!waking) return null;
  return (
    <div className="waking clay" role="status" aria-live="polite">
      <Owl pose="sleeping" size={84} />
      <div>
        <strong>Waking up the server…</strong>
        <p>Free hosting naps when nobody&apos;s around. This takes up to a minute, just once.</p>
      </div>
    </div>
  );
}
