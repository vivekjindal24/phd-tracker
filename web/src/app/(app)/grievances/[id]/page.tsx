"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Attachments } from "@/components/Attachments";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate, formatStamp } from "@/lib/format";
import { GRIEVANCE_CATEGORY_LABELS, GRIEVANCE_STATUS_LABELS } from "@/lib/types";
import type { Grievance } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "../grievances.css";

type Act = (path: string, body?: Record<string, string>) => Promise<void>;

/** One written step (the decision, the appeal, the appeal's decision), sent with its text. */
function WriteStep({ label, hint, button, field, path, act }: {
  label: string; hint: string; button: string; field: string; path: string; act: Act;
}) {
  const [text, setText] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    act(path, { [field]: text });
  }
  return (
    <form className="stack-form" onSubmit={submit}>
      <Field label={label} hint={hint}>
        <textarea required maxLength={5000} rows={5} value={text} onChange={(e) => setText(e.target.value)} />
      </Field>
      <Button kind="primary" type="submit">{button}</Button>
    </form>
  );
}

function Step({ title, when, by, text }: { title: string; when: string | null; by?: string | null; text: string | null }) {
  if (!text) return null;
  return (
    <section className="grievance-step">
      <h3>{title}</h3>
      <p className="muted">{when && formatStamp(when)}{by && ` · ${by}`}</p>
      <p className="grievance-text">{text}</p>
    </section>
  );
}

export default function GrievanceDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: g, error, setData } = useFetch<Grievance>(`/grievances/${id}`);
  const [actError, setActError] = useState<string | null>(null);

  const act: Act = async (path, body) => {
    setActError(null);
    try {
      setData(await api<Grievance>(`/grievances/${id}/${path}`, { method: "POST", body: JSON.stringify(body ?? {}) }));
    } catch (e) {
      setActError(errorText(e));
    }
  };

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!g) return null;
  const deadline = g.due_on && `Due ${formatDate(g.due_on)}`;
  return (
    <>
      <PageHeader eyebrow={`Grievance · ${g.scholar.name} · ${GRIEVANCE_CATEGORY_LABELS[g.category]}`} title={g.subject} />
      <Card>
        <p>
          <span className={`badge grievance-${g.status}`}>{GRIEVANCE_STATUS_LABELS[g.status]}</span>{" "}
          <span className="muted">Filed {formatStamp(g.filed_at)}{deadline && ` · ${deadline}`}</span>
        </p>
        <section className="grievance-step">
          <h3>The grievance</h3>
          <p className="grievance-text">{g.description}</p>
        </section>
        <Step title="Decision of the grievance cell" when={g.decided_at} by={g.decided_by} text={g.decision} />
        <Step title="Appeal" when={g.appealed_at} text={g.appeal_reason} />
        <Step title={`Decision on the appeal`} when={g.appeal_decided_at} by={g.appeal_decided_by} text={g.appeal_decision} />
        <ErrorText>{actError}</ErrorText>
        {g.can.decide && (
          <section className="grievance-step">
            <WriteStep label="Decision of the grievance cell" button="Record the decision" field="text" path="decide" act={act}
              hint="With its reasons. The scholar is told and may accept it or appeal within 15 days." />
          </section>
        )}
        {g.can.decide_appeal && (
          <section className="grievance-step">
            <WriteStep label="Decision on the appeal" button="Record the decision on the appeal" field="text" path="appeal-decision" act={act}
              hint="With its reasons. This closes the grievance." />
          </section>
        )}
        {(g.can.accept || g.can.appeal) && (
          <section className="grievance-step">
            <h3>Do you accept the decision?</h3>
            {g.appeal_closes_on && <p className="muted">You may appeal to {g.appeals_to} until {formatDate(g.appeal_closes_on)}.</p>}
            <div className="stack-form">
              {g.can.accept && <div><Button kind="secondary" onClick={() => act("accept")}>Accept and close</Button></div>}
              {g.can.appeal && (
                <WriteStep label={`Appeal to ${g.appeals_to}`} button="Appeal" field="reason" path="appeal" act={act}
                  hint="Why the decision does not resolve your grievance." />
              )}
            </div>
          </section>
        )}
        {g.can.withdraw && (
          <section className="grievance-step">
            <Button kind="ghost" onClick={() => act("withdraw")}>Withdraw this grievance</Button>
          </section>
        )}
      </Card>
      <Attachments table="grievances" recordId={g.id} canUpload={g.can.attach} removeOwnOnly
        title="Papers" hint="Evidence from the scholar; orders from the cell or on the appeal." />
    </>
  );
}
