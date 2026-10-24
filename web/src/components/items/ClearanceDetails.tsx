import Link from "next/link";
import { Card } from "@/components/ui/kit";
import { formatDate } from "@/lib/format";
import type { ClearanceContent, ItemView } from "@/lib/types";

/** What the clearance certifies — computed by the API when the Exam Office submits. */
export function ClearanceDetails({ item }: { item: ItemView }) {
  const c = item.content as ClearanceContent;
  return (
    <Card>
      <h2>Coursework</h2>
      <dl className="kv">
        <dt>Credits</dt><dd>{c.credits ?? <span className="muted">Computed at submit</span>}</dd>
        <dt>CGPA</dt><dd>{c.cgpa?.toFixed(2) ?? <span className="muted">Computed at submit</span>}</dd>
        <dt>Cleared on</dt><dd>{c.cleared_on ? formatDate(c.cleared_on) : <span className="muted">Not yet</span>}</dd>
      </dl>
      <Link href={`/scholars/${item.scholar.id}`}>Courses and grades on the profile →</Link>
    </Card>
  );
}
