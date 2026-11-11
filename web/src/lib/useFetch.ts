"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";

/** GET a resource; errors surface as a message, never as silently empty data. */
export function useFetch<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(path !== null);

  const reload = useCallback(async () => {
    if (path === null) return;
    setLoading(true);
    try {
      setData(await api<T>(path));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}

/** A list read page by page, so a long list is never silently cut off. */
export function usePagedFetch<T>(path: string | null, pageSize: number) {
  const sep = path?.includes("?") ? "&" : "?";
  const first = useFetch<T[]>(path && `${path}${sep}limit=${pageSize}`);
  const [end, setEnd] = useState(false);
  const [moreError, setMoreError] = useState<string | null>(null);
  const { data, setData, reload } = first;

  useEffect(() => setEnd(false), [path]);

  const more = useCallback(async () => {
    if (!data) return;
    try {
      const next = await api<T[]>(`${path}${sep}limit=${pageSize}&offset=${data.length}`);
      setData([...data, ...next]);
      setEnd(next.length < pageSize);
      setMoreError(null);
    } catch (e) {
      setMoreError(errorText(e));
    }
  }, [data, path, sep, pageSize, setData]);

  return {
    ...first,
    error: first.error ?? moreError,
    reload: () => {
      setEnd(false);
      return reload();
    },
    hasMore: !end && (data?.length ?? 0) >= pageSize,
    more,
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
