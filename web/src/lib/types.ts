import type { DateFormat } from "@/lib/format";
/** Mirrors of the API's response models (services/api/app/schemas/). */

export type OfficeRole = "vice_chancellor" | "research_office" | "exam_office" | "library";
export type GrievanceRole = "grievance_cell" | "ombudsperson";
export type AssignedRole = "unit_head" | "admin" | OfficeRole | GrievanceRole;
export type Role = "scholar" | "supervisor" | AssignedRole;
export type CoSupervision = "off" | "view" | "approve";
export type StepKind = "supervisor" | "department" | OfficeRole;
export type ItemType =
  | "progress_report"
  | "publication"
  | "coursework_clearance"
  | "thesis_submission"
  | "no_dues_clearance"
  | "fellowship_claim"
  | "viva_arrangement"
  | "supervisor_change";
export type ModuleKey =
  | "publications"
  | "conferences"
  | "documents"
  | "coursework"
  | "admissions"
  | "fellowships"
  | "projects"
  | "ledger"
  | "patents";

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
  is_reviewer: boolean;
  co_supervision: CoSupervision;
  date_format: DateFormat; // how the university writes dates, everywhere
  modules: Record<ModuleKey, boolean>;
  unread_notifications: number;
  email_muted: string[];
  whatsapp_available: boolean;
  whatsapp_number: string | null;
  whatsapp_muted: string[];
};

export type OrgUnit = {
  id: string;
  parent_id: string | null;
  name: string;
  kind: string;
  code: string;
  path: string;
  cross_unit_directory: boolean;
  aishe_discipline: string | null;
};

/** How the university names one form of the PhD file (PRD F17); empty: Anveshan's. */
export type PhdFormName = { title: string; number: string; copy_to: string[] };
/** One row of the university's own index of the PhD file (PRD F17). */
export type PhdIndexRow = { title: string; sources: string[] };
export type SettingsData = {
  university_address: string;
  department_committee_name: string;
  co_supervision: CoSupervision;
  require_hardcopy: boolean;
  require_no_dues: boolean;
  require_ethics: boolean;
  require_two_factor: boolean;
  require_signing: boolean;
  apr_custom_template: boolean;
  apr_sections: AprSection[];
  apr_template: AprSection[];
  seminar_graders: "panel" | "panel_and_attending";
  seminar_rubric: { name: string; max: number }[];
  seminar_forms: Record<SeminarKind, SeminarForm>;
  phd_forms: Record<string, PhdFormName>;
  phd_form_defaults: Record<string, string>; // Anveshan's title of each form, in career order
  phd_index: PhdIndexRow[]; // the university's own index; empty: Anveshan's annexures
  phd_sources: { key: string; label: string; group: string }[]; // what a row may draw on
  exam_controller_id: string | null; // who signs notices as Controller of Examinations
  date_format: DateFormat;
  min_coursework_credits: number;
  min_coursework_cgpa: number;
  max_duration_years: number;
  max_extension_days: number;
  max_relaxation_days: number;
  max_maternity_leave_days: number;
  min_duration_years: number;
  max_plagiarism_percent: number;
  min_publications: number;
  publications_indexed_only: boolean;
  publication_file_required: boolean;
  patent_verifier: PatentVerifier;
  grievance_appeals_to: AppealsTo;
  modules: Record<ModuleKey, boolean>;
  chains: Record<ItemType, { kind: StepKind }[]>;
  email_configured: boolean;
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
  vice_chancellor: "Vice Chancellor",
  grievance_cell: "Grievance cell",
  ombudsperson: "Ombudsperson",
};

export const STEP_LABELS: Record<StepKind, string> = {
  supervisor: "Supervisor",
  department: "Department",
  research_office: "Research Office",
  exam_office: "Exam Office",
  library: "Library",
  vice_chancellor: "Vice Chancellor",
};

