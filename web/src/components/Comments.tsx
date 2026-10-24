"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "@/lib/api";
import type { CommentTarget } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import { Button, Card, ErrorText } from "./ui/kit";
import "./comments.css";

type CommentItem = { id: string; author: string; author_id: string; body: string; created_at: string; mine: boolean };

/** A flat thread on any record; visible exactly when the record is (the API decides). */
export function Comments({ target, recordId }: { target: CommentTarget; recordId: string }) {
  const { data, error, setData } = useFetch<CommentItem[]>(`/comments?table_name=${target}&record_id=${recordId}`);
  const [body, setBody] = useState("");
  const [postError, setPostError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function post(e: FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setPostError(null);
    try {
      const c = await api<CommentItem>("/comments", {
        method: "POST",
        body: JSON.stringify({ table_name: target, record_id: recordId, body }),
      });
      setData([...(data ?? []), c]);
      setBody("");
    } catch (err) {
      setPostError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setPostError(null);
    try {
      await api(`/comments/${id}`, { method: "DELETE" });
      setData((data ?? []).filter((c) => c.id !== id));
    } catch (err) {
      setPostError(errorText(err));
    }
  }

  if (error) return null; // no access to the record's thread: show nothing rather than an error
  return (
    <Card className="comments">
      <h2>Comments</h2>
      {data && data.length === 0 && <p className="muted">No comments yet.</p>}
      <ol className="comment-list">
        {data?.map((c) => (
          <li key={c.id} className={c.mine ? "mine" : undefined}>
            <div className="comment-head">
              <strong>{c.author}</strong>
              <time dateTime={c.created_at}>{new Date(c.created_at).toLocaleString()}</time>
              {c.mine && <button type="button" className="comment-delete" onClick={() => remove(c.id)}
                aria-label="Delete your comment">Delete</button>}
            </div>
            <p>{c.body}</p>
          </li>
        ))}
      </ol>
      <form onSubmit={post} className="comment-form">
        <label className="visually-hidden" htmlFor={`comment-${recordId}`}>Write a comment</label>
        <textarea id={`comment-${recordId}`} value={body} maxLength={4000} placeholder="Write a comment…"
          onChange={(e) => setBody(e.target.value)} />
        <ErrorText>{postError}</ErrorText>
        <Button kind="primary" type="submit" disabled={busy || !body.trim()}>Post</Button>
      </form>
    </Card>
  );
}
