"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Owl } from "@/components/brand/Owl";
import { Ledger } from "@/components/Ledger";
import { ScholarSearch } from "@/components/ScholarSearch";
import { Button, Card, ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import { useSession } from "@/lib/session";
import { SCHEME_LABELS } from "@/lib/types";
import type { Fellowship, FellowshipScheme, FellowshipStatus, Scholar } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

const SCHEMES = Object.keys(SCHEME_LABELS) as FellowshipScheme[];
const STATUS_LABELS: Record<FellowshipStatus, string> = { active: "Active", completed: "Completed", terminated: "Terminated" };

function RecordFellowship({ onAdded }: { onAdded: () => void }) {
  const [scholar, setScholar] = useState<Scholar | null>(null);
  const [v, setV] = useState({ scheme: "ugc_jrf" as FellowshipScheme, amount_monthly: "", hra_amount: "0", start_date: "", end_date: "" });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof v, value: string) => setV((p) => ({ ...p, [k]: value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!scholar) return;
    setError(null);
    try {
      await api("/fellowships", {
        method: "POST",
        body: JSON.stringify({ ...v, scholar_id: scholar.id, amount_monthly: Number(v.amount_monthly), hra_amount: Number(v.hra_amount) }),
      });
      setScholar(null);
      onAdded();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Card>
      <h2>Record a fellowship</h2>
      {scholar ? (
        <form className="stack-form" onSubmit={submit}>
          <p>For <strong>{scholar.full_name}</strong> · {scholar.roll_number} <Button kind="ghost" onClick={() => setScholar(null)}>Change</Button></p>
          <div className="row">
            <Field label="Scheme">
              <select value={v.scheme} onChange={(e) => set("scheme", e.target.value)}>
                {SCHEMES.map((s) => <option key={s} value={s}>{SCHEME_LABELS[s]}</option>)}
              </select>
            </Field>
            <Field label="Monthly amount (₹)"><input type="number" required min={0} step={1} value={v.amount_monthly} onChange={(e) => set("amount_monthly", e.target.value)} /></Field>
            <Field label="HRA per month (₹)"><input type="number" required min={0} step={1} value={v.hra_amount} onChange={(e) => set("hra_amount", e.target.value)} /></Field>
          </div>
          <div className="row">
            <Field label="Starts"><input type="date" required value={v.start_date} onChange={(e) => set("start_date", e.target.value)} /></Field>
            <Field label="Ends"><input type="date" required value={v.end_date} onChange={(e) => set("end_date", e.target.value)} /></Field>
          </div>
          <ErrorText>{error}</ErrorText>
          <Button kind="primary" type="submit">Save fellowship</Button>
        </form>
      ) : (
        <ScholarSearch label="Scholar" onPick={setScholar} />
      )}
    </Card>
  );
}

function Manage({ f, onSaved }: { f: Fellowship; onSaved: () => void }) {
  const [upgradeOn, setUpgradeOn] = useState(f.srf_upgrade_on ?? "");
  const [amount, setAmount] = useState(String(f.amount_monthly));
  const [endDate, setEndDate] = useState(f.end_date);
  const [error, setError] = useState<string | null>(null);

  async function save(body: Record<string, unknown>) {
    setError(null);
    try {
      await api(`/fellowships/${f.id}`, { method: "PATCH", body: JSON.stringify(body) });
      onSaved();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <div className="stack-form">
      {f.scheme === "ugc_jrf" && (
        <form className="row" onSubmit={(e) => { e.preventDefault(); save({ scheme: "ugc_srf", srf_upgrade_on: upgradeOn, amount_monthly: Number(amount) }); }}>
          <Field label="Upgraded to SRF on"><input type="date" required value={upgradeOn} onChange={(e) => setUpgradeOn(e.target.value)} /></Field>
          <Field label="New monthly amount (₹)"><input type="number" required min={0} value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
          <Button kind="secondary" type="submit">Record SRF upgrade</Button>
        </form>
      )}
      <form className="row" onSubmit={(e) => { e.preventDefault(); save({ end_date: endDate }); }}>
        <Field label="Ends"><input type="date" required value={endDate} onChange={(e) => setEndDate(e.target.value)} /></Field>
        <Button kind="secondary" type="submit">Change end date</Button>
      </form>
      <Field label="Status">
        <select value={f.status} onChange={(e) => save({ status: e.target.value })}>
          {(Object.keys(STATUS_LABELS) as FellowshipStatus[]).map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
        </select>
      </Field>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

export default function FellowshipsPage() {
  const { me } = useSession();
  const { data, error, reload } = useFetch<Fellowship[]>("/fellowships");
  const [openId, setOpenId] = useState<string | null>(null);
  const canRecord = me ? me.office_roles.includes("research_office") || me.unit_roles.some((r) => r.role === "admin") : false;
  const open = data?.find((f) => f.id === openId) ?? null;

  return (
    <>
      <PageHeader eyebrow="Grants" title="Fellowships" />
      {canRecord && <RecordFellowship onAdded={reload} />}
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table label="Fellowships" head={["Scholar", "Scheme", "Per month", "Period", "Status", ""]}
          empty={<div className="empty-state"><Owl pose="empty" size={96} /><h2>No fellowships recorded</h2></div>}>
          {data.map((f) => (
            <tr key={f.id}>
              <td>{f.scholar.name}<div className="muted">{f.roll_number} · {f.unit.name}</div></td>
              <td>{SCHEME_LABELS[f.scheme]}{f.srf_upgrade_on && <div className="muted">SRF since {formatDate(f.srf_upgrade_on)}</div>}</td>
              <td className="mono">{formatMoney(f.amount_monthly)}{f.hra_amount > 0 && <div className="muted">+ HRA {formatMoney(f.hra_amount)}</div>}</td>
              <td className="mono">{formatDate(f.start_date)} – {formatDate(f.end_date)}</td>
              <td>{STATUS_LABELS[f.status]}</td>
              <td>
                {(f.can_manage || f.sees_ledger) && (
                  <Button kind="ghost" aria-expanded={openId === f.id} onClick={() => setOpenId(openId === f.id ? null : f.id)}>
                    {openId === f.id ? "Close" : f.can_manage ? "Manage" : "Ledger"}
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </Table>
      )}
      {open && (
        <Card>
          <h2>{open.scholar.name} · {SCHEME_LABELS[open.scheme]}</h2>
          {open.can_manage && <Manage key={`${open.id}-${open.scheme}-${open.end_date}`} f={open} onSaved={reload} />}
          {open.sees_ledger && <><h3>Ledger</h3><Ledger owner={{ fellowship_id: open.id }} /></>}
        </Card>
      )}
    </>
  );
}
