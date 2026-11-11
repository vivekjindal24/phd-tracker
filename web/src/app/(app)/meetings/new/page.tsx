"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { PersonPicker } from "@/components/PersonPicker";
import { ShareChecks } from "@/components/meetings/ShareChecks";
import { Button, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Meeting, MeetingShare, Scholar } from "@/lib/types";
import { errorText } from "@/lib/useFetch";
import "../meetings.css";

const today = () => new Date().toISOString().slice(0, 10);

export default function NewMeetingPage() {
  const { me } = useSession();
  const router = useRouter();
  const [chosen, setChosen] = useState<Scholar | null>(null);
  const [date, setDate] = useState(today());
  const [agenda, setAgenda] = useState("");
  const [minutes, setMinutes] = useState("");
  const [actions, setActions] = useState("");
  const [next, setNext] = useState("");
  const [share, setShare] = useState<MeetingShare[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isMainSupervisor = Boolean(chosen && me?.faculty_id && chosen.supervisor?.id === me.faculty_id);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const m = await api<Meeting>("/meetings", {
        method: "POST",
        body: JSON.stringify({
          scholar_id: chosen?.id, meeting_date: date, agenda, minutes, action_items: actions,
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
        {/* mine: the caller's own record and the scholars they supervise, the only parties to a meeting. */}
        <PersonPicker label="Scholar" path="/scholars?mine=true" value={chosen} onPick={setChosen}
          detail={(s) => s.roll_number} />
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
        <Button kind="primary" type="submit" disabled={busy || !chosen}>
          {busy ? "Saving…" : "Save meeting"}
        </Button>
      </form>
    </>
  );
}
