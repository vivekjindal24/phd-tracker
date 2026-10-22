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
