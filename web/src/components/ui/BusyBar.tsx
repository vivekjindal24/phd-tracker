"use client";

import { useEffect, useState } from "react";
import { onBusy } from "@/lib/api";

/** Thin bar while any request is in flight; the CSS delay keeps fast ones invisible. */
export function BusyBar() {
  const [busy, setBusy] = useState(false);
  useEffect(() => onBusy(setBusy), []);
  return busy ? <div className="busy-bar" role="progressbar" aria-label="Loading" /> : null;
}
