"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Comments } from "@/components/Comments";
import { DownloadButton } from "@/components/DownloadButton";
import { Celebrate } from "@/components/items/Celebrate";
import { ChainSteps } from "@/components/items/ChainSteps";
import { StateBadge } from "@/components/items/StateBadge";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { ItemView } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "./item.css";

const ACTION_TEXT: Record<string, string> = {
  submit: "submitted",
  resubmit: "resubmitted",
  approve: "approved",
  send_back: "sent back",
};

function celebratedKey(id: string) {
  return `anveshan.celebrated.${id}`;
}

/** The scholar sees the celebration once, the first time they open an approved item. */
function firstApprovedView(item: ItemView, myScholarId: string | null | undefined): boolean {
  if (item.state !== "approved" || item.scholar.id !== myScholarId) return false;
  try {
    if (localStorage.getItem(celebratedKey(item.id))) return false;
    localStorage.setItem(celebratedKey(item.id), "1");
    return true;
  } catch {
    return false; // storage blocked: skip the celebration rather than repeat it
  }
}

function ReportContent({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  const summary = String(item.content.summary ?? "");
  const [draft, setDraft] = useState(summary);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setDraft(summary), [summary]);

  async function save() {
    setError(null);
    try {
      onSaved(await api<ItemView>(`/reports/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ summary: draft }),
      }));
      setEditing(false);
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <Card>
      <h2>Summary of progress</h2>
      {editing ? (
        <Field label="Summary" hint="At least 20 characters.">
          <textarea className="summary-edit" value={draft} maxLength={20000}
            onChange={(e) => setDraft(e.target.value)} />
        </Field>
      ) : (
        <p className="prose">{summary}</p>
      )}
      <ErrorText>{error}</ErrorText>
      {item.can_edit && (editing ? (
        <div className="row">
          <Button kind="primary" onClick={save}>Save</Button>
          <Button kind="ghost" onClick={() => { setDraft(summary); setEditing(false); }}>Cancel</Button>
        </div>
      ) : (
        <Button onClick={() => setEditing(true)}>Edit summary</Button>
      ))}
    </Card>
  );
}

function Actions({ item, run }: { item: ItemView; run: (action: string, body?: object) => Promise<void> }) {
  const [comment, setComment] = useState("");
  const [target, setTarget] = useState<string>("initiator");
  const [busy, setBusy] = useState(false);

  async function go(action: string, body?: object) {
    setBusy(true);
    try {
      await run(action, body);
      setComment("");
    } finally {
      setBusy(false);
    }
  }

  if (item.can_submit) {
    return (
      <Card>
        <h2>Ready?</h2>
        <p className="muted">Once submitted, the summary is locked while it goes up the chain.</p>
        <Button kind="primary" disabled={busy} onClick={() => go("submit")}>Submit for approval</Button>
      </Card>
    );
  }
  if (item.can_resubmit) {
    return (
      <Card>
        <h2>Sent back to you</h2>
        <p className="muted">Fix what was asked (see the history below), then resubmit. It starts again from the first step.</p>
        <Button kind="primary" disabled={busy} onClick={() => go("resubmit")}>Resubmit</Button>
      </Card>
    );
  }
  if (item.can_act) {
    const toStep = target === "initiator" ? null : Number(target);
    return (
      <Card className="act">
        <h2>Your decision · {item.waiting_on}</h2>
        <Field label="Comment" hint="Optional when approving; required when sending back.">
          <textarea value={comment} maxLength={4000} onChange={(e) => setComment(e.target.value)} />
        </Field>
        <div className="row">
          <Button kind="primary" disabled={busy} onClick={() => go("approve", { comment: comment || null })}>
            Approve
          </Button>
        </div>
        <div className="send-back">
          <Field label="Send back to">
            <select value={target} onChange={(e) => setTarget(e.target.value)}>
              {item.send_back_targets.map((t) => (
                <option key={String(t.to_step)} value={t.to_step === null ? "initiator" : String(t.to_step)}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>
          <Button kind="danger" disabled={busy || !comment.trim()}
            onClick={() => go("send-back", { comment, to_step: toStep })}>
            Send back
          </Button>
        </div>
      </Card>
    );
  }
  if (item.blocked_reason) {
    return <Card><p className="muted">{item.blocked_reason}</p></Card>;
  }
  return null;
}

export default function ItemPage() {
  const { type, id } = useParams<{ type: string; id: string }>();
  const { me, reload: reloadMe } = useSession();
  const { data: item, error, setData } = useFetch<ItemView>(`/items/${type}/${id}`);
  const [actError, setActError] = useState<string | null>(null);
  const [celebrate, setCelebrate] = useState(false);

  useEffect(() => {
    if (item && firstApprovedView(item, me?.scholar_id)) setCelebrate(true);
  }, [item, me?.scholar_id]);

  async function run(action: string, body?: object) {
    setActError(null);
    try {
      const next = await api<ItemView>(`/items/${type}/${id}/${action}`, {
        method: "POST",
        body: JSON.stringify(body ?? {}),
      });
      setData(next);
      if (action === "approve" && next.state === "approved") setCelebrate(true);
      reloadMe(); // queue / notification counts changed
    } catch (e) {
      setActError(errorText(e));
    }
  }

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!item) return null;
  return (
    <>
      {celebrate && <Celebrate onDone={() => setCelebrate(false)} />}
      <PageHeader eyebrow={`${item.label} · ${item.scholar.name}`} title={item.title}
        actions={<>
          <StateBadge state={item.state} waitingOn={item.waiting_on} />
          {item.item_type === "progress_report" && (
            <DownloadButton path={`/reports/${item.id}.pdf`}>Download PDF</DownloadButton>
          )}
        </>} />
      <div className="item-grid">
        <div className="item-main">
          <Card>
            <h2>Approval chain</h2>
            <ChainSteps chain={item.chain} />
          </Card>
          {item.item_type === "progress_report" && <ReportContent item={item} onSaved={setData} />}
          {item.item_type === "progress_report" && <Comments target="progress_reports" recordId={item.id} />}
        </div>
        <div className="item-side">
          <ErrorText>{actError}</ErrorText>
          <Actions item={item} run={run} />
          <Card>
            <h2>History</h2>
            {item.history.length === 0 ? (
              <p className="muted">Not submitted yet.</p>
            ) : (
              <ol className="history">
                {item.history.map((h, i) => (
                  <li key={i}>
                    <strong>{h.actor}</strong> {ACTION_TEXT[h.action] ?? h.action}
                    {h.step && h.action !== "submit" && ` at ${h.step}`}
                    {h.to && ` → ${h.to}`}
                    <time dateTime={h.at}>{new Date(h.at).toLocaleString()}</time>
                    {h.comment && <blockquote>{h.comment}</blockquote>}
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
