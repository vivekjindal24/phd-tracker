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
  require_hardcopy: boolean;
  seminar_graders: "panel" | "panel_and_attending";
  seminar_rubric: { name: string; max: number }[];
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

export type SeminarRow = {
  id: string;
  unit: Ref;
  title: string;
  starts_at: string;
  venue: string;
  report_due: string;
  report_year: number;
  period: Period;
  status: "scheduled" | "cancelled";
  scholar_count: number;
};

export type SeminarDetail = SeminarRow & {
  notes: string;
  scholars: {
    scholar: Ref;
    roll_number: string;
    supervisor: string | null;
    report_state: ItemState | null;
    hardcopy_received_on: string | null;
    finalised_at: string | null;
  }[];
  panel: { faculty_id: string; name: string; kind: "panel" | "attending" }[];
  can_manage: boolean;
  require_hardcopy: boolean;
  is_grader: boolean;
  can_attend: boolean;
};

export type RubricCriterion = { name: string; max: number };

export type TodoPart =
  | "introduction"
  | "literature_review"
  | "methodology"
  | "experiments_results"
  | "discussion"
  | "writing_presentation"
  | "other";
export type Point = { part: TodoPart; text: string };
export type TodoItem = {
  id: string;
  scholar_id: string;
  part: TodoPart;
  text: string;
  status: "open" | "done";
  done_at: string | null;
  created_at: string;
};
export type GradeView = {
  grader: string;
  scores: Record<string, number>;
  rubric: RubricCriterion[];
  total: number;
  max_total: number;
  comment: string;
  submitted_at: string;
};
export type ReviewView = {
  seminar_id: string;
  seminar_title: string;
  scholar: Ref;
  rubric: RubricCriterion[];
  grades: GradeView[];
  average_percent: number | null;
  draft_points: Point[];
  finalised_at: string | null;
  todos: TodoItem[];
  can_grade: boolean;
  my_grade: GradeView | null;
  can_finalise: boolean;
  ai_available: boolean;
  parts: Record<TodoPart, string>;
};
export const PART_LABELS: Record<TodoPart, string> = {
  introduction: "Introduction",
  literature_review: "Literature review",
  methodology: "Methodology",
  experiments_results: "Experiments & results",
  discussion: "Discussion",
  writing_presentation: "Writing & presentation",
  other: "Other",
};

export type ImportKind = "faculty" | "scholars" | "history";

export type ImportReport = {
  kind: ImportKind;
  dry_run: boolean;
  total_rows: number;
  to_create: number;
  created: number;
  already_present: { row: number; what: string }[];
  errors: { row: number; column: string; message: string }[];
  invitations_sent: number | null;
  invitations_failed: string[];
};

export type PubType = "journal" | "conference" | "book_chapter" | "patent";
export type Indexing = "scopus" | "wos" | "ugc_care" | "other";
export type PubStatus = "submitted" | "accepted" | "published";
export const PUB_TYPE_LABELS: Record<PubType, string> = {
  journal: "Journal article",
  conference: "Conference paper",
  book_chapter: "Book chapter",
  patent: "Patent",
};
export const INDEXING_LABELS: Record<Indexing, string> = {
  scopus: "Scopus",
  wos: "Web of Science",
  ugc_care: "UGC-CARE",
  other: "Other",
};
export const PUB_STATUS_LABELS: Record<PubStatus, string> = {
  submitted: "Submitted",
  accepted: "Accepted",
  published: "Published",
};
export type PublicationContent = {
  title: string;
  authors: string;
  pub_type: PubType;
  venue: string;
  issn_isbn: string | null;
  indexing: Indexing[];
  doi: string | null;
  pub_year: number;
  pub_status: PubStatus;
};
export type PublicationRow = {
  id: string;
  scholar: Ref;
  title: string;
  venue: string;
  pub_type: PubType;
  pub_year: number;
  indexing: Indexing[];
  state: ItemState;
  waiting_on: string | null;
  updated_at: string;
};

export type ConferenceType = "paper_presented" | "poster" | "attended" | "invited_talk" | "workshop";
export const CONFERENCE_TYPE_LABELS: Record<ConferenceType, string> = {
  paper_presented: "Paper presented",
  poster: "Poster",
  attended: "Attended",
  invited_talk: "Invited talk",
  workshop: "Workshop",
};
export type Conference = {
  id: string;
  scholar: Ref;
  event_name: string;
  event_type: ConferenceType;
  event_date: string;
  place: string;
  title: string | null;
  can_edit: boolean;
};

export type FileOwner =
  | "scholars"
  | "publications"
  | "conferences"
  | "documents"
  | "thesis_submissions"
  | "examiner_reports"
  | "vivas"
  | "shodhganga_deposits";
export type CommentTarget =
  | "scholars"
  | "meetings"
  | "progress_reports"
  | "milestones"
  | "publications"
  | "conferences"
  | "documents"
  | "thesis_submissions";
export type FileItem = {
  id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  status: string;
  uploaded_by: string;
  created_at: string;
};

export type ThesisContent = {
  title: string;
  plagiarism_tool: string | null;
  plagiarism_score: number | null;
  examiners: string | null;
  examiners_entered: boolean;
  examiners_hidden: boolean;
};
export type Recommendation = "accept" | "minor_revision" | "major_revision" | "reject";
export const RECOMMENDATION_LABELS: Record<Recommendation, string> = {
  accept: "Accept",
  minor_revision: "Minor revision",
  major_revision: "Major revision",
  reject: "Reject",
};
export type VivaOutcome = "pass" | "redefend" | "fail";
export const VIVA_LABELS: Record<VivaOutcome, string> = {
  pass: "Passed",
  redefend: "Re-defend after revision",
  fail: "Not passed",
};
export type Evaluation = {
  thesis_id: string;
  names_hidden: boolean;
  reports: {
    id: string;
    examiner_name: string | null;
    institution: string | null;
    received_on: string;
    recommendation: Recommendation;
    notes: string;
    released: boolean;
  }[];
  unreleased_count: number;
  vivas: { id: string; held_on: string; venue: string; panel: string; outcome: VivaOutcome; notes: string }[];
  deposit: { id: string; deposited_on: string; handle_url: string } | null;
  can_record_reports: boolean;
  can_record_viva: boolean;
  can_record_deposit: boolean;
};
export type ThesisRow = {
  id: string;
  scholar: Ref;
  title: string;
  state: ItemState;
  waiting_on: string | null;
  updated_at: string;
};
export type DocKind = "proposal" | "chapter" | "synopsis" | "draft" | "other";
export const DOC_KIND_LABELS: Record<DocKind, string> = {
  proposal: "Proposal",
  chapter: "Chapter",
  synopsis: "Synopsis",
  draft: "Draft",
  other: "Other",
};
export type DocumentItem = {
  id: string;
  scholar: Ref;
  title: string;
  doc_kind: DocKind;
  updated_at: string;
  can_edit: boolean;
  versions: { id: string; version_no: number; note: string; file_id: string; file_name: string; size_bytes: number; created_at: string }[];
};
