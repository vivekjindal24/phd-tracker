"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Owl } from "@/components/brand/Owl";
import { listPath, useScholarFilter } from "@/components/ScholarFilter";
import { StateBadge } from "@/components/items/StateBadge";
import { Button, Card, ErrorText, PageHeader, Table } from "@/components/ui/kit";
import { ListFoot } from "@/components/ListFoot";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { ItemView, NoDuesMine, ThesisRow } from "@/lib/types";
import { errorText, useFetch, usePagedFetch } from "@/lib/useFetch";

function StartThesis() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const item = await api<ItemView>("/theses", { method: "POST" });
      router.push(`/items/thesis_submission/${item.id}`);
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Card className="empty-state">
      <Owl pose="reading" size={110} />
      <h2>Ready to submit your thesis?</h2>
      <p>Start a submission, upload the final thesis, then send it up the chain: supervisor → department → Library (plagiarism check) → Exam Office → Research Office.</p>
      <form className="stack-form" onSubmit={submit}>
        <p className="muted">Your thesis title comes from your RDC approval, so there is nothing to type.</p>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit">Start thesis submission</Button>
      </form>
    </Card>
  );
}

/** The scholar's no-dues clearance: required before the thesis only when the university says so. */
function NoDues() {
  const router = useRouter();
  const { data, error } = useFetch<NoDuesMine>("/no-dues/mine");
  const [startError, setStartError] = useState<string | null>(null);

  async function start() {
    setStartError(null);
    try {
      const item = await api<ItemView>("/no-dues", { method: "POST" });
      router.push(`/items/no_dues_clearance/${item.id}`);
    } catch (err) {
      setStartError(errorText(err));
    }
  }

  if (!data) return <ErrorText>{error}</ErrorText>;
  if (!data.required && !data.item) return null;
  return (
    <Card>
      <h2>No-dues clearance</h2>
      {data.item ? (
        <p><Link href={`/items/no_dues_clearance/${data.item.id}`}>Your clearance</Link>{" "}
          <StateBadge state={data.item.state} waitingOn={data.item.waiting_on} /></p>
      ) : (
        <>
          <p>Your thesis can be submitted once your supervisor (lab), department, Library and Research Office (fees) confirm you owe nothing.</p>
          <Button kind="secondary" onClick={start}>Request no-dues clearance</Button>
        </>
      )}
      <ErrorText>{startError}</ErrorText>
    </Card>
  );
}

export default function ThesisPage() {
  const { me } = useSession();
  const filter = useScholarFilter();
  const [sort, setSort] = useState("");
  const { data, error, hasMore, more, total, exportPath } = usePagedFetch<ThesisRow>(listPath("/theses", filter.params, { sort }), 200);
  const mine = me?.scholar_id ? data?.find((t) => t.scholar.id === me.scholar_id) : undefined;
  const others = data?.filter((t) => t.scholar.id !== me?.scholar_id) ?? [];

  return (
    <>
      <PageHeader eyebrow="Documents & thesis" title="Thesis submissions" />
      {/* Not for a scholar: filtering would hide their own thesis card above the list. */}
      {!me?.scholar_id && filter.fields && <div className="toolbar">{filter.fields}</div>}
      <ErrorText>{error}</ErrorText>
      {me?.scholar_id && <NoDues />}
      {data && me?.scholar_id && (mine ? (
        <Card>
          <h2>Your thesis</h2>
          <p><Link href={`/items/thesis_submission/${mine.id}`}>{mine.title}</Link>{" "}
            <StateBadge state={mine.state} waitingOn={mine.waiting_on} /></p>
        </Card>
      ) : <StartThesis />)}
      {data && (others.length > 0 || !me?.scholar_id) && (
        <Table label="Thesis submissions" head={["Thesis", "Scholar", "State", "Last change"]}
          sort={{ by: sort, keys: ["title", "scholar", "state", "updated"], onChange: setSort }}
          empty={<div className="empty-state"><Owl pose="empty" size={96} /><h2>{filter.active ? "No submissions match" : "No submissions yet"}</h2></div>}>
          {others.map((t) => (
            <tr key={t.id}>
              <td><Link href={`/items/thesis_submission/${t.id}`}>{t.title}</Link></td>
              <td>{t.scholar.name}</td>
              <td><StateBadge state={t.state} waitingOn={t.waiting_on} /></td>
              <td className="mono">{new Date(t.updated_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </Table>
      )}
      <ListFoot hasMore={hasMore} more={more} shown={data?.length} total={total} exportPath={exportPath} />
    </>
  );
}
