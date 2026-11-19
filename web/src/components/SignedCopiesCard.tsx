"use client";

import { useState } from "react";
import { Button, Card, ErrorText } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { openFile, uploadFile } from "@/lib/upload";
import { errorText, useFetch } from "@/lib/useFetch";
import "./attachments.css";

type Copy = { id: string; file_id: string; file_name: string; uploaded_by: string; uploaded_at: string; approved_at: string | null };
type Paper = { kind: string; label: string; copy: Copy | null; may_upload: boolean; may_approve: boolean };
type Entry = { heading: string; date: string | null; record: string | null; papers: Paper[] };
type PhdFile = { handles_copies: boolean; annexures: { key: string; title: string; entries: Entry[] }[] };

const day = (at: string) => new Date(at).toLocaleDateString();

/** Signed copies of the PhD file's papers (PRD F17b): each entry's papers signed by hand — a
 *  seminar's notification, report and attendance sheet, the viva's papers, the examiners' letters…
 *  The supervisor, the department admin or the Research Office uploads one; the admin or the
 *  Research Office approves it (their own uploads count at once). The examiners' papers are the
 *  admin's, the Research Office's and the Exam Office's alone. Approved copies follow their entry
 *  in the PhD file. The API decides all of it; this only offers what it allows, paper by paper. */
export function SignedCopiesCard({ scholarId }: { scholarId: string }) {
  const { data, error, reload } = useFetch<PhdFile>(`/internal/scholars/${scholarId}/phd-file`);
  const [busy, setBusy] = useState<string | null>(null);
  const [actError, setActError] = useState<string | null>(null);

  if (error) return null; // the rest of the page says why the scholar cannot be read
  if (!data?.handles_copies) return null;

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

  const upload = (annexure: string, record: string, kind: string, file: File) =>
    act(`Uploading ${file.name}…`, async () => {
      const { id } = await api<{ id: string }>(`/scholars/${scholarId}/signed-copies`, {
        method: "POST",
        body: JSON.stringify({ annexure, record_id: record, kind }),
      });
      try {
        await uploadFile("signed_copies", id, file);
      } catch (e) {
        await api(`/signed-copies/${id}`, { method: "DELETE" }).catch(() => undefined); // the empty place goes too
        throw e;
      }
    });

  const parts = data.annexures
    .map((a) => ({ ...a, entries: a.entries.filter((e) => e.papers.length > 0) }))
    .filter((a) => a.entries.length > 0);

  return (
    <Card className="attachments">
      <h2>Signed papers for the PhD file</h2>
      <p className="muted">
        Scan each paper once it is signed and upload it in its place, as a PDF or a photo. A supervisor&apos;s upload waits
        for the department admin or the Research Office to approve it; once approved, it goes into the PhD file after its
        entry. The examiners&apos; papers are handled by the admin, the Research Office and the Exam Office only.
      </p>
      {parts.length === 0 && <p className="muted">Nothing on record yet.</p>}
      {parts.map((a) => (
        <section key={a.key} aria-label={a.title}>
          <h3 style={{ margin: "var(--space-3) 0 var(--space-2)", fontSize: "1rem" }}>{a.title}</h3>
          <ul className="file-list">
            {a.entries.map((e) => (
              <li key={e.record} style={{ display: "grid", gap: "var(--space-2)" }}>
                <span style={{ fontWeight: 600 }}>{e.heading}</span>
                <ul className="file-list" style={{ paddingLeft: "var(--space-4)" }}>
                  {e.papers.map((p) => {
                    const c = p.copy;
                    return (
                      <li key={p.kind}>
                        <span>{p.label}:</span>
                        {c ? (
                          <>
                            <button type="button" className="file-name" onClick={() => act("Opening…", () => openFile(c.file_id))}>
                              {c.file_name}
                            </button>
                            <span className="muted">
                              Uploaded by {c.uploaded_by} on {day(c.uploaded_at)} ·{" "}
                              {c.approved_at ? `approved on ${day(c.approved_at)}` : "waiting for approval"}
                            </span>
                            {p.may_approve && !c.approved_at && (
                              <Button kind="primary" disabled={busy !== null}
                                onClick={() => act("Approving…", () => api(`/signed-copies/${c.id}/approve`, { method: "POST" }))}>
                                Approve
                              </Button>
                            )}
                            {p.may_approve && (
                              <Button kind="ghost" disabled={busy !== null}
                                onClick={() => act("Removing…", () => api(`/signed-copies/${c.id}`, { method: "DELETE" }))}>
                                Remove
                              </Button>
                            )}
                          </>
                        ) : (
                          <span className="muted">not uploaded</span>
                        )}
                        {p.may_upload && (
                          <label className="file-add">
                            <span className="btn btn-secondary">{c ? "Upload a new copy" : "Upload"}</span>
                            <input type="file" accept="application/pdf,image/png,image/jpeg" className="visually-hidden"
                              aria-label={`Upload ${p.label} for ${e.heading}`} disabled={busy !== null}
                              onChange={(ev) => {
                                const f = ev.target.files?.[0];
                                ev.target.value = "";
                                if (f) upload(a.key, e.record!, p.kind, f);
                              }} />
                          </label>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {busy && <p className="muted" role="status">{busy}</p>}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}
