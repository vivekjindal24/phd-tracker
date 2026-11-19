"use client";

import { useState } from "react";
import { Button, Card, ErrorText } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { openFile, uploadFile } from "@/lib/upload";
import { errorText, useFetch } from "@/lib/useFetch";
import "./attachments.css";

type Copy = { id: string; file_id: string; file_name: string; uploaded_by: string; uploaded_at: string; approved_at: string | null };
type Entry = { heading: string; date: string | null; record: string | null; signed_copy: Copy | null };
type PhdFile = {
  may_upload_copies: boolean;
  may_approve_copies: boolean;
  annexures: { key: string; title: string; entries: Entry[] }[];
};

const day = (at: string) => new Date(at).toLocaleDateString();

/** Signed copies of the PhD file's forms (PRD F17b): the scan of each form signed on paper. The
 *  supervisor, the department admin or the Research Office uploads it; the admin or the Research
 *  Office approves it (their own uploads count at once). An approved copy stands in the PhD file
 *  in place of the generated page. The API decides all of it; this only offers what it allows. */
export function SignedCopiesCard({ scholarId }: { scholarId: string }) {
  const { data, error, reload } = useFetch<PhdFile>(`/internal/scholars/${scholarId}/phd-file`);
  const [busy, setBusy] = useState<string | null>(null);
  const [actError, setActError] = useState<string | null>(null);

  if (error) return null; // the rest of the page says why the scholar cannot be read
  if (!data || !(data.may_upload_copies || data.may_approve_copies)) return null;

  async function act(label: string, run: () => Promise<unknown>) {
    setBusy(label);
    setActError(null);
    try {
      await run();
      await reload();
    } catch (e) {
      setActError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  const upload = (annexure: string, record: string, file: File) =>
    act(`Uploading ${file.name}…`, async () => {
      const { id } = await api<{ id: string }>(`/scholars/${scholarId}/signed-copies`, {
        method: "POST",
        body: JSON.stringify({ annexure, record_id: record }),
      });
      try {
        await uploadFile("signed_copies", id, file);
      } catch (e) {
        await api(`/signed-copies/${id}`, { method: "DELETE" }).catch(() => undefined); // the empty place goes too
        throw e;
      }
    });

  const parts = data.annexures
    .map((a) => ({ ...a, entries: a.entries.filter((e) => e.record) }))
    .filter((a) => a.entries.length > 0);

  return (
    <Card className="attachments">
      <h2>Signed copies of forms</h2>
      <p className="muted">
        Scan each form once it is signed on paper and upload it here, as a PDF or a photo. A supervisor&apos;s upload
        waits for the department admin or the Research Office to approve it; once approved, it goes into the PhD file in
        place of the printed page.
      </p>
      {parts.length === 0 && <p className="muted">Nothing on record yet.</p>}
      {parts.map((a) => (
        <section key={a.key} aria-label={a.title}>
          <h3 style={{ margin: "var(--space-3) 0 var(--space-2)", fontSize: "1rem" }}>{a.title}</h3>
          <ul className="file-list">
            {a.entries.map((e) => {
              const c = e.signed_copy;
              return (
                <li key={e.record}>
                  <span style={{ fontWeight: 600 }}>{e.heading}</span>
                  {c ? (
                    <>
                      <button type="button" className="file-name" onClick={() => act("Opening…", () => openFile(c.file_id))}>
                        {c.file_name}
                      </button>
                      <span className="muted">
                        Uploaded by {c.uploaded_by} on {day(c.uploaded_at)} ·{" "}
                        {c.approved_at ? `approved on ${day(c.approved_at)}` : "waiting for approval"}
                      </span>
                      {data.may_approve_copies && !c.approved_at && (
                        <Button kind="primary" disabled={busy !== null}
                          onClick={() => act("Approving…", () => api(`/signed-copies/${c.id}/approve`, { method: "POST" }))}>
                          Approve
                        </Button>
                      )}
                      {data.may_approve_copies && (
                        <Button kind="ghost" disabled={busy !== null}
                          onClick={() => act("Removing…", () => api(`/signed-copies/${c.id}`, { method: "DELETE" }))}>
                          Remove
                        </Button>
                      )}
                    </>
                  ) : (
                    <span className="muted">No signed copy yet</span>
                  )}
                  {data.may_upload_copies && (
                    <label className="file-add">
                      <span className="btn btn-secondary">{c ? "Upload a new copy" : "Upload signed copy"}</span>
                      <input type="file" accept="application/pdf,image/png,image/jpeg" className="visually-hidden"
                        disabled={busy !== null}
                        onChange={(ev) => {
                          const f = ev.target.files?.[0];
                          ev.target.value = "";
                          if (f) upload(a.key, e.record!, f);
                        }} />
                    </label>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      {busy && <p className="muted" role="status">{busy}</p>}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}
