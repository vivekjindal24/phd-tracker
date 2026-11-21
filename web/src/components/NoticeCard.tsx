"use client";

import { useEffect, useState } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { errorText, useFetch } from "@/lib/useFetch";

type Wording = { announcement: string; closing: string; copy_to: string[] };
type Notice = {
  can_edit: boolean;
  choices: { key: string; label: string }[];
  signers: string[];
  department_signers: string[];
  custom: Partial<Wording> & { signers?: string[] };
  standard: Wording;
  holders: Record<string, { id: string; name: string }[]>; // who holds each role, today
  names: Record<string, string | null>; // who signs in each role, as things stand
  unnamed: string[]; // signers several people could be, nobody chosen: printed with the role alone
  can_set_controller: boolean; // the Exam Office and the root admin choose the Controller here
};
type Draft = { signers: string[]; names: Record<string, string>; announcement: string; closing: string; copyTo: string };

/** The roles several people hold, where whoever signs is chosen per department or notice. The
 *  Controller of Examinations is chosen once for the whole university instead (Settings). */
const contested = (n: Notice) => Object.keys(n.holders)
  .filter((k) => k !== "exam_office" && n.holders[k]!.length > 1);
const draftOf = (n: Notice): Draft => ({
  signers: n.signers,
  names: Object.fromEntries(contested(n).filter((k) => n.names[k]).map((k) => [k, n.names[k]!])),
  announcement: n.custom.announcement ?? "",
  closing: n.custom.closing ?? "",
  copyTo: (n.custom.copy_to ?? []).join("\n"),
});
const same = (a: string[], b: string[]) => a.length === b.length && a.every((x) => b.includes(x));

/** PRD F17b: who signs a seminar's or viva's notice and what it says. The department admin changes
 *  it for this one, or sets the signers for every one of the department; others only read it.
 *  `base`: the seminar's or viva arrangement's API path; `what`: "seminar" or "viva". */
