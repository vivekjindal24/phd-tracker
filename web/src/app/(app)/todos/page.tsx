"use client";

import { Owl } from "@/components/brand/Owl";
import { Card, ErrorText, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { PART_LABELS } from "@/lib/types";
import type { TodoItem, TodoPart } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import { useState } from "react";
import "./todos.css";

export default function TodosPage() {
  const { data, error, setData } = useFetch<TodoItem[]>("/todos");
  const [tickError, setTickError] = useState<string | null>(null);

  async function tick(todo: TodoItem) {
    setTickError(null);
    try {
      const next = await api<TodoItem>(`/todos/${todo.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: todo.status === "done" ? "open" : "done" }),
      });
      setData((data ?? []).map((t) => (t.id === next.id ? next : t)));
    } catch (e) {
      setTickError(errorText(e));
    }
  }

  const groups = (Object.keys(PART_LABELS) as TodoPart[])
    .map((part) => ({ part, items: (data ?? []).filter((t) => t.part === part) }))
    .filter((g) => g.items.length > 0);
  const open = (data ?? []).filter((t) => t.status === "open").length;

  return (
    <>
      <PageHeader eyebrow="From your progress seminars" title="My to-dos"
        actions={data && data.length > 0 ? <span className="badge">{open} open</span> : undefined} />
      <ErrorText>{error ?? tickError}</ErrorText>
      {data && data.length === 0 && (
        <Card className="empty-state">
          <Owl pose="empty" size={96} />
          <h2>Nothing to do yet</h2>
          <p>Points from your seminar panel appear here once your supervisor finalises the review.</p>
        </Card>
      )}
      <div className="todo-groups">
        {groups.map((g) => (
          <Card key={g.part}>
            <h2>{PART_LABELS[g.part]}</h2>
            <ul className="todo-checks">
              {g.items.map((t) => (
                <li key={t.id} className={t.status === "done" ? "done" : undefined}>
                  <label>
                    <input type="checkbox" checked={t.status === "done"} onChange={() => tick(t)} />
                    <span>{t.text}</span>
                  </label>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </>
  );
}
