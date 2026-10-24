"use client";

import { useState } from "react";
import { Button, ErrorText } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { errorText } from "@/lib/useFetch";

/** Admins (re)send a set-password email; a new link replaces any older one (PRD F2). */
export function InviteButton({ userId }: { userId: string }) {
  const [state, setState] = useState<"idle" | "busy" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

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
      <ErrorText>{error}</ErrorText>
    </div>
  );
}
