"use client";

import { useEffect, useState } from "react";
import { Button, Card } from "@/components/ui/kit";
import type { PhdIndexRow, SettingsData } from "@/lib/types";
import type { Save } from "./save";

/** PRD F17, part 4: the university's own index of the PhD file — its rows, in its order, each
 *  filled from Anveshan's records. Whatever no row takes is printed after them; empty: Anveshan's. */
export function PhdIndex({ data, save }: { data: SettingsData; save: Save }) {
  const [rows, setRows] = useState<PhdIndexRow[]>(data.phd_index);
  useEffect(() => setRows(data.phd_index), [data.phd_index]);
  const dirty = JSON.stringify(rows) !== JSON.stringify(data.phd_index);
  const label = (key: string) => data.phd_sources.find((s) => s.key === key)?.label ?? key;
  const used = new Set(rows.flatMap((r) => r.sources));
  const groups = [...new Set(data.phd_sources.map((s) => s.group))];
  const anveshans = () => data.phd_sources.filter((s) => s.key.startsWith("annexure:"))
    .map((s) => ({ title: s.group, sources: [s.key] }));

  const change = (i: number, row: PhdIndexRow) => setRows(rows.map((r, j) => (j === i ? row : r)));
  const move = (i: number, by: number) => {
    const next = [...rows];
    [next[i], next[i + by]] = [next[i + by]!, next[i]!];
    setRows(next);
  };

  return (
    <Card className="settings-phd-index">
      <h2>Index of the PhD file</h2>
      {rows.length === 0 ? (
        <>
          <p className="muted">Anveshan&apos;s index of 16 parts is used. Write your own to print the file in your rows, order and numbering.</p>
          <Button onClick={() => setRows(anveshans())}>Write your own index</Button>
        </>
      ) : (
        <>
          <p className="muted">
            Each row is filled from the records you pick; a row with none prints “Not held in Anveshan”.
            A record goes in one row only. Records no row takes are printed after your rows, so nothing is left out.
          </p>
          <ol className="phd-index">
            {rows.map((r, i) => (
              <li key={i}>
                <div className="row">
                  <input aria-label={`Row ${i + 1}`} maxLength={200} value={r.title}
                    onChange={(e) => change(i, { ...r, title: e.target.value })} />
                  <button type="button" aria-label={`Move row ${i + 1} up`} disabled={i === 0} onClick={() => move(i, -1)}>↑</button>
                  <button type="button" aria-label={`Move row ${i + 1} down`} disabled={i === rows.length - 1} onClick={() => move(i, 1)}>↓</button>
                  <button type="button" aria-label={`Remove row ${i + 1}`} onClick={() => setRows(rows.filter((_, j) => j !== i))}>×</button>
                </div>
                <div className="chips">
                  {r.sources.map((s) => (
                    <span key={s} className="badge">
                      {label(s)}{" "}
                      <button type="button" aria-label={`Take ${label(s)} out of row ${i + 1}`}
                        onClick={() => change(i, { ...r, sources: r.sources.filter((x) => x !== s) })}>×</button>
                    </span>
                  ))}
                  <select aria-label={`Add a record to row ${i + 1}`} value=""
                    onChange={(e) => e.target.value && change(i, { ...r, sources: [...r.sources, e.target.value] })}>
                    <option value="">Add a record…</option>
                    {groups.map((g) => (
                      <optgroup key={g} label={g}>
                        {data.phd_sources.filter((s) => s.group === g && !used.has(s.key)).map((s) => (
                          <option key={s.key} value={s.key}>{s.label}</option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>
              </li>
            ))}
          </ol>
          <div className="row">
            <Button onClick={() => setRows([...rows, { title: "New row", sources: [] }])}>Add row</Button>
            {dirty && (
              <>
                <Button kind="primary" disabled={rows.some((r) => !r.title.trim())}
                  onClick={() => save("/settings", "PATCH", { phd_index: rows }).catch(() => {})}>Save index</Button>
                <Button kind="ghost" onClick={() => setRows(data.phd_index)}>Undo</Button>
              </>
            )}
            {data.phd_index.length > 0 && (
              <Button kind="ghost" onClick={() => save("/settings", "PATCH", { phd_index: [] }).catch(() => {})}>
                Back to Anveshan&apos;s index
              </Button>
            )}
          </div>
        </>
      )}
    </Card>
  );
}
