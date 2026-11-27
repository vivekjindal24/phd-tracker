"use client";

import { useState } from "react";
import { Button, Card, ErrorText, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import type { PrivacyNotice } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import { NoticeText } from "./NoticeText";
import "./privacy.css";

/** Before anything else, once and again whenever the University changes it (DPDP Act s.5). */
export function PrivacyGate({ onRead }: { onRead: () => Promise<void> }) {
  const notice = useFetch<PrivacyNotice>("/privacy");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function read() {
    setBusy(true);
    setError(null);
    try {
      await api("/privacy/seen", { method: "POST" });
      await onRead();
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <div className="privacy-gate">
      <PageHeader eyebrow="Before you continue" title="How your personal data is used" />
      <Card>
        {notice.data ? <NoticeText notice={notice.data} /> : <ErrorText>{notice.error}</ErrorText>}
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" disabled={busy || !notice.data} onClick={read}>
          {busy ? "Saving…" : "I have read this"}
        </Button>
        <p className="muted">You can read it again at any time from the Privacy link at the bottom of every page.</p>
      </Card>
    </div>
  );
}
