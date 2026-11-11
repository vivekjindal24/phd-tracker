"use client";

import { useEffect, useState } from "react";
import { Button, ErrorText, Field, ShowMore } from "@/components/ui/kit";
import { useDebounced, usePagedFetch } from "@/lib/useFetch";

type Person = { id: string; full_name: string };
const PAGE = 20;

/** People from a list endpoint that takes `q`, `limit` and `offset` (/scholars, /faculty):
 *  twenty at a time, narrowed by typing, so nobody is out of reach in a large university. */
function usePeople<T extends Person>(path: string | null) {
  const [q, setQ] = useState("");
  const search = useDebounced(q);
  const sep = path?.includes("?") ? "&" : "?";
  const list = usePagedFetch<T>(path && (search ? `${path}${sep}q=${encodeURIComponent(search)}` : path), PAGE);
  const box = <input type="search" placeholder="Type a name to narrow the list" value={q} onChange={(e) => setQ(e.target.value)} />;
  return { ...list, box, searching: Boolean(search) };
}

/** Choose one person. A lone choice is taken without asking. */
export function PersonPicker<T extends Person>({ label, hint, path, value, onPick, detail }: {
  label: string;
  hint?: string;
  path: string;
  value: T | null;
  onPick: (person: T | null) => void;
  detail: (person: T) => string;
}) {
  const { data, error, hasMore, more, box, searching } = usePeople<T>(path);
  const only = !searching && data?.length === 1 ? data[0] : undefined;
  useEffect(() => {
    if (!value && only) onPick(only);
  }, [value, only, onPick]);

  if (value) {
    return (
      <div className="field">
        {label}
        <div className="person-picked">
          <span><strong>{value.full_name}</strong> <span className="muted">{detail(value)}</span></span>
          {!only && <Button kind="ghost" onClick={() => onPick(null)}>Change</Button>}
        </div>
      </div>
    );
  }
  return (
    <div className="person-picker">
      <Field label={label} hint={hint}>{box}</Field>
      <ErrorText>{error}</ErrorText>
      <ul className="person-options">
        {data?.map((p) => (
          <li key={p.id}>
            <button type="button" onClick={() => onPick(p)}>{p.full_name} <span className="muted">{detail(p)}</span></button>
          </li>
        ))}
      </ul>
      {data?.length === 0 && <p className="muted">Nobody matches.</p>}
      <ShowMore hasMore={hasMore} more={more} />
    </div>
  );
}

/** Tick several people. Ticks are kept while the list is narrowed or extended. */
export function PersonChecks<T extends Person>({ legend, path, value, onChange, detail }: {
  legend: string;
  path: string | null;
  value: string[];
  onChange: (ids: string[]) => void;
  detail: (person: T) => string;
}) {
  const { data, error, hasMore, more, box } = usePeople<T>(path);
  const toggle = (id: string) => onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id]);
  return (
    <div className="person-picker">
      <Field label={`${legend} (${value.length} selected)`}>{box}</Field>
      <ErrorText>{error}</ErrorText>
      <ul className="person-options person-checks">
        {data?.map((p) => (
          <li key={p.id}>
            <label>
              <input type="checkbox" checked={value.includes(p.id)} onChange={() => toggle(p.id)} />
              {p.full_name} <span className="muted">{detail(p)}</span>
            </label>
          </li>
        ))}
      </ul>
      {data?.length === 0 && <p className="muted">Nobody matches.</p>}
      <ShowMore hasMore={hasMore} more={more} />
    </div>
  );
}
