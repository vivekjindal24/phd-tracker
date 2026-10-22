"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ShareChecks } from "@/components/meetings/ShareChecks";
import { Button, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Meeting, MeetingShare, Scholar } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "../meetings.css";

const today = () => new Date().toISOString().slice(0, 10);

export default function NewMeetingPage() {
  const { me } = useSession();
  const router = useRouter();
  // The caller's own scoped scholar list (a scholar gets just themselves).
  const { data: scholars } = useFetch<Scholar[]>("/scholars?limit=500");
  const mine = (scholars ?? []).filter(
    (s) => s.user_id === me?.id || s.supervisor?.id === me?.faculty_id || s.co_supervisor?.id === me?.faculty_id,
  );
  const [scholarId, setScholarId] = useState("");
  const [date, setDate] = useState(today());
  const [agenda, setAgenda] = useState("");
  const [minutes, setMinutes] = useState("");
  const [actions, setActions] = useState("");
  const [next, setNext] = useState("");
  const [share, setShare] = useState<MeetingShare[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!scholarId && mine.length === 1 && mine[0]) setScholarId(mine[0].id);
  }, [mine, scholarId]);

  const chosen = mine.find((s) => s.id === scholarId);
  const isMainSupervisor = Boolean(chosen && me?.faculty_id && chosen.supervisor?.id === me.faculty_id);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const m = await api<Meeting>("/meetings", {
        method: "POST",
        body: JSON.stringify({
          scholar_id: scholarId, meeting_date: date, agenda, minutes, action_items: actions,
          next_meeting_date: next || null, shared_with: isMainSupervisor ? share : [],
        }),
      });
      router.push(`/meetings/${m.id}`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow="Supervision trail" title="Log a meeting" />
      <form className="clay card meeting-form" onSubmit={submit}>
        <Field label="Scholar">
          <select required value={scholarId} onChange={(e) => setScholarId(e.target.value)}>
            <option value="" disabled>Choose…</option>
            {mine.map((s) => (
              <option key={s.id} value={s.id}>{s.full_name} ({s.roll_number})</option>
            ))}
          </select>
        </Field>
        <div className="two">
          <Field label="Meeting date" hint="Backdating is fine; the record shows when it was logged.">
            <input type="date" required max={today()} value={date} onChange={(e) => setDate(e.target.value)} />
          </Field>
          <Field label="Next meeting (optional)">
            <input type="date" min={date} value={next} onChange={(e) => setNext(e.target.value)} />
          </Field>
        </div>
        <Field label="Agenda">
          <input required maxLength={2000} value={agenda} onChange={(e) => setAgenda(e.target.value)}
            placeholder="e.g. Chapter 3 draft review" />
        </Field>
        <Field label="Minutes">
          <textarea maxLength={20000} value={minutes} onChange={(e) => setMinutes(e.target.value)} />
        </Field>
        <Field label="Action items">
          <textarea maxLength={20000} value={actions} onChange={(e) => setActions(e.target.value)} />
        </Field>
        {isMainSupervisor && <ShareChecks value={share} onChange={setShare} />}
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit" disabled={busy || !scholarId}>
          {busy ? "Saving…" : "Save meeting"}
        </Button>
      </form>
    </>
  );
}
