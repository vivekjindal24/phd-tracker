"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Owl } from "@/components/brand/Owl";
import { StateBadge } from "@/components/items/StateBadge";
import { Button, Card, ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { ItemView, ThesisRow } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

function StartThesis() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const item = await api<ItemView>("/theses", { method: "POST", body: JSON.stringify({ title }) });
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
        <Field label="Thesis title">
          <input required maxLength={500} value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit">Start thesis submission</Button>
      </form>
    </Card>
  );
}

export default function ThesisPage() {
  const { me } = useSession();
  const { data, error } = useFetch<ThesisRow[]>("/theses");
  const mine = me?.scholar_id ? data?.find((t) => t.scholar.id === me.scholar_id) : undefined;
  const others = data?.filter((t) => t.scholar.id !== me?.scholar_id) ?? [];

  return (
    <>
      <PageHeader eyebrow="Documents & thesis" title="Thesis submissions" />
      <ErrorText>{error}</ErrorText>
      {data && me?.scholar_id && (mine ? (
        <Card>
          <h2>Your thesis</h2>
          <p><Link href={`/items/thesis_submission/${mine.id}`}>{mine.title}</Link>{" "}
            <StateBadge state={mine.state} waitingOn={mine.waiting_on} /></p>
        </Card>
      ) : <StartThesis />)}
      {data && (others.length > 0 || !me?.scholar_id) && (
        <Table label="Thesis submissions" head={["Thesis", "Scholar", "State", "Last change"]}
          empty={<div className="empty-state"><Owl pose="empty" size={96} /><h2>No submissions yet</h2></div>}>
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
    </>
  );
}
