"use client";

import { useEffect, useState } from "react";
import { Button, Card } from "@/components/ui/kit";
import { ITEM_LABELS, STEP_LABELS } from "@/lib/types";
import type { ItemType, StepKind } from "@/lib/types";
import type { Save } from "./save";

const MAX_STEPS = 8;
const KINDS = Object.keys(STEP_LABELS) as StepKind[];

function ChainRow({
  itemType,
  steps,
  save,
}: {
  itemType: ItemType;
  steps: StepKind[];
  save: Save;
}) {
  const [draft, setDraft] = useState(steps);
  const [adding, setAdding] = useState<StepKind>("supervisor");
  const [busy, setBusy] = useState(false);
  useEffect(() => setDraft(steps), [steps]);
  const dirty = draft.join() !== steps.join();

  const move = (i: number, by: -1 | 1) => {
    const next = [...draft];
    const [step] = next.splice(i, 1);
    if (step) next.splice(i + by, 0, step);
    setDraft(next);
  };

  async function commit() {
    setBusy(true);
    try {
      await save(`/settings/chains/${itemType}`, "PUT", { steps: draft.map((kind) => ({ kind })) });
    } catch {
      // error shown by the page; the draft stays for correction
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="chain">
      <h3>{ITEM_LABELS[itemType]}</h3>
      <ol className="chain-steps">
        {draft.map((kind, i) => (
          <li key={`${kind}-${i}`} className="chain-step">
            <span>
              {i + 1}. {STEP_LABELS[kind]}
            </span>
            <span className="chain-step-actions">
              <button type="button" aria-label={`Move ${STEP_LABELS[kind]} earlier`}
                disabled={i === 0} onClick={() => move(i, -1)}>‹</button>
              <button type="button" aria-label={`Move ${STEP_LABELS[kind]} later`}
                disabled={i === draft.length - 1} onClick={() => move(i, 1)}>›</button>
              <button type="button" aria-label={`Remove ${STEP_LABELS[kind]}`}
                disabled={draft.length === 1} onClick={() => setDraft(draft.filter((_, j) => j !== i))}>×</button>
            </span>
          </li>
        ))}
      </ol>
      <div className="chain-controls">
        <label className="visually-hidden" htmlFor={`add-${itemType}`}>Step to add</label>
        <select id={`add-${itemType}`} value={adding} onChange={(e) => setAdding(e.target.value as StepKind)}>
          {KINDS.map((k) => (
            <option key={k} value={k}>{STEP_LABELS[k]}</option>
          ))}
        </select>
        <Button disabled={draft.length >= MAX_STEPS} onClick={() => setDraft([...draft, adding])}>
          Add step
        </Button>
        {dirty && (
          <>
            <Button kind="primary" disabled={busy} onClick={commit}>Save chain</Button>
            <Button kind="ghost" onClick={() => setDraft(steps)}>Undo</Button>
          </>
        )}
      </div>
    </li>
  );
}

export function ChainEditor({
  chains,
  save,
}: {
  chains: Record<ItemType, { kind: StepKind }[]>;
  save: Save;
}) {
  return (
    <Card className="settings-chains">
      <h2>Approval chains</h2>
      <p className="muted">
        One chain per item type for the whole university. Changes apply to new submissions only.
      </p>
      <ul className="chain-list">
        {(Object.keys(ITEM_LABELS) as ItemType[]).map((type) => (
          <ChainRow key={type} itemType={type} steps={chains[type].map((s) => s.kind)} save={save} />
        ))}
      </ul>
    </Card>
  );
}