export const ITEM_LABELS: Record<ItemType, string> = {
  progress_report: "Progress report",
  publication: "Publication",
  coursework_clearance: "Coursework clearance",
  thesis_submission: "Thesis submission",
  no_dues_clearance: "No-dues clearance",
  fellowship_claim: "Fellowship claim",
  viva_arrangement: "Viva arrangement",
  supervisor_change: "Change of supervisor",
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
  patents: "Patents",
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
  left_on: string | null;
  left_reason: LeftReason | null;
  study_mode: StudyMode | null;
  // Personal data: null unless sees_personal (the API decides), then null = not recorded.
  sees_personal: boolean;
  gender: Gender | null;
  category: Category | null;
  has_disability: boolean | null;
  minority: Minority | null;
  nationality: Nationality | null;
  country: string | null; // an NRI's, PIO's or foreign national's
  father_name: string | null;
  directory_only: boolean;
};
export type StudyMode = "full_time" | "part_time";
export const STUDY_MODE_LABELS: Record<StudyMode, string> = { full_time: "Full-time", part_time: "Part-time" };
export type Gender = "female" | "male" | "transgender";
export const GENDER_LABELS: Record<Gender, string> = { female: "Female", male: "Male", transgender: "Transgender" };
export type Category = "general" | "obc" | "sc" | "st" | "ews";
export const CATEGORY_LABELS: Record<Category, string> = { general: "General", obc: "OBC", sc: "SC", st: "ST", ews: "EWS" };
/** AISHE counts the Muslim minority and the other notified minorities apart. */
export type Minority = "none" | "muslim" | "christian" | "sikh" | "buddhist" | "jain" | "parsi";
export const MINORITY_LABELS: Record<Minority, string> = {
  none: "Not from a minority community", muslim: "Muslim", christian: "Christian", sikh: "Sikh",
  buddhist: "Buddhist", jain: "Jain", parsi: "Parsi (Zoroastrian)",
};
/** AISHE's foreign students: NRIs, PIOs and other foreign nationals, each with a country. */
export type Nationality = "indian" | "nri" | "pio" | "foreign";
export const NATIONALITY_LABELS: Record<Nationality, string> = {
  indian: "Indian", nri: "Indian, non-resident (NRI)", pio: "Person of Indian origin (PIO / OCI)", foreign: "Foreign national",
};
/** AISHE's disability is benchmark disability (RPwD Act 2016). */
export const DISABILITY_LABEL = "Person with benchmark disability (40% or more)";
export type LeftReason = "withdrawn" | "cancelled";
export const LEFT_LABELS: Record<LeftReason, string> = { withdrawn: "Withdrew", cancelled: "Registration cancelled" };

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
  /** How this viewer's decision is signed: required by the university, optional, or off. */
  signing: "required" | "optional" | "off";
  send_back_targets: { to_step: number | null; label: string }[];
  blocked_reason: string | null;
  history: { action: string; actor: string; on_behalf_of: string | null; step: string | null; to: string | null; comment: string | null; rating: Rating | null; at: string; signature: string | null }[];
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
  quick_approve: boolean; // nothing to fill in first, so it can be approved from the queue in bulk
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
  approved_title: string | null;
  seminar_id: string | null; // the seminar whose recommendation opened this entry
  updated_at: string;
};

/** PRD F15: progress seminars review a report period; the other kinds do not. */
export type SeminarKind = "progress" | "registration" | "pre_synopsis";
export const SEMINAR_KIND_LABELS: Record<SeminarKind, string> = {
  progress: "Progress seminar",
  registration: "Registration seminar",
  pre_synopsis: "Pre-synopsis seminar",
};
/** How a kind is marked at this university: rubric scores, or its own form questions. */
export type SeminarForm = { marking: "rubric" | "questions"; form_name: string; questions: string[] };
export type SeminarRecommendation = "recommended" | "recommended_with_changes" | "not_recommended";
export const SEMINAR_RECOMMENDATION_LABELS: Record<SeminarRecommendation, string> = {
  recommended: "Recommended",
  recommended_with_changes: "Recommended with changes",
  not_recommended: "Not recommended",
};
export type FormAnswer = { question: string; answer: "yes" | "no"; remark: string };

