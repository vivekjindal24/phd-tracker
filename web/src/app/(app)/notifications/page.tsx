"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { Button, Card, ErrorText, PageHeader } from "@/components/ui/kit";
import { api, ApiError } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { NotificationItem } from "@/lib/types";
import "./notifications.css";

export default function NotificationsPage() {
  const { reload } = useSession();
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
                {n.link && <Link href={n.link}>Open</Link>}
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
    </>
  );
}
