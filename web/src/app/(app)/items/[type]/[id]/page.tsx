"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Attachments } from "@/components/Attachments";
import { Comments } from "@/components/Comments";
import { DownloadButton } from "@/components/DownloadButton";
import { Celebrate, firstTime } from "@/components/Celebrate";
import { ChainSteps } from "@/components/items/ChainSteps";
import { ClaimDetails } from "@/components/items/ClaimDetails";
import { ClearanceDetails } from "@/components/items/ClearanceDetails";
import { PublicationDetails } from "@/components/items/PublicationDetails";
import { ReportDetails } from "@/components/items/ReportDetails";
import { ThesisDetails } from "@/components/items/ThesisDetails";
import { ThesisEvaluation } from "@/components/items/ThesisEvaluation";
import { VivaArrangementDetails } from "@/components/items/VivaArrangementDetails";
import { StateBadge } from "@/components/items/StateBadge";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api, ApiError } from "@/lib/api";
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
  fellowship_claim: "fellowship_claims",
  viva_arrangement: "viva_arrangements",
};

/** The type-specific record card; the chain, actions and history around it are generic. */
function ItemContent({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  if (item.item_type === "progress_report") return <ReportDetails item={item} onSaved={onSaved} />;
  if (item.item_type === "publication") return <PublicationDetails item={item} onSaved={onSaved} />;
  if (item.item_type === "thesis_submission") return <ThesisDetails item={item} onSaved={onSaved} />;
  if (item.item_type === "coursework_clearance") return <ClearanceDetails item={item} />;
  if (item.item_type === "fellowship_claim") return <ClaimDetails item={item} onSaved={onSaved} />;
  if (item.item_type === "viva_arrangement") return <VivaArrangementDetails item={item} onSaved={onSaved} />;
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

type Run = (action: string, body?: object) => Promise<boolean>;
type Signing = { action: string; body: object; method: "email" | "authenticator" };

/** PRD F17b, while the university requires signing: the decision waits here for a fresh code. */
function SignBox({ sign, itemPath, run, onCancel }: { sign: Signing; itemPath: string; run: Run; onCancel: () => void }) {
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const verb = sign.action === "approve" ? "approve" : "send back";

  async function emailCode() {
    setError(null);
    try {
      await api(`${itemPath}/signing-code`, {
        method: "POST",
        body: JSON.stringify({ action: sign.action === "approve" ? "approve" : "send_back" }),
      });
      setSent(true);
    } catch (e) {
      setError(errorText(e));
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    await run(sign.action, { ...sign.body, code });
    setBusy(false);
  }

  return (
    <Card className="act">
      <h2>Sign to {verb}</h2>
      {sign.method === "email" ? (
        <>
          <p className="muted">We email you a six-digit code for this one action. It works once, for 10 minutes.</p>
          <Button kind="secondary" onClick={emailCode}>{sent ? "Send a new code" : "Email me a code"}</Button>
          {sent && <p role="status">The code is on its way to your email.</p>}
        </>
      ) : (
        <p className="muted">Type the six-digit code your authenticator app shows for Anveshan now.</p>
      )}
      <form className="act" onSubmit={submit}>
        <Field label="Code">
          <input inputMode="numeric" autoComplete="one-time-code" required pattern="[0-9]{6}" maxLength={6}
            autoFocus value={code} onChange={(e) => setCode(e.target.value.trim())} />
        </Field>
        <ErrorText>{error}</ErrorText>
        <div className="row">
          <Button kind="primary" type="submit" disabled={busy}>{busy ? "Signing…" : `Sign and ${verb}`}</Button>
          <Button kind="ghost" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

function Actions({ item, run }: { item: ItemView; run: Run }) {
  const [comment, setComment] = useState("");
  const [rating, setRating] = useState<Rating | "">("");
  const [target, setTarget] = useState<string>("initiator");
  const [sign, setSign] = useState(false); // while signing is optional (PRD F17b)
  const assessed = item.item_type === "progress_report"; // the API refuses a bare approval
  const [busy, setBusy] = useState(false);

  async function go(action: string, body?: object) {
    setBusy(true);
    try {
      if (await run(action, body)) setComment("");
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
        {item.signing === "required" && (
          <p className="muted">Your university requires your signature: you will be asked for a code.</p>
        )}
        {item.signing === "optional" && (
          <label className="check">
            <input type="checkbox" checked={sign} onChange={(e) => setSign(e.target.checked)} />
            Sign this with my signature (you will be asked for a code)
          </label>
        )}
        {item.signing === "off" && (
          <p className="muted">To sign your decisions, add your signature under My account; your department&apos;s admin confirms it.</p>
        )}
        <div className="row">
          <Button kind="primary" disabled={busy || (assessed && (!rating || !comment.trim()))}
            onClick={() => go("approve", { comment: comment || null, rating: rating || null, sign })}>
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
            onClick={() => go("send-back", { comment, to_step: toStep, sign })}>
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
  const [sign, setSign] = useState<Signing | null>(null);
  const isOwn = !!item && item.scholar.id === me?.scholar_id;

  // The scholar sees the celebration once, the first time they open their approved item.
  useEffect(() => {
    if (item && isOwn && item.state === "approved" && firstTime(item.id)) setCelebrate(APPROVED);
  }, [item, isOwn]);

  async function run(action: string, body?: object): Promise<boolean> {
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
      setSign(null);
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.code === "signing_code_required") {
        setSign({ action, body: body ?? {}, method: e.details.method === "authenticator" ? "authenticator" : "email" });
      } else {
        setActError(errorText(e));
      }
      return false;
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
            <DownloadButton path={`/reports/${item.id}.pdf`} signable>Download PDF</DownloadButton>
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
          {sign && <SignBox sign={sign} itemPath={`/items/${type}/${id}`} run={run} onCancel={() => setSign(null)} />}
          <Actions item={item} run={run} />
          <Card>
            <h2>History</h2>
            {item.history.length === 0 ? (
              <p className="muted">Not submitted yet.</p>
            ) : (
              <ol className="history">
                {item.history.map((h, i) => (
                  <li key={i}>
                    <strong>{h.actor}</strong>{h.on_behalf_of && <> (on behalf of {h.on_behalf_of})</>} {ACTION_TEXT[h.action] ?? h.action}
                    {h.step && h.action !== "submit" && ` at ${h.step}`}
                    {h.to && ` → ${h.to}`}
                    <time dateTime={h.at}>{new Date(h.at).toLocaleString()}</time>
                    {h.rating && <> <span className={`badge ${h.rating === "satisfactory" ? "badge-approved" : "badge-sent_back"}`}>{RATING_LABELS[h.rating]}</span></>}
                    {h.comment && <blockquote>{h.comment}</blockquote>}
                    {h.signature && <img className="history-signature" src={h.signature} alt={`Signature of ${h.actor}`} />}
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
