"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Attachments } from "@/components/Attachments";
import { Comments } from "@/components/Comments";
import { DownloadButton } from "@/components/DownloadButton";
import { Celebrate, firstTime } from "@/components/Celebrate";
import { ChainSteps } from "@/components/items/ChainSteps";
import { ClearanceDetails } from "@/components/items/ClearanceDetails";
import { PublicationDetails } from "@/components/items/PublicationDetails";
import { ReportDetails } from "@/components/items/ReportDetails";
import { ThesisDetails } from "@/components/items/ThesisDetails";
import { ThesisEvaluation } from "@/components/items/ThesisEvaluation";
import { StateBadge } from "@/components/items/StateBadge";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { RATING_LABELS } from "@/lib/types";
import type { CommentTarget, ItemType, ItemView, Rating } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "./item.css";

const ACTION_TEXT: Record<string, string> = {
  submit: "submitted",
  resubmit: "resubmitted",
  approve: "approved",
  send_back: "sent back",
};

const APPROVED = { message: "Approved! 🎓" };

// The comment / file owner table behind each item type.
const RECORD_TABLE: Partial<Record<ItemType, CommentTarget>> = {
  progress_report: "progress_reports",
  publication: "publications",
  thesis_submission: "thesis_submissions",
  coursework_clearance: "coursework_clearances",
  no_dues_clearance: "no_dues_clearances",
};

/** The type-specific record card; the chain, actions and history around it are generic. */
function ItemContent({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  if (item.item_type === "progress_report") return <ReportDetails item={item} onSaved={onSaved} />;
  if (item.item_type === "publication") return <PublicationDetails item={item} onSaved={onSaved} />;
  if (item.item_type === "thesis_submission") return <ThesisDetails item={item} onSaved={onSaved} />;
  if (item.item_type === "coursework_clearance") return <ClearanceDetails item={item} />;
  return null;
}

/** UX Flow 2 step 4: whoever an item was sent back to sees why, pinned above everything else. */
function SentBackReason({ item }: { item: ItemView }) {
  const last = item.history.at(-1);
  if (last?.action !== "send_back") return null;
  return (
    <Card className="sent-back-reason">
      <h2>Sent back to {item.can_resubmit ? "you" : last.to}</h2>
      <p className="prose">{last.comment}</p>
      <p className="muted">{last.actor}, at {last.step}</p>
    </Card>
  );
}

function Actions({ item, run }: { item: ItemView; run: (action: string, body?: object) => Promise<void> }) {
  const [comment, setComment] = useState("");
  const [rating, setRating] = useState<Rating | "">("");
  const [target, setTarget] = useState<string>("initiator");
  const assessed = item.item_type === "progress_report"; // the API refuses a bare approval
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
        <p className="muted">Once submitted, the details are locked while it goes up the chain.</p>
        <Button kind="primary" disabled={busy} onClick={() => go("submit")}>Submit for approval</Button>
      </Card>
    );
  }
  if (item.can_resubmit) {
    return (
      <Card>
        <h2>Ready to resubmit?</h2>
        <p className="muted">Fix what was asked (the reason is pinned above), then resubmit. It starts again from the first step.</p>
        <Button kind="primary" disabled={busy} onClick={() => go("resubmit")}>Resubmit</Button>
      </Card>
    );
  }
  if (item.can_act) {
    const toStep = target === "initiator" ? null : Number(target);
    return (
      <Card className="act">
        <h2>Your decision · {item.waiting_on}</h2>
        {assessed && (
          <Field label="Your assessment of this period">
            <select value={rating} onChange={(e) => setRating(e.target.value as Rating | "")}>
              <option value="">Choose…</option>
              {(Object.keys(RATING_LABELS) as Rating[]).map((r) => <option key={r} value={r}>{RATING_LABELS[r]}</option>)}
            </select>
          </Field>
        )}
        <Field label={assessed ? "Remarks" : "Comment"}
          hint={assessed ? "Required: what went well, what must improve, what to do next. It prints on the report."
            : "Optional when approving; required when sending back."}>
          <textarea value={comment} maxLength={4000} onChange={(e) => setComment(e.target.value)} />
        </Field>
        <div className="row">
          <Button kind="primary" disabled={busy || (assessed && (!rating || !comment.trim()))}
            onClick={() => go("approve", { comment: comment || null, rating: rating || null })}>
            {assessed ? "Approve with this assessment" : "Approve"}
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
  const [celebrate, setCelebrate] = useState<{ message?: string } | null>(null);
  const isOwn = !!item && item.scholar.id === me?.scholar_id;

  // The scholar sees the celebration once, the first time they open their approved item.
  useEffect(() => {
    if (item && isOwn && item.state === "approved" && firstTime(item.id)) setCelebrate(APPROVED);
  }, [item, isOwn]);

  async function run(action: string, body?: object) {
    setActError(null);
    try {
      const next = await api<ItemView>(`/items/${type}/${id}/${action}`, {
        method: "POST",
        body: JSON.stringify(body ?? {}),
      });
      setData(next);
      // Every approve gets a small burst; the final step gets the full one with the owl.
      if (action === "approve") setCelebrate(next.state === "approved" ? APPROVED : {});
      reloadMe(); // queue / notification counts changed
    } catch (e) {
      setActError(errorText(e));
    }
  }

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!item) return null;
  const table = RECORD_TABLE[item.item_type];
  return (
    <>
      {celebrate && <Celebrate message={celebrate.message} onDone={() => setCelebrate(null)} />}
      <PageHeader eyebrow={`${item.label} · ${item.scholar.name}`} title={item.title}
        actions={<>
          <StateBadge state={item.state} waitingOn={item.waiting_on} />
          {item.item_type === "progress_report" && (
            <DownloadButton path={`/reports/${item.id}.pdf`}>Download PDF</DownloadButton>
          )}
        </>} />
      <div className="item-grid">
        <div className="item-main">
          <SentBackReason item={item} />
          <Card>
            <h2>Approval chain</h2>
            <ChainSteps chain={item.chain} />
          </Card>
          <ItemContent item={item} onSaved={setData} />
          {item.item_type === "publication" && (
            <Attachments table="publications" recordId={item.id} canUpload={item.can_edit}
              hint="The paper or acceptance letter, for the Library to check." />
          )}
          {item.item_type === "thesis_submission" && item.state === "approved" && (
            <ThesisEvaluation thesisId={item.id} isOwn={isOwn} />
          )}
          {table && <Comments target={table} recordId={item.id} />}
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
                    {h.rating && <> <span className={`badge ${h.rating === "satisfactory" ? "badge-approved" : "badge-sent_back"}`}>{RATING_LABELS[h.rating]}</span></>}
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
