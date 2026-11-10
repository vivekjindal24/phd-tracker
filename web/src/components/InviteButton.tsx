"use client";

import { useState } from "react";
import { Button, ErrorText } from "@/components/ui/kit";
import { api } from "@/lib/api";
import type { SettingsData } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

/** Admins (re)send a set-password email; a new link replaces any older one (PRD F2). While the
 *  university requires two-factor login, they can also reset it for someone who lost a phone. */
export function InviteButton({ userId }: { userId: string }) {
  const [state, setState] = useState<"idle" | "busy" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);
  const twoFactor = useFetch<SettingsData>("/settings").data?.require_two_factor ?? false;
  const [reset, setReset] = useState(false);

  async function resetTwoFactor() {
    setError(null);
    try {
      await api(`/users/${userId}/two-factor/reset`, { method: "POST" });
      setReset(true);
    } catch (e) {
      setError(errorText(e));
    }
  }

  async function send() {
    setState("busy");
    setError(null);
    try {
      await api(`/users/${userId}/invite`, { method: "POST" });
      setState("sent");
    } catch (e) {
      setError(errorText(e));
      setState("idle");
    }
  }

  return (
    <div className="invite">
      <Button kind="ghost" disabled={state === "busy"} onClick={send}>
        {state === "busy" ? "Sending…" : "Email a set-password link"}
      </Button>
      {state === "sent" && <p className="muted" role="status">Sent. The link works once, for 72 hours.</p>}
      {twoFactor && <Button kind="ghost" disabled={reset} onClick={resetTwoFactor}>Reset two-factor login</Button>}
      {reset && <p className="muted" role="status">Reset. They set it up again at their next log in.</p>}
      <ErrorText>{error}</ErrorText>
    </div>
  );
}