export function NoticeCard({ base, what, department }: { base: string; what: string; department: string }) {
  const { data: n, error, setData, reload } = useFetch<Notice>(`${base}/notice`);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  useEffect(() => { if (n) setDraft(draftOf(n)); }, [n]);
  if (error) return <Card><ErrorText>{error}</ErrorText></Card>;
  if (!n || !draft) return null;

  const label = (key: string) => n.choices.find((c) => c.key === key)?.label ?? key;
  async function put(path: string, body: unknown) {
    setSaveError(null);
    try {
      setData(await api<Notice>(`${base}/notice${path}`, { method: "PUT", body: JSON.stringify(body) }));
    } catch (e) {
      setSaveError(errorText(e));
    }
  }

  async function setController(userId: string) {
    setSaveError(null);
    try {
      await api("/settings/exam-controller", { method: "PUT", body: JSON.stringify({ user_id: userId || null }) });
      await reload();
    } catch (e) {
      setSaveError(errorText(e));
    }
  }
  const office = n.holders.exam_office ?? [];
  const unnamed = n.unnamed.filter((k) => k !== "exam_office"); // the Controller line says its own
  const controller = n.signers.includes("exam_office") && office.length > 1 && (
    n.can_set_controller ? (
      <Field label="Who signs as Controller of Examinations" hint="For every notice of the university; only the Exam Office or the root admin changes it.">
        <select value={n.names.exam_office ?? ""} onChange={(e) => setController(e.target.value)}>
          <option value="">Choose… (left unchosen, the line prints without a name)</option>
          {office.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </Field>
    ) : (
      <p className="muted">
        Controller of Examinations: {office.find((p) => p.id === n.names.exam_office)?.name
          ?? "not chosen yet. The Exam Office or the root admin chooses it for the whole university"}.
      </p>
    )
  );

  if (!n.can_edit) {
    return (
      <Card>
        <h2>Notice</h2>
        <p className="muted">Signed by: {n.signers.map(label).join(", ")}. The department admin can change this.</p>
        {controller}
        <ErrorText>{saveError}</ErrorText>
      </Card>
    );
  }

  const copyTo = draft.copyTo.split("\n").map((l) => l.trim()).filter(Boolean);
  const toName = contested(n).filter((k) => draft.signers.includes(k));
  const names = Object.fromEntries(toName.filter((k) => draft.names[k]).map((k) => [k, draft.names[k]]));
  const namesChanged = JSON.stringify(draft.names) !== JSON.stringify(draftOf(n).names);
  const changed = Object.keys(n.custom).length > 0;
  const dirty = JSON.stringify(draft) !== JSON.stringify(draftOf(n));
  const toggle = (key: string) => setDraft({
    ...draft,
    signers: draft.signers.includes(key) ? draft.signers.filter((k) => k !== key) : [...draft.signers, key],
  });

  return (
    <Card>
      <h2>Notice</h2>
      <p className="muted">
        {changed ? `Changed for this ${what}.` : `As every ${what} notice of ${department}.`} Printed with lines to sign by hand.
      </p>
      <div className="stack-form">
        <fieldset className="check-row">
          <legend>Signed by</legend>
          {n.choices.map((c) => (
            <label key={c.key} className="check">
              <input type="checkbox" checked={draft.signers.includes(c.key)} onChange={() => toggle(c.key)} />
              {c.label}
            </label>
          ))}
        </fieldset>
        {toName.map((k) => (
          <Field key={k} label={`Who signs as ${label(k)}`} hint={`${n.holders[k]!.length} people hold this role.`}>
            <select value={draft.names[k] ?? ""} onChange={(e) => setDraft({ ...draft, names: { ...draft.names, [k]: e.target.value } })}>
              <option value="">Choose… (left unchosen, the line prints without a name)</option>
              {n.holders[k]!.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </Field>
        ))}
        {controller}
        {unnamed.length > 0 && (
          <p className="field-hint" role="status">
            Several people are {unnamed.map(label).join(" and ")}: choose who signs, or the line prints with the role alone.
          </p>
        )}
        <Field label="Announcement" hint={`Left empty, it is written from the ${what}'s date, time and venue.`}>
          <textarea rows={4} maxLength={2000} placeholder={n.standard.announcement} value={draft.announcement}
            onChange={(e) => setDraft({ ...draft, announcement: e.target.value })} />
        </Field>
        <Field label="Closing line">
          <input maxLength={500} placeholder={n.standard.closing} value={draft.closing}
            onChange={(e) => setDraft({ ...draft, closing: e.target.value })} />
        </Field>
        <Field label="Copy to" hint="One per line. Left empty, the standard list is used.">
          <textarea rows={4} placeholder={n.standard.copy_to.join("\n")} value={draft.copyTo}
            onChange={(e) => setDraft({ ...draft, copyTo: e.target.value })} />
        </Field>
        <ErrorText>{saveError}</ErrorText>
        <div className="row">
          <Button kind="primary" disabled={!dirty || draft.signers.length === 0} onClick={() => put("", {
            signers: same(draft.signers, n.department_signers) ? null : draft.signers,
            announcement: draft.announcement.trim() || null,
            closing: draft.closing.trim() || null,
            copy_to: copyTo.length ? copyTo : null,
            names: Object.keys(names).length ? names : null,
          })}>Save for this {what}</Button>
          <Button disabled={draft.signers.length === 0 || (same(draft.signers, n.department_signers) && !namesChanged)}
            onClick={() => put("/department", { signers: draft.signers, names })}>
            Use these signers for every {what} of {department}
          </Button>
          {changed && <Button kind="ghost" onClick={() => put("", {})}>Back to the standard notice</Button>}
          {dirty && <Button kind="ghost" onClick={() => setDraft(draftOf(n))}>Undo</Button>}
        </div>
      </div>
    </Card>
  );
}
