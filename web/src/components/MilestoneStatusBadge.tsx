import type { MilestoneStatus } from "@/lib/types";

const CLASS: Record<MilestoneStatus, string> = {
  Pending: "badge-draft",
  Approved: "badge-approved",
  Rejected: "badge-sent_back",
};

export function MilestoneStatusBadge({ status }: { status: MilestoneStatus }) {
  return <span className={`badge ${CLASS[status]}`}>{status}</span>;
}