export type SeminarRow = {
  id: string;
  unit: Ref;
  kind: SeminarKind;
  title: string;
  starts_at: string;
  venue: string;
  report_due: string | null;
  report_year: number | null;
  period: Period | null;
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
  can_request: boolean;
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
  answers: FormAnswer[] | null;
  recommendation: SeminarRecommendation | null;
  comment: string;
  submitted_at: string;
};
export type ReviewView = {
  seminar_id: string;
  seminar_title: string;
  seminar_kind: SeminarKind;
  scholar: Ref;
  form: SeminarForm;
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
export type OrcidWork = { put_code: number; title: string; year: number | null; kind: string; doi: string | null; already_recorded: boolean };
export type DoiImportOut = { created: { id: string; title: string }[]; skipped: { doi: string; reason: string }[] };
/** What Crossref knows of a DOI (GET /publications/doi). */
export type DoiDetails = Omit<PublicationContent, "indexing" | "pub_year"> & {
  doi: string;
  pub_year: number | null;
  already_recorded: boolean;
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
/** A faculty paper with the Library (PRD M1): no chain, verified or returned with a note. */
export type Verification = "waiting" | "returned" | "verified";
export const VERIFICATION_LABELS: Record<Verification, string> = {
  waiting: "With the Library",
  returned: "Returned to you",
  verified: "Verified",
};
/** The badge class each shows in, matching the item states' colours. */
export const VERIFICATION_BADGE: Record<Verification, string> = {
  waiting: "badge-in_review",
  returned: "badge-sent_back",
  verified: "badge-approved",
};
export type FacultyPublicationRow = {
  id: string;
  faculty: Ref;
  unit: string;
  title: string;
  venue: string;
  pub_type: PubType;
  pub_year: number;
  indexing: Indexing[];
  verification: Verification;
  updated_at: string;
};
export type FacultyPublication = FacultyPublicationRow & PublicationContent & {
  return_note: string | null;
  checked_at: string | null;
  checked_by: string | null;
  can_edit: boolean;
  can_check: boolean;
};
/** A patent of a member of faculty or a scholar (PRD M10): checked by the office the
 *  university chose (settings.patent_verifier), verified or returned with a note. */
export type PatentStatus = "filed" | "published" | "granted";
export const PATENT_STATUS_LABELS: Record<PatentStatus, string> = {
  filed: "Filed",
  published: "Published",
  granted: "Granted",
};
/** A patent's check, whichever office does it. */
export const PATENT_CHECK_LABELS: Record<Verification, string> = {
  waiting: "Waiting to be checked",
  returned: "Returned",
  verified: "Verified",
};
export type PatentVerifier = "research_office" | "library";
export const PATENT_VERIFIER_LABELS: Record<PatentVerifier, string> = {
  research_office: "Research Office",
  library: "Library",
};
export type PatentContent = {
  title: string;
  inventors: string;
  application_number: string;
  filed_on: string;
  office: string;
  patent_status: PatentStatus;
  published_on: string | null;
  granted_on: string | null;
  patent_number: string | null;
};
export type PatentRow = {
  id: string;
  owner: Ref;
  owner_kind: "faculty" | "scholar";
  unit: string;
  title: string;
  application_number: string;
  filed_on: string;
  patent_status: PatentStatus;
  granted_on: string | null;
  verification: Verification;
  updated_at: string;
};
export type Patent = PatentRow & PatentContent & {
  return_note: string | null;
  checked_at: string | null;
  checked_by: string | null;
  verifier: PatentVerifier;
  can_edit: boolean;
  can_check: boolean;
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
  | "grievances"
  | "thesis_reviews"
  | "scholars"
  | "publications"
  | "faculty_publications"
  | "patents"
  | "conferences"
  | "documents"
  | "thesis_submissions"
  | "examiner_reports"
  | "vivas"
  | "shodhganga_deposits"
  | "utilisation_certificates"
  | "ethics_clearances"
  | "progress_reports"
  | "signed_copies"
  | "announcements";
/** A notice on the notice board; `unit` null: the whole university. */
export type Notice = {
  id: string;
  unit: Ref | null;
  title: string;
  body: string;
  pinned: boolean;
  ends_on: string | null;
  posted_by: string | null;
  posted_at: string;
  can_manage: boolean;
};
export type CommentTarget =
  | "scholars"
  | "meetings"
  | "progress_reports"
  | "milestones"
  | "publications"
  | "conferences"
  | "documents"
  | "thesis_submissions"
  | "coursework_clearances"
  | "no_dues_clearances"
  | "fellowship_claims"
  | "viva_arrangements"
  | "supervisor_changes";
/** Named places for a scholar's own documents in the PhD file. */
export type FileSlot = "employer_noc" | "entrance_minutes";
export const FILE_SLOT_LABELS: Record<FileSlot, string> = {
  employer_noc: "Employer's no-objection certificate",
  entrance_minutes: "Minutes of the entrance examination",
};
export type FileItem = {
  id: string;
  slot: FileSlot | null;
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
export type Branding = {
  university: string;
  address: string;
  has_logo: boolean;
  logo_version: number | null;
};

export type CertificateCheck = {
  name: string;
  thesis_title: string;
  unit: string;
  viva_date: string;
  issued_on: string;
  status: "valid" | "revoked";
};

export type ReviewStatus = "invited" | "accepted" | "declined" | "expired" | "submitted";
export const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  invited: "Invited",
  accepted: "Accepted",
  declined: "Declined",
  expired: "No reply",
  submitted: "Submitted",
};
export type ReviewRow = {
  id: string;
  name: string;
  email: string;
  institution: string;
  origin: ExaminerOrigin | null;
  deadline: string;
  allow_download: boolean;
  status: ReviewStatus;
  decline_reason: string | null;
  submitted_at: string | null;
};
export type ReviewInvitation = {
  university: string;
  reviewer_name: string;
  thesis_title: string;
  abstract: string;
  deadline: string;
};
export type ReviewSummary = { id: string; thesis_title: string; deadline: string; status: ReviewStatus; is_open: boolean };
export type ReviewDetail = ReviewSummary & {
  abstract: string;
  allow_download: boolean;
  comments: { id: string; page: number; body: string }[];
};
export type ReviewCopyTrace = {
  code: string;
  kind: "view" | "download";
  issued_at: string;
  reviewer_name: string;
  reviewer_email: string;
  institution: string;
  thesis_title: string;
};

export type Evaluation = {
  thesis_id: string;
  names_hidden: boolean;
  reports: {
    id: string;
    examiner_name: string | null;
    institution: string | null;
    origin: ExaminerOrigin | null;
    received_on: string;
    recommendation: Recommendation;
    notes: string;
    released: boolean;
    comments: { page: number; body: string }[];
  }[];
  unreleased_count: number;
  reviews: ReviewRow[];
  can_invite_reviewers: boolean;
  vivas: { id: string; held_on: string; venue: string; panel: string; outcome: VivaOutcome; notes: string }[];
  deposit: { id: string; deposited_on: string; handle_url: string } | null;
  certificates: {
    id: string;
    serial: string;
    issued_on: string;
    verify_path: string;
    revoked_at: string | null;
    revoked_reason: string | null;
  }[];
  can_issue_certificate: boolean;
  can_revoke_certificate: boolean;
  can_record_reports: boolean;
  arrangements: { id: string; state: ItemState; scheduled_at: string; held: boolean }[];
  can_arrange_viva: boolean;
  can_record_viva: boolean;
  viva_block: string | null;
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

export type Course = { id: string; unit: Ref; code: string; title: string; credits: number };
export type CourseworkView = {
  scholar: Ref;
  enrolments: { id: string; course: Course; semester: string; grade: string | null; grade_points: number | null }[];
  credits: number;
  cgpa: number | null;
  min_credits: number;
  min_cgpa: number;
  problems: string[];
  clearance: { id: string; state: ItemState; waiting_on: string | null; cleared_on: string | null } | null;
  can_manage: boolean;
  locked: boolean;
};
export type ClearanceContent = { credits: number | null; cgpa: number | null; cleared_on: string | null };

export type EntranceRoute = "net_jrf" | "gate" | "university_test" | "other";
export const ENTRANCE_LABELS: Record<EntranceRoute, string> = {
  net_jrf: "UGC-NET / JRF (exempt)",
  gate: "GATE",
  university_test: "University entrance test",
  other: "Other",
};
export type InterviewResult = "pending" | "selected" | "not_selected";
export const RESULT_LABELS: Record<InterviewResult, string> = {
  pending: "Pending",
  selected: "Selected",
  not_selected: "Not selected",
};
export type Admission = {
  id: string;
  candidate_name: string;
  email: string;
  phone: string | null;
  unit: Ref;
  entrance_route: EntranceRoute;
  entrance_score: number | null;
  interview_date: string | null;
  interview_result: InterviewResult;
  admitted_on: string | null;
  scholar_id: string | null;
  can_edit: boolean;
};

export type TimeKind = "extension" | "relaxation" | "maternity_leave" | "medical_leave" | "other_leave";
export const TIME_KIND_LABELS: Record<TimeKind, string> = {
  extension: "Extension (re-registration)",
  relaxation: "Relaxation (women / PwD)",
  maternity_leave: "Maternity / child-care leave",
  medical_leave: "Medical leave",
  other_leave: "Other leave",
};
export type DurationStatus = "ok" | "near" | "over" | "done" | "left" | "unknown";
export type DurationView = {
  scholar: Ref;
  admission_date: string | null;
  limit_date: string | null;
  days_left: number | null;
  status: DurationStatus;
  extension_days: number;
  relaxation_days: number;
  leave_days: number;
  warnings: string[];
  adjustments: { id: string; kind: TimeKind; start_date: string; end_date: string; days: number; resolution_number: string | null; notes: string }[];
  max_years: number;
  can_manage: boolean;
};
export type LeadershipRow = {
  unit: Ref;
  current: number;
  completed: number;
  median_years_to_complete: number | null;
  left: number;
  withdrawn: number;
  cancelled: number;
  dropout_rate: number | null;
  supervisors: number;
  supervisors_at_cap: number;
  average_load: number | null;
};
export type LeadershipView = {
  unit: Ref;
  total: LeadershipRow;
  by_unit: LeadershipRow[];
  at_risk: { scholar: Ref; stage: Stage; limit_date: string | null; reasons: string[] }[];
  trends: TrendYear[];
  as_of: string;
};
export type TrendYear = {
  year: string;
  so_far: boolean;
  admitted: number;
  awarded: number;
  median_years_to_complete: number | null;
  publications: number;
};

// --- grants (PRD M6-M8) ---
export type FellowshipScheme = "ugc_jrf" | "ugc_srf" | "csir" | "inspire" | "institute" | "other";
export const SCHEME_LABELS: Record<FellowshipScheme, string> = {
  ugc_jrf: "UGC JRF",
  ugc_srf: "UGC SRF",
  csir: "CSIR",
  inspire: "DST INSPIRE",
  institute: "Institute",
  other: "Other",
};
export type FellowshipStatus = "active" | "completed" | "terminated";
export type Fellowship = {
  id: string;
  scholar: Ref;
  roll_number: string;
  unit: Ref;
  scheme: FellowshipScheme;
  amount_monthly: number;
  hra_amount: number;
  start_date: string;
  end_date: string;
  srf_upgrade_on: string | null;
  status: FellowshipStatus;
  can_manage: boolean;
  sees_ledger: boolean;
};
export type ClaimContent = { fellowship_id: string; month: string; amount: number; leave_days: number; note: string };
export type FellowshipClaim = {
  id: string;
  scholar: Ref;
  fellowship_id: string;
  scheme: FellowshipScheme;
  month: string;
  amount: number;
  leave_days: number;
  state: ItemState;
  waiting_on: string | null;
  submitted_at: string | null;
  approved_at: string | null;
};
export type ProjectStatus = "ongoing" | "completed" | "closed";
export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = { ongoing: "Ongoing", completed: "Completed", closed: "Closed" };
export type Project = {
  id: string;
  title: string;
  agency: string;
  sanction_number: string;
  amount_sanctioned: number;
  start_date: string;
  end_date: string;
  status: ProjectStatus;
  pi: Ref;
  unit: Ref;
  members: { id: string; scholar: Ref; roll_number: string; member_role: string }[];
  can_manage: boolean;
  sees_ledger: boolean;
};
export type LedgerKind = "disbursement" | "expense";
export type LedgerHead = "fellowship_salary" | "equipment" | "consumables" | "travel" | "contingency" | "overhead";
export const HEAD_LABELS: Record<LedgerHead, string> = {
  fellowship_salary: "Fellowship / salary",
  equipment: "Equipment",
  consumables: "Consumables",
  travel: "Travel",
  contingency: "Contingency",
  overhead: "Overhead",
};
export type LedgerView = {
  entries: { id: string; entry_kind: LedgerKind; head: LedgerHead; amount: number; entry_date: string; reference: string | null; note: string; balance: number }[];
  received: number;
  spent: number;
  balance: number;
  sanctioned: number | null;
  can_manage: boolean;
  can_add_expense: boolean;
};
export type UtilisationCertificate = { id: string; period_start: string; period_end: string; submitted_on: string | null };

export type NoDuesMine = { required: boolean; item: ItemView | null };
export type ThesisGate = { label: string; met: boolean; detail: string };

export type FacultyRequest = {
  id: string;
  kind: "seminar_panel" | "co_supervisor";
  target: string;
  email: string;
  status: "pending" | "accepted" | "declined" | "cancelled" | "expired";
  note: string;
  requested_by_name: string;
  faculty_name: string | null;
  created_at: string;
  expires_at: string;
};

export type FacultyRequests = { incoming: FacultyRequest[]; sent: FacultyRequest[] };

export type CommitteeRole = "chairperson" | "secretary" | "member" | "vc_nominee";
export const COMMITTEE_ROLE_LABELS: Record<CommitteeRole, string> = {
  chairperson: "Chairperson",
  secretary: "Member and Secretary",
  member: "Member",
  vc_nominee: "Member (nominee of the Vice Chancellor)",
};
/** Which roles each kind of committee takes (PRD F9b); department members also sit in a seat. */
export const ADVISORY_ROLES: CommitteeRole[] = ["chairperson", "member", "vc_nominee"];
export const DEPARTMENT_ROLES: CommitteeRole[] = ["chairperson", "secretary", "member"];
export type CommitteeSeat = "hod" | "dean_nominee" | "faculty_nominee" | "vc_nominee" | "scholar";
export const COMMITTEE_SEAT_LABELS: Record<CommitteeSeat, string> = {
  hod: "Head of the Department (ex officio)",
  dean_nominee: "Dean's nominee",
  faculty_nominee: "Faculty nominated by the department",
  vc_nominee: "Vice Chancellor's nominee",
  scholar: "PhD scholar",
};
export type CommitteeMember = {
  id: string;
  name: string;
  institution: string;
  email: string | null; // an outside member's; only for those who keep the committee
  external: boolean;
  role: CommitteeRole;
  seat: CommitteeSeat | null;
};
export type CommitteeFormation = {
  id: string;
  formed_on: string;
  reference: string | null;
  notes: string;
  secretary: string | null; // the supervisor when it was formed
  members: CommitteeMember[];
};
/** `formations` newest first: the first is the current committee, the rest are history. */
export type CommitteeView = {
  title: string; // "Research Advisory Committee", or the university's name for a department's
  convener: string | null;
  formations: CommitteeFormation[];
  can_manage: boolean;
};

export type EthicsKind = "human" | "animal" | "biosafety" | "not_required";
export const ETHICS_KIND_LABELS: Record<EthicsKind, string> = {
  human: "Human ethics",
  animal: "Animal ethics",
  biosafety: "Biosafety",
  not_required: "Not required",
};
export type EthicsRecord = {
  id: string;
  kind: EthicsKind;
  committee: string | null;
  approval_number: string | null;
  approved_on: string | null;
  valid_until: string | null;
  notes: string;
};
export type EthicsView = { records: EthicsRecord[]; required: boolean; satisfied: boolean; can_manage: boolean };

/** Progress report template and assessment (PRD F8). */
export type AprSection = { name: string; hint: string };
export type SectionText = { name: string; text: string };
export type Rating = "satisfactory" | "needs_improvement" | "unsatisfactory";
export const RATING_LABELS: Record<Rating, string> = {
  satisfactory: "Satisfactory",
  needs_improvement: "Needs improvement",
  unsatisfactory: "Unsatisfactory",
};
export type PeriodActivity = { meetings: number; publications: string[] | null; conferences: string[] | null };

export type AuditRow = {
  id: string;
  at: string;
  actor: string | null;
  actor_roles: string[];
  action: "insert" | "update" | "soft_delete" | "restore" | "transition" | "lookup";
  table_name: string;
  record_id: string;
  from_state: string | null;
  to_state: string | null;
  fields: string[];
  scholar: Ref | null;
};

/** A specimen signature (PRD F17b); `image` is a data: URL. */
export type Photo = { image: string | null; can_change: boolean };
export type Signature = { image: string; uploaded_at: string; uploaded_by_self: boolean; confirmed_at: string | null };
export type PendingSignature = { user_id: string; full_name: string; email: string; signature: Signature };

/** A viva arrangement's record (PRD M3, Form X); its board is read separately. */
export type VivaArrangementContent = {
  thesis_id: string;
  scheduled_at: string;
  venue: string;
  online_link: string | null;
  notes: string;
  invited_at: string | null;
};
export type VivaBoardRole = "chairperson" | "external_examiner" | "member";
export const VIVA_BOARD_ROLE_LABELS: Record<VivaBoardRole, string> = {
  chairperson: "Chairperson",
  external_examiner: "External examiner",
  member: "Member",
};
/** Form XI. `name` is null for an external examiner this viewer may not see before the viva. */
export type VivaBoard = {
  supervisor: string | null;
  members: { id: string; role: VivaBoardRole; name: string | null; institution: string | null; email: string | null; external: boolean }[];
  names_hidden: boolean;
  can_edit: boolean;
  can_invite: boolean;
  email_configured: boolean;
};

export type ExaminerOrigin = "national" | "international";
export const EXAMINER_ORIGIN_LABELS: Record<ExaminerOrigin, string> = { national: "National", international: "International" };

/** The committee's line on a progress report (null: not stated). */
export type Assistantship = "with" | "without";

/** Form VI: numbered attempts at the comprehensive examination. */
export type ComprehensiveResult = "satisfactory" | "unsatisfactory";
export type ComprehensiveView = {
  attempts: { id: string; attempt: number; held_in: string; result: ComprehensiveResult; notes: string }[];
  passed: boolean;
  can_manage: boolean;
};

/** One supervisor or co-supervisor appointment (Form IV); `ended_on` null = current. */
export type Appointment = {
  id: string;
  role: "supervisor" | "co_supervisor";
  faculty: Ref;
  appointed_on: string | null;
  order_ref: string | null;
  ended_on: string | null;
};
export type SupervisionView = {
  appointments: Appointment[];
  can_manage: boolean;
  open_change: { id: string; state: ItemState; to: string } | null; // a change under way
  can_propose_change: boolean;
};
/** A proposed change of supervisor (item content). */
export type SupervisorChangeContent = {
  scholar_id: string;
  from: Ref | null;
  to: Ref;
  reason: string;
  scholar_consent: boolean;
  order_ref: string | null;
  effective_on: string | null;
};

/** A scholar's grievance (GET /grievances); who may read it is the API's (grievances.py). */
export type AppealsTo = "ombudsperson" | "vice_chancellor";
export type GrievanceCategory = "supervision" | "evaluation" | "coursework" | "fellowship" | "administration" | "other";
export type GrievanceStatus = "open" | "decided" | "closed" | "appealed" | "appeal_decided" | "withdrawn";
export const GRIEVANCE_CATEGORY_LABELS: Record<GrievanceCategory, string> = {
  supervision: "Supervision",
  evaluation: "Evaluation or examination",
  coursework: "Coursework",
  fellowship: "Fellowship or stipend",
  administration: "Administration",
  other: "Other",
};
export const GRIEVANCE_STATUS_LABELS: Record<GrievanceStatus, string> = {
  open: "With the grievance cell",
  decided: "Decided",
  closed: "Closed",
  appealed: "Appealed",
  appeal_decided: "Appeal decided",
  withdrawn: "Withdrawn",
};
export type Grievance = {
  id: string;
  scholar: { id: string; name: string };
  category: GrievanceCategory;
  subject: string;
  description: string;
  status: GrievanceStatus;
  filed_at: string;
  due_on: string | null;
  decision: string | null;
  decided_at: string | null;
  decided_by: string | null;
  appeal_closes_on: string | null;
  appeal_reason: string | null;
  appealed_at: string | null;
  appeal_decision: string | null;
  appeal_decided_at: string | null;
  appeal_decided_by: string | null;
  appeals_to: string;
  can: { decide: boolean; withdraw: boolean; accept: boolean; appeal: boolean; decide_appeal: boolean; attach: boolean };
};
