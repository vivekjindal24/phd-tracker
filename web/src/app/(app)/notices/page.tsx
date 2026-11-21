"use client";

import { type FormEvent, useState } from "react";
import { Attachments } from "@/components/Attachments";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate, formatDay } from "@/lib/format";
import type { Notice, Ref } from "@/lib/types";
import "./notices.css";
import { errorText, useFetch } from "@/lib/useFetch";

type Where = { university: boolean; units: Ref[] };

/** Post a notice: to the whole university or a department, with an optional end date. */
function PostNotice({ where, onPosted }: { where: Where; onPosted: () => void }) {
  const [unitId, setUnitId] = useState(where.university ? "" : where.units[0]?.id ?? "");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [pinned, setPinned] = useState(false);
  const [endsOn, setEndsOn] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/announcements", {
        method: "POST",
        body: JSON.stringify({ unit_id: unitId || null, title, body, pinned, ends_on: endsOn || null }),
      });
      setTitle("");
      setBody("");
      setPinned(false);
      setEndsOn("");
      onPosted();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Card>
      <h2>Post a notice</h2>
      <form className="stack-form" onSubmit={submit}>
        <Field label="For">
          <select value={unitId} onChange={(e) => setUnitId(e.target.value)}>
            {where.university && <option value="">The whole university</option>}
            {where.units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </select>
        </Field>
        <Field label="Title">
          <input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label="Text" hint="Everyone it is for is told, in the portal and by email.">
          <textarea rows={4} maxLength={5000} value={body} onChange={(e) => setBody(e.target.value)} />
        </Field>
        <div className="row">
          <Field label="Take it down after" hint="Optional. It then moves to past notices.">
            <input type="date" value={endsOn} onChange={(e) => setEndsOn(e.target.value)} />
          </Field>
          <label className="check">
            <input type="checkbox" checked={pinned} onChange={(e) => setPinned(e.target.checked)} />
            Pin to the top
          </label>
        </div>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit">Post notice</Button>
        <p className="muted">Attach a file, such as the fee notice, to the notice once it is posted.</p>
      </form>
    </Card>
  );
}

/** The notice board (owner, 2026-11-22): university-wide and department notices. */
export default function NoticesPage() {
  const [past, setPast] = useState(false);
  const { data, error, reload } = useFetch<Notice[]>(`/announcements?past=${past}`);
  const { data: where } = useFetch<Where>("/announcements/where");
  const [actError, setActError] = useState<string | null>(null);

  async function act(path: string, init: RequestInit) {
    setActError(null);
    try {
      await api(path, init);
      await reload();
    } catch (e) {
      setActError(errorText(e));
    }
  }

  return (
    <>
      <PageHeader eyebrow="Notice board" title="Notices"
        actions={<Button kind="ghost" onClick={() => setPast(!past)}>{past ? "Current notices" : "Past notices"}</Button>} />
      <ErrorText>{error ?? actError}</ErrorText>
      <div className="notices">
        <div className="notices-list">
          {data && data.length === 0 && (
            <Card><p className="muted">{past ? "No past notices." : "No notices right now."}</p></Card>
          )}
          {(data ?? []).map((n) => (
            <Card key={n.id} as="article">
              <h2>{n.pinned && <span className="badge">Pinned</span>} {n.title}</h2>
              <p className="muted">
                {n.unit?.name ?? "Whole university"} · posted {formatDay(n.posted_at)}
                {n.posted_by && ` by ${n.posted_by}`}
                {n.ends_on && ` · until ${formatDate(n.ends_on)}`}
              </p>
              {n.body && <p className="prose">{n.body}</p>}
              <Attachments table="announcements" recordId={n.id} canUpload={n.can_manage} title="Attached" />
              {n.can_manage && (
                <div className="row">
                  <Button kind="ghost" onClick={() => act(`/announcements/${n.id}`, { method: "PATCH", body: JSON.stringify({ pinned: !n.pinned }) })}>
                    {n.pinned ? "Unpin" : "Pin to the top"}
                  </Button>
                  <Button kind="danger" onClick={() => act(`/announcements/${n.id}`, { method: "DELETE" })}>Remove</Button>
                </div>
              )}
            </Card>
          ))}
        </div>
        {where && (where.university || where.units.length > 0) && !past && <PostNotice where={where} onPosted={reload} />}
      </div>
    </>
  );
}
