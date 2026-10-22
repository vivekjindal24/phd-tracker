import { STATE_LABELS } from "@/lib/types";
import type { ItemState } from "@/lib/types";

/** Workflow state, text first and colour second; the step comes from the API. */
export function StateBadge({ state, waitingOn }: { state: ItemState; waitingOn?: string | null }) {
  const text = state === "in_review" && waitingOn ? `In review · ${waitingOn}` : STATE_LABELS[state];
  return <span className={`badge badge-${state}`}>{text}</span>;
}
