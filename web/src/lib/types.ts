/** Mirrors of the API's response models (services/api/app/schemas.py). */

export type AssignedRole = "unit_head" | "admin" | "research_office" | "exam_office" | "library";
export type Role = "scholar" | "supervisor" | AssignedRole;
export type CoSupervision = "off" | "view" | "approve";
export type StepKind = "supervisor" | "department" | "research_office" | "exam_office" | "library";
export type ItemType =
  | "progress_report"
  | "publication"
  | "coursework_clearance"
  | "thesis_submission";
export type ModuleKey =
  | "publications"
  | "conferences"
  | "documents"
  | "coursework"
  | "admissions"
  | "fellowships"
  | "projects"
  | "ledger";

export type Me = {
  id: string;
  email: string;
  full_name: string;
  roles: Role[];
  unit_roles: { role: AssignedRole; unit_id: string; unit_name: string; unit_path: string }[];
  office_roles: AssignedRole[];
  faculty_id: string | null;
  scholar_id: string | null;
  is_root_admin: boolean;
  co_supervision: CoSupervision;
  modules: Record<ModuleKey, boolean>;
  unread_notifications: number;
  email_muted: string[];
};

export type OrgUnit = {
  id: string;
  parent_id: string | null;
  name: string;
  kind: string;
  code: string;
  path: string;
};

export type SettingsData = {
  co_supervision: CoSupervision;
  modules: Record<ModuleKey, boolean>;
  chains: Record<ItemType, { kind: StepKind }[]>;
};

export type NotificationItem = {
  id: string;
  category: string;
  title: string;
  body: string;
  link: string | null;
  read_at: string | null;
  created_at: string;
};

export const ROLE_LABELS: Record<Role, string> = {
  scholar: "Scholar",
  supervisor: "Supervisor",
  unit_head: "Unit head",
  admin: "Admin",
  research_office: "Research Office",
  exam_office: "Exam Office",
  library: "Library",
};

export const STEP_LABELS: Record<StepKind, string> = {
  supervisor: "Supervisor",
  department: "Department",
  research_office: "Research Office",
  exam_office: "Exam Office",
  library: "Library",
};

export const ITEM_LABELS: Record<ItemType, string> = {
  progress_report: "Progress report",
  publication: "Publication",
  coursework_clearance: "Coursework clearance",
  thesis_submission: "Thesis submission",
};

export const MODULE_LABELS: Record<ModuleKey, string> = {
  publications: "Publications",
  conferences: "Conferences & talks",
  documents: "Documents & thesis",
  coursework: "Coursework",
  admissions: "Admissions",
  fellowships: "Fellowships",
  projects: "Research projects",
  ledger: "Grant ledger",
};

export const STAGES = [
  "Registered",
  "Coursework",
  "Proposal Approved",
  "Pre-Synopsis",
  "Thesis Submitted",
  "Viva",
  "Degree Awarded",
] as const;
export type Stage = (typeof STAGES)[number];

export const DESIGNATIONS = ["Professor", "Associate Professor", "Assistant Professor"] as const;
export type Designation = (typeof DESIGNATIONS)[number];

export type Ref = { id: string; name: string };

export type Scholar = {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  roll_number: string;
  unit: Ref;
  stage: Stage;
  research_title: string | null;
  admission_date: string | null;
  supervisor: Ref | null;
  co_supervisor: Ref | null;
};

export type Faculty = {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  unit: Ref;
  designation: Designation;
  employee_id: string | null;
  can_supervise: boolean;
  max_scholars: number;
  load: number;
};

export type MeetingShare = "unit_heads" | "research_office" | "admins";
export const SHARE_LABELS: Record<MeetingShare, string> = {
  unit_heads: "Unit heads (HoD, Dean)",
  research_office: "Research Office",
  admins: "Admins",
};

export type Meeting = {
  id: string;
  scholar: Ref;
  supervisor: Ref;
  meeting_date: string;
  redacted: boolean;
  agenda: string | null;
  minutes: string | null;
  action_items: string | null;
  next_meeting_date: string | null;
  shared_with: MeetingShare[];
  can_edit: boolean;
  can_share: boolean;
  created_at: string;
  updated_at: string;
};

export type ItemState = "draft" | "in_review" | "sent_back" | "approved";
export const STATE_LABELS: Record<ItemState, string> = {
  draft: "Draft",
  in_review: "In review",
  sent_back: "Sent back",
  approved: "Approved",
};

export type ItemView = {
  item_type: ItemType;
  id: string;
  label: string;
  title: string;
  scholar: Ref;
  state: ItemState;
  current_step: number | null;
  waiting_on: string | null;
  chain: { kind: StepKind; label: string; status: "done" | "current" | "upcoming" }[];
  submitted_at: string | null;
  approved_at: string | null;
  content: Record<string, unknown>;
  can_edit: boolean;
  can_submit: boolean;
  can_resubmit: boolean;
  can_act: boolean;
  send_back_targets: { to_step: number | null; label: string }[];
  blocked_reason: string | null;
  history: { action: string; actor: string; step: string | null; to: string | null; comment: string | null; at: string }[];
};

export type QueueEntry = {
  item_type: ItemType;
  id: string;
  label: string;
  title: string;
  scholar: Ref;
  step: string;
  waiting_since: string;
  days_waiting: number;
};

export type Period = "January-June" | "July-December";
export type ReportRow = {
  id: string;
  scholar: Ref;
  report_year: number;
  period: Period;
  state: ItemState;
  waiting_on: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  updated_at: string;
};

export const MILESTONE_LABELS = {
  coursework: "Coursework",
  proposal_approval: "Proposal approval",
  rac_review: "RAC review",
  pre_synopsis: "Pre-synopsis",
  thesis_submission: "Thesis submission",
  viva: "Viva",
  degree_awarded: "Degree awarded",
} as const;
export type MilestoneType = keyof typeof MILESTONE_LABELS;
export const MILESTONE_STATUSES = ["Pending", "Approved", "Rejected"] as const;
export type MilestoneStatus = (typeof MILESTONE_STATUSES)[number];
export const APPROVAL_BODIES = ["RDC", "DPGC", "DRC", "RAC", "Other"] as const;
export type ApprovalBody = (typeof APPROVAL_BODIES)[number];

export type Milestone = {
  id: string;
  scholar: Ref;
  roll_number: string;
  unit: Ref;
  milestone_type: MilestoneType;
  status: MilestoneStatus;
  approval_body: ApprovalBody;
  resolution_number: string | null;
  resolution_date: string | null;
  notes: string;
  updated_at: string;
};
