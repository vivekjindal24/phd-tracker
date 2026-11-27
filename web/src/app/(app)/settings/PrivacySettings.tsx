"use client";

import { useEffect, useState } from "react";
import { PersonPicker } from "@/components/PersonPicker";
import { Button, Card, Field } from "@/components/ui/kit";
import type { PrivacyNotice, SettingsData } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import type { Save } from "./save";

type Person = { id: string; full_name: string; email: string };
const MAX_NOTICE = 20000;

/** The privacy notice everyone reads (again, once it changes) and who answers data requests
 *  (DPDP Act 2023). Anveshan's draft stands until the University saves its own. */
export function PrivacySettings({ data, save }: { data: SettingsData; save: Save }) {
  const notice = useFetch<PrivacyNotice>("/privacy");
  const [text, setText] = useState("");
  const [person, setPerson] = useState<Person | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (notice.data) setText(notice.data.text);
  }, [notice.data]);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    try {
      await work();
      await notice.reload();
    } catch {
      // the page shows the error
    } finally {
      setBusy(false);
    }
  }

  const current = notice.data;
  const changed = current !== null && text !== current.text;
  return (
    <Card className="settings-privacy">
      <h2>Privacy notice</h2>
      <p className="muted">
        {data.privacy_notice
          ? "Your University's own notice. Saving a change shows it again to everyone at their next visit."
          : "Anveshan's draft, filled in with your University's name. Have your lawyer check it, then save your own."}
      </p>
      <Field label="Notice" hint="Plain text; a blank line starts a new paragraph. The contact and the outside services are added below it.">
        <textarea rows={14} maxLength={MAX_NOTICE} value={text} disabled={!current} onChange={(e) => setText(e.target.value)} />
      </Field>
      <div className="row">
        <Button kind="primary" disabled={busy || !changed || !text.trim()}
          onClick={() => run(() => save("/settings", "PATCH", { privacy_notice: text }))}>Save notice</Button>
        {data.privacy_notice && (
          <Button kind="ghost" disabled={busy}
            onClick={() => run(() => save("/settings", "PATCH", { privacy_notice: "" }))}>Go back to Anveshan&apos;s draft</Button>
        )}
      </div>
      <h3>Privacy officer</h3>
      <p>
        {current?.officer
          ? <>Now: <strong>{current.officer.name}</strong> ({current.officer.email}). They answer data requests and are named in the notice.</>
          : "None named: the University's root admins answer data requests."}
      </p>
      <PersonPicker<Person> label="Name someone else" path="/users" value={person} onPick={setPerson} detail={(p) => p.email} />
      <div className="row">
        <Button disabled={busy || !person}
          onClick={() => run(async () => { await save("/settings/privacy-officer", "PUT", { user_id: person?.id }); setPerson(null); })}>
          Name as privacy officer
        </Button>
        {data.privacy_officer_id && (
          <Button kind="ghost" disabled={busy}
            onClick={() => run(() => save("/settings/privacy-officer", "PUT", { user_id: null }))}>Leave it to the root admins</Button>
        )}
      </div>
    </Card>
  );
}
