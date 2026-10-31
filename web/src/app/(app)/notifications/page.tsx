"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type MouseEvent, useCallback, useEffect, useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api, ApiError } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { NotificationItem } from "@/lib/types";
import "./notifications.css";

// Mirrors the API's NotificationCategory; muting affects that channel only (PRD F5).
const CATEGORIES: [string, string][] = [
  ["approval_waiting", "An item is waiting for my step"],
  ["sent_back", "An item is sent back to me"],
  ["approved", "My item is approved"],
  ["apr_due", "A progress report is due or overdue"],
  ["meeting_tomorrow", "A supervision meeting is tomorrow"],
  ["seminar", "Progress seminars and their to-dos"],
  ["fellowship_ending", "A fellowship is ending"],
  ["grant_alert", "A project is ending or running low on funds"],
  ["system", "Other updates (comments, meetings logged, thesis)"],
];

function EmailSettings() {
  const { me, reload } = useSession();
  const [error, setError] = useState<string | null>(null);
  if (!me) return null;
  const muted = me.email_muted;

  async function toggle(category: string) {
    setError(null);
    const next = muted.includes(category) ? muted.filter((c) => c !== category) : [...muted, category];
    try {
      await api("/auth/me/email-muted", { method: "PUT", body: JSON.stringify({ email_muted: next }) });
      await reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <Card className="email-settings">
      <fieldset className="check-row">
        <legend>Email me when…</legend>
        {CATEGORIES.map(([key, label]) => (
          <label key={key} className="check">
            <input type="checkbox" checked={!muted.includes(key)} onChange={() => toggle(key)} />
            {label}
          </label>
        ))}
      </fieldset>
      <p className="muted">Everything still arrives here in your inbox; this only changes email.</p>
      <ErrorText>{error}</ErrorText>
    </Card>
  );
}

/** A 10-digit number is taken as Indian; anything else must already be +<country><number>. */
function toE164(raw: string): string {
  const digits = raw.replace(/[\s()-]/g, "");
  return /^\d{10}$/.test(digits) ? `+91${digits}` : digits;
}

function WhatsappSettings() {
  const { me, reload } = useSession();
  const [draft, setDraft] = useState(me?.whatsapp_number ?? "");
  const [error, setError] = useState<string | null>(null);
  if (!me?.whatsapp_available) return null;
  const { whatsapp_number: number, whatsapp_muted: muted } = me;

  async function save(whatsapp_number: string | null, whatsapp_muted: string[]) {
    setError(null);
    try {
      await api("/auth/me/whatsapp", {
        method: "PUT",
        body: JSON.stringify({ whatsapp_number, whatsapp_muted }),
      });
      await reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  function toggle(category: string) {
    const next = muted.includes(category) ? muted.filter((c) => c !== category) : [...muted, category];
    return save(number, next);
  }

  async function remove() {
    await save(null, []);
    setDraft("");
  }

  return (
    <Card className="email-settings">
      <h2>WhatsApp</h2>
      {number ? (
        <>
          <p>
            Messages go to <strong>{number}</strong>. They say only what kind of thing happened and
            link here — never names or details.
          </p>
          <fieldset className="check-row">
            <legend>WhatsApp me when…</legend>
            {CATEGORIES.map(([key, label]) => (
              <label key={key} className="check">
                <input type="checkbox" checked={!muted.includes(key)} onChange={() => toggle(key)} />
                {label}
              </label>
            ))}
          </fieldset>
          <Button kind="ghost" onClick={remove}>
            Stop WhatsApp messages
          </Button>
        </>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save(toE164(draft), []);
          }}
        >
          <Field label="Your WhatsApp number" hint="10 digits for India, or +<country code><number>.">
            <input
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              required
            />
          </Field>
          <p className="muted">
            Saving it means you agree to get Anveshan updates on WhatsApp. You can stop any time.
          </p>
          <Button type="submit">Send me WhatsApp updates</Button>
        </form>
      )}
      <ErrorText>{error}</ErrorText>
    </Card>
  );
}

export default function NotificationsPage() {
  const { reload } = useSession();
  const router = useRouter();
  const [items, setItems] = useState<NotificationItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await api<NotificationItem[]>("/notifications"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function markRead(id: string) {
    try {
      await api(`/notifications/${id}/read`, { method: "POST" });
      await Promise.all([load(), reload()]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  /** Opening a notification reads it: mark it first, then go to the record. A new-tab click
   *  (cmd/ctrl/middle) keeps the browser's own behaviour and still marks it read. */
  async function open(e: MouseEvent<HTMLAnchorElement>, n: NotificationItem) {
    const newTab = e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0;
    if (!newTab) e.preventDefault();
    if (!n.read_at) await markRead(n.id);
    if (!newTab && n.link) router.push(n.link);
  }

  async function markAll() {
    try {
      await api("/notifications/read-all", { method: "POST" });
      await Promise.all([load(), reload()]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  const unread = items?.some((n) => !n.read_at) ?? false;
  return (
    <>
      <PageHeader
        title="Notifications"
        actions={unread && <Button onClick={markAll}>Mark all read</Button>}
      />
      <ErrorText>{error}</ErrorText>
      {items && items.length === 0 && (
        <Card className="empty-state">
          <Owl pose="empty" size={96} />
          <h2>All quiet</h2>
          <p>You&apos;ll be told here when something needs you.</p>
        </Card>
      )}
      {items && items.length > 0 && (
        <ul className="inbox clay">
          {items.map((n) => (
            <li key={n.id} className={n.read_at ? "read" : "unread"}>
              <div>
                <strong>{n.title}</strong>
                {n.body && <p>{n.body}</p>}
                <time dateTime={n.created_at}>{new Date(n.created_at).toLocaleString()}</time>
              </div>
              <div className="inbox-actions">
                {n.link && <Link href={n.link} onClick={(e) => open(e, n)}>Open</Link>}
                {!n.read_at && (
                  <Button kind="ghost" onClick={() => markRead(n.id)}>
                    Mark read
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      <EmailSettings />
      <WhatsappSettings />
    </>
  );
}
