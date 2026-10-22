"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ShareChecks } from "@/components/meetings/ShareChecks";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Meeting, MeetingShare } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "../meetings.css";

export default function MeetingDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: m, error, setData } = useFetch<Meeting>(`/meetings/${id}`);
  const [editing, setEditing] = useState(false);
  const [minutes, setMinutes] = useState("");
  const [actions, setActions] = useState("");
  const [share, setShare] = useState<MeetingShare[]>([]);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!m) return;
    setMinutes(m.minutes ?? "");
    setActions(m.action_items ?? "");
    setShare(m.shared_with);
  }, [m]);

  async function patch(body: Record<string, unknown>) {
    setSaveError(null);
    try {
      setData(await api<Meeting>(`/meetings/${id}`, { method: "PATCH", body: JSON.stringify(body) }));
      setEditing(false);
    } catch (e) {
      setSaveError(errorText(e));
    }
  }

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!m) return null;
  return (
    <>
      <PageHeader eyebrow={`${m.scholar.name} · ${m.supervisor.name}`}
        title={`Meeting · ${formatDate(m.meeting_date)}`} />
      <div className="meeting-detail">
        {m.redacted ? (
          <Card className="empty-state">
            <h2>Minutes not shared</h2>
            <p>The supervisor hasn&apos;t shared this meeting&apos;s minutes with your role.</p>
          </Card>
        ) : (
          <Card>
            <h2>Agenda</h2>
            <p className="meeting-body">{m.agenda}</p>
            <h2 style={{ marginTop: "var(--space-5)" }}>Minutes</h2>
            {editing ? (
              <Field label="Minutes">
                <textarea value={minutes} onChange={(e) => setMinutes(e.target.value)} maxLength={20000} />
              </Field>
            ) : (
              <p className="meeting-body">{m.minutes || <span className="muted">None recorded</span>}</p>
            )}
            <h2 style={{ marginTop: "var(--space-5)" }}>Action items</h2>
            {editing ? (
              <Field label="Action items">
                <textarea value={actions} onChange={(e) => setActions(e.target.value)} maxLength={20000} />
              </Field>
            ) : (
              <p className="meeting-body">{m.action_items || <span className="muted">None</span>}</p>
            )}
            {m.next_meeting_date && <p><strong>Next meeting:</strong> {formatDate(m.next_meeting_date)}</p>}
            <ErrorText>{saveError}</ErrorText>
            {m.can_edit && (editing ? (
              <div className="row">
                <Button kind="primary" onClick={() => patch({ minutes, action_items: actions })}>Save</Button>
                <Button kind="ghost" onClick={() => setEditing(false)}>Cancel</Button>
              </div>
            ) : (
              <Button onClick={() => setEditing(true)}>Edit minutes</Button>
            ))}
          </Card>
        )}
        {m.can_share && (
          <Card>
            <ShareChecks value={share} onChange={setShare} />
            <Button kind="secondary" style={{ marginTop: "var(--space-3)" }}
              disabled={share.join() === m.shared_with.join()}
              onClick={() => patch({ shared_with: share })}>
              Save sharing
            </Button>
          </Card>
        )}
        <p className="stamp">
          Logged {new Date(m.created_at).toLocaleString()}
          {m.updated_at !== m.created_at && ` · last edited ${new Date(m.updated_at).toLocaleString()}`}
        </p>
        <p><Link href="/meetings">← All meetings</Link></p>
      </div>
    </>
  );
}
