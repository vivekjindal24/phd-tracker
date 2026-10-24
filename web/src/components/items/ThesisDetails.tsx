"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Attachments } from "@/components/Attachments";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import type { ItemView, ThesisContent } from "@/lib/types";
import { errorText } from "@/lib/useFetch";

/** UGC (Promotion of Academic Integrity) Regulations 2018: up to 10% similarity is Level 0. */
const UGC_LEVEL0_MAX = 10;

function StepForm({
  title,
  hint,
  children,
  onSave,
}: {
  title: string;
  hint: string;
  children: React.ReactNode;
  onSave: () => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      await onSave();
      setSaved(true);
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <form className="verify" onSubmit={submit}>
      <h3>{title}</h3>
      <p className="muted">{hint}</p>
      {children}
      <ErrorText>{error}</ErrorText>
      {saved && <p className="muted" role="status">Saved — you can approve now.</p>}
      <Button kind="secondary" type="submit">Save</Button>
    </form>
  );
}

function TitleEdit({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  const c = item.content as ThesisContent;
  const [title, setTitle] = useState(c.title);
  return (
    <StepForm title="Thesis title" hint="Upload the final thesis below, then submit." onSave={async () => {
      onSaved(await api<ItemView>(`/theses/${item.id}`, { method: "PATCH", body: JSON.stringify({ title }) }));
    }}>
      <Field label="Title">
        <input required maxLength={500} value={title} onChange={(e) => setTitle(e.target.value)} />
      </Field>
    </StepForm>
  );
}

function Plagiarism({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  const c = item.content as ThesisContent;
  const [tool, setTool] = useState(c.plagiarism_tool ?? "");
  const [score, setScore] = useState(c.plagiarism_score === null ? "" : String(c.plagiarism_score));
  return (
    <StepForm title="Plagiarism check" hint="Record the tool and similarity score, and attach the certificate below."
      onSave={async () => {
        onSaved(await api<ItemView>(`/theses/${item.id}/plagiarism`, {
          method: "PUT",
          body: JSON.stringify({ plagiarism_tool: tool, plagiarism_score: Number(score) }),
        }));
      }}>
      <div className="row">
        <Field label="Tool"><input required maxLength={100} value={tool} placeholder="Turnitin, Ouriginal, DrillBit…"
          onChange={(e) => setTool(e.target.value)} /></Field>
        <Field label="Similarity %"><input required type="number" min={0} max={100} step={0.01} value={score}
          onChange={(e) => setScore(e.target.value)} /></Field>
      </div>
    </StepForm>
  );
}

function Examiners({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  const c = item.content as ThesisContent;
  const [names, setNames] = useState(c.examiners ?? "");
  return (
    <StepForm title="Examiners" hint="Confidential: only the Exam Office, Research Office and university admin see these names until the viva."
      onSave={async () => {
        onSaved(await api<ItemView>(`/theses/${item.id}/examiners`, { method: "PUT", body: JSON.stringify({ examiners: names }) }));
      }}>
      <Field label="Names and institutions" hint="One per line.">
        <textarea required maxLength={2000} value={names} onChange={(e) => setNames(e.target.value)} />
      </Field>
    </StepForm>
  );
}

export function ThesisDetails({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  const c = item.content as ThesisContent;
  const atLibrary = item.can_act && item.waiting_on === "Library";
  const atExam = item.can_act && item.waiting_on === "Exam Office";
  const over = c.plagiarism_score !== null && c.plagiarism_score > UGC_LEVEL0_MAX;
  return (
    <>
      <Card>
        <h2>Thesis</h2>
        <dl className="kv">
          <dt>Plagiarism check</dt>
          <dd>
            {c.plagiarism_score === null ? <span className="muted">Not done yet</span> : (
              <>
                {c.plagiarism_score}% · {c.plagiarism_tool}{" "}
                <span className={`badge ${over ? "badge-sent_back" : "badge-approved"}`}>
                  {over ? `Above ${UGC_LEVEL0_MAX}%` : "Within UGC Level 0"}
                </span>
              </>
            )}
          </dd>
          <dt>Examiners</dt>
          <dd>
            {c.examiners ?? <span className="muted">{c.examiners_entered ? "Confidential" : "Not entered yet"}</span>}
          </dd>
        </dl>
        {item.can_edit && <TitleEdit item={item} onSaved={onSaved} />}
        {atLibrary && <Plagiarism item={item} onSaved={onSaved} />}
        {atExam && <Examiners item={item} onSaved={onSaved} />}
      </Card>
      <Attachments table="thesis_submissions" recordId={item.id} canUpload={item.can_edit || atLibrary}
        removeOwnOnly title="Thesis files" hint="The final thesis (and, from the Library, the plagiarism-check certificate)." />
    </>
  );
}
