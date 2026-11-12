"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, apiPage } from "./api";
import type { Page } from "./api";

/** GET a resource; errors surface as a message, never as silently empty data. */
export function useFetch<T>(path: string | null, load: (path: string) => Promise<T> = api<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(path !== null);

  const reload = useCallback(async () => {
    if (path === null) return;
    setLoading(true);
    try {
      setData(await load(path));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [path, load]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}

/** A list read page by page, so a long list is never silently cut off; `total` is how many
 *  rows match in all. */
export function usePagedFetch<T>(path: string | null, pageSize: number) {
  const sep = path?.includes("?") ? "&" : "?";
  const first = useFetch<Page<T>>(path && `${path}${sep}limit=${pageSize}`, apiPage<T>);
  const [end, setEnd] = useState(false);
  const [moreError, setMoreError] = useState<string | null>(null);
  const { data: page, setData, reload } = first;
  const data = page?.rows ?? null;

  useEffect(() => setEnd(false), [path]);

  const more = useCallback(async () => {
    if (!page) return;
    try {
      const next = await apiPage<T>(`${path}${sep}limit=${pageSize}&offset=${page.rows.length}`);
      setData({ rows: [...page.rows, ...next.rows], total: next.total });
      setEnd(next.rows.length < pageSize);
      setMoreError(null);
    } catch (e) {
      setMoreError(errorText(e));
    }
  }, [page, path, sep, pageSize, setData]);

  return {
    data,
    loading: first.loading,
    error: first.error ?? moreError,
    reload: () => {
      setEnd(false);
      return reload();
    },
    hasMore: !end && (data?.length ?? 0) >= pageSize,
    more,
    total: page?.total ?? null,
  };
}

/** A search box's text, trimmed, once typing pauses: one request per pause, not per key. */
export function useDebounced(value: string, ms = 300): string {
  const [settled, setSettled] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setSettled(value.trim()), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

export function errorText(e: unknown): string {
  return e instanceof ApiError ? e.message : String(e);
}
