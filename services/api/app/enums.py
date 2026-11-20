"""Enumerated values. DB CHECK constraints and Pydantic Literals are both built from these
tuples, so they cannot drift apart (DATABASE.md §2)."""

from typing import Literal, get_args
from zoneinfo import ZoneInfo

AssignedRole = Literal[
    "unit_head", "admin", "research_office", "exam_office", "library", "vice_chancellor"
]
ASSIGNED_ROLES = get_args(AssignedRole)
UNIT_ROLES = ("unit_head", "admin")
OFFICE_ROLES = ("research_office", "exam_office", "library", "vice_chancellor")
# Read every record, university wide: the Research Office and the Vice Chancellor.
READ_ALL_ROLES = frozenset({"research_office", "vice_chancellor"})

Designation = Literal["Professor", "Associate Professor", "Assistant Professor"]
DESIGNATIONS = get_args(Designation)
UGC_CAP: dict[str, int] = {
    "Professor": 8,
    "Associate Professor": 6,
    "Assistant Professor": 4,
}

Stage = Literal[
    "Registered",
    "Coursework",
    "Proposal Approved",
    "Pre-Synopsis",
    "Thesis Submitted",
    "Viva",
    "Degree Awarded",
]
STAGES = get_args(Stage)

ModuleKey = Literal[
    "publications",
    "conferences",
    "documents",
    "coursework",
    "admissions",
    "fellowships",
    "projects",
    "ledger",
]
MODULE_KEYS = get_args(ModuleKey)

CoSupervision = Literal["off", "view", "approve"]
CO_SUPERVISION = get_args(CoSupervision)

ItemType = Literal[
    "progress_report",
    "publication",
    "coursework_clearance",
    "thesis_submission",
    "no_dues_clearance",
    "fellowship_claim",
    "viva_arrangement",
]
ITEM_TYPES = get_args(ItemType)
SigningAction = Literal["approve", "send_back"]
SIGNING_ACTIONS = get_args(SigningAction)

StepKind = Literal[
    "supervisor", "department", "research_office", "exam_office", "library", "vice_chancellor"
]
STEP_KINDS = get_args(StepKind)

ItemState = Literal["draft", "in_review", "sent_back", "approved"]
ITEM_STATES = get_args(ItemState)

ApprovalAction = Literal["submit", "approve", "send_back", "resubmit"]
APPROVAL_ACTIONS = get_args(ApprovalAction)

PasswordTokenPurpose = Literal["invite", "reset"]
PASSWORD_TOKEN_PURPOSES = get_args(PasswordTokenPurpose)

SsoProvider = Literal["google", "microsoft"]
SSO_PROVIDERS = get_args(SsoProvider)

AuditAction = Literal["insert", "update", "soft_delete", "restore", "transition", "lookup"]
AUDIT_ACTIONS = get_args(AuditAction)

NotificationCategory = Literal[
    "approval_waiting",
    "sent_back",
    "approved",
    "apr_due",
    "meeting_tomorrow",
    "fellowship_ending",
    "grant_alert",
    "seminar",
    "system",
]
NOTIFICATION_CATEGORIES = get_args(NotificationCategory)
# E.164: "+" then country code and number, 8-15 digits (users.whatsapp_number CHECK).
WHATSAPP_NUMBER_RE = r"^\+[1-9][0-9]{7,14}$"

DeliveryStatus = Literal["not_sent", "sent", "failed", "muted"]  # per channel: email, WhatsApp
DELIVERY_STATUSES = get_args(DeliveryStatus)

MilestoneType = Literal[
    "coursework",
    "proposal_approval",
    "rac_review",
    "pre_synopsis",
    "thesis_submission",
    "viva",
    "degree_awarded",
]
MILESTONE_TYPES = get_args(MilestoneType)
MilestoneStatus = Literal["Pending", "Approved", "Rejected"]
MILESTONE_STATUSES = get_args(MilestoneStatus)
ApprovalBody = Literal["RDC", "DPGC", "DRC", "RAC", "Other"]
APPROVAL_BODIES = get_args(ApprovalBody)

# The kinds of seminar (PRD F15): the six-monthly progress review, and the registration (proposal)
# and pre-synopsis seminars. Each kind is marked by rubric scores or by the university's own form
# questions with a recommendation (settings.seminar_forms).
SeminarKind = Literal["progress", "registration", "pre_synopsis"]
SEMINAR_KINDS = get_args(SeminarKind)
SEMINAR_KIND_LABELS = {
    "progress": "Progress seminar",
    "registration": "Registration seminar",
    "pre_synopsis": "Pre-synopsis seminar",
}
SeminarMarking = Literal["rubric", "questions"]
# The forms the PhD file prints (phd_forms.py), in career order, with Anveshan's titles. A
# university renames each, gives it its form number ("Form VII-A") and its "copy to" list in
# settings.phd_forms (PRD F17, part 4).
PHD_FORMS = {
    "appointment": "Appointment of Supervisor",
    "co_appointment": "Appointment of Co-supervisor",
    "committee_formation": "Formation of Research Advisory Committee",
    "clearance": "Coursework Clearance",
    "comprehensive": "Report of Comprehensive Examination",
    "registration_notice": "Registration Seminar: Circular",
    "registration_report": "Registration Seminar Report",
    "registration_attendance": "Registration Seminar: Attendance Sheet",
    "progress_notice": "Progress Seminar: Circular",
    "progress_attendance": "Progress Seminar: Attendance Sheet",
    "pre_synopsis_notice": "Pre-Thesis Synopsis Seminar: Circular",
    "pre_synopsis_report": "Pre-Thesis Synopsis Report",
    "pre_synopsis_attendance": "Pre-Thesis Synopsis Seminar: Attendance Sheet",
    "submission": "Submission of Thesis",
    "viva_approval": "Approval for Conduct of Viva-Voce Examination",
    "viva_notice": "Viva-Voce Examination: Notice",
    "viva_attendance": "Viva-Voce Examination: Attendance Sheet",
    "viva_report": "Viva-Voce Examination Report",
}
# Who may sign a seminar's or viva's notice (PRD F17b), in the order they sign; the department
# admin picks, per department and per seminar or viva (owner, 2026-11-21). Defaults: notices.py.
NoticeSigner = Literal["exam_office", "drc_secretary", "admin", "drc_chair", "unit_head", "dean"]
NOTICE_SIGNERS = get_args(NoticeSigner)
NOTICE_SIGNER_LABELS = {
    "exam_office": "Controller of Examinations",
    "drc_secretary": "Secretary, DRC",
    "admin": "Department Admin",
    "drc_chair": "Chairperson, DRC",
    "unit_head": "Head of Department",
    "dean": "Dean",
}
FormAnswer = Literal["yes", "no"]
SeminarRecommendation = Literal["recommended", "recommended_with_changes", "not_recommended"]
SEMINAR_RECOMMENDATIONS = get_args(SeminarRecommendation)
DEFAULT_SEMINAR_FORMS = {
    "progress": {"marking": "rubric", "form_name": "", "questions": []},
    "registration": {
        "marking": "questions",
        "form_name": "Registration seminar report",
        "questions": [
            "Is the research problem clearly formulated?",
            "Is the review of literature adequate?",
            "Are the objectives clearly stated?",
            "Is the proposed methodology appropriate?",
            "Can the work be completed within the time allowed?",
        ],
    },
    "pre_synopsis": {
        "marking": "questions",
        "form_name": "Pre-synopsis seminar report",
        "questions": [
            "Have the objectives of the research been met?",
            "Are the results adequate for a thesis?",
            "Does the scholar meet the publication requirement?",
            "Is the synopsis in the prescribed format?",
            "Have earlier comments of the committee been addressed?",
        ],
    },
}
SeminarStatus = Literal["scheduled", "cancelled"]
SEMINAR_STATUSES = get_args(SeminarStatus)
SeminarGraders = Literal["panel", "panel_and_attending"]
SEMINAR_GRADERS = get_args(SeminarGraders)
PanelKind = Literal["panel", "attending"]
PANEL_KINDS = get_args(PanelKind)
DEFAULT_RUBRIC = (
    {"name": "Progress", "max": 10},
    {"name": "Presentation", "max": 10},
    {"name": "Understanding", "max": 10},
    {"name": "Plan", "max": 10},
)

# Progress reports (PRD F8): each approver rates the period; the standard sections a scholar
# fills unless the university sets its own (settings.apr_custom_template).
Rating = Literal["satisfactory", "needs_improvement", "unsatisfactory"]
RATINGS = get_args(Rating)
DEFAULT_APR_SECTIONS = (
    {"name": "Work done this period", "hint": "Experiments, fieldwork, reading and writing."},
    {
        "name": "Progress against objectives",
        "hint": "Each objective of the proposal: where it stands.",
    },
    {"name": "Difficulties faced", "hint": "Anything that slowed the work, and what would help."},
    {"name": "Plan for the next six months", "hint": "What will be done, and by when."},
)

TodoPart = Literal[
    "introduction",
    "literature_review",
    "methodology",
    "experiments_results",
    "discussion",
    "writing_presentation",
    "other",
]
TODO_PARTS = get_args(TodoPart)
TODO_PART_LABELS: dict[str, str] = {
    "introduction": "Introduction",
    "literature_review": "Literature review",
    "methodology": "Methodology",
    "experiments_results": "Experiments & results",
    "discussion": "Discussion",
    "writing_presentation": "Writing & presentation",
    "other": "Other",
}
TodoStatus = Literal["open", "done"]
TODO_STATUSES = get_args(TodoStatus)

Period = Literal["January-June", "July-December"]
PERIODS = get_args(Period)

PubType = Literal["journal", "conference", "book_chapter", "patent"]
PUB_TYPES = get_args(PubType)
Indexing = Literal["scopus", "wos", "ugc_care", "other"]
INDEXINGS = get_args(Indexing)
PubStatus = Literal["submitted", "accepted", "published"]
PUB_STATUSES = get_args(PubStatus)
ConferenceType = Literal["paper_presented", "poster", "attended", "invited_talk", "workshop"]
CONFERENCE_TYPES = get_args(ConferenceType)

# Committee roles (PRD F9b). A scholar's advisory committee: chairperson, member, VC nominee
# (the supervisor is always its secretary, never a row). A department's committee:
# chairperson, secretary, member, each also in a seat. Listed in print order.
CommitteeRole = Literal["chairperson", "secretary", "member", "vc_nominee"]
COMMITTEE_ROLES = get_args(CommitteeRole)
ADVISORY_ROLES = frozenset({"chairperson", "member", "vc_nominee"})
DEPARTMENT_ROLES = frozenset({"chairperson", "secretary", "member"})
CommitteeSeat = Literal["hod", "dean_nominee", "faculty_nominee", "vc_nominee", "scholar"]
COMMITTEE_SEATS = get_args(CommitteeSeat)
DEFAULT_DEPARTMENT_COMMITTEE = "Department Research Committee (DRC)"

# Ethics clearances (PRD F9c): a committee's approval, or a recorded "not required".
EthicsKind = Literal["human", "animal", "biosafety", "not_required"]
ETHICS_KINDS = get_args(EthicsKind)

DocKind = Literal["proposal", "chapter", "synopsis", "draft", "other"]
DOC_KINDS = get_args(DocKind)
Recommendation = Literal["accept", "minor_revision", "major_revision", "reject"]
RECOMMENDATIONS = get_args(Recommendation)
# Supervisor appointments kept as history (PRD F17, Form IV).
SupervisionRole = Literal["supervisor", "co_supervisor"]
SUPERVISION_ROLES = get_args(SupervisionRole)
# Where an examiner comes from: the PhD file lists national and international examiners apart.
ExaminerOrigin = Literal["national", "international"]
EXAMINER_ORIGINS = get_args(ExaminerOrigin)
# The advisory committee's line on a progress report: may continue with / without assistantship.
Assistantship = Literal["with", "without"]
ASSISTANTSHIPS = get_args(Assistantship)
# Comprehensive examination (Form VI): each attempt's result.
ComprehensiveResult = Literal["satisfactory", "unsatisfactory"]
COMPREHENSIVE_RESULTS = get_args(ComprehensiveResult)
ReviewStatus = Literal["invited", "accepted", "declined", "expired", "submitted"]
REVIEW_STATUSES = get_args(ReviewStatus)
CopyKind = Literal["view", "download"]
COPY_KINDS = get_args(CopyKind)
VivaOutcome = Literal["pass", "redefend", "fail"]
VIVA_OUTCOMES = get_args(VivaOutcome)
# ponytail: one zone for every install (Indian universities); a setting if that ever changes.
LOCAL_TZ = ZoneInfo("Asia/Kolkata")
# A viva board's members besides the supervisor, who always sits on it (PRD M3, Form XI).
VivaBoardRole = Literal["chairperson", "external_examiner", "member"]
VIVA_BOARD_ROLES = get_args(VivaBoardRole)

EntranceRoute = Literal["net_jrf", "gate", "university_test", "other"]
ENTRANCE_ROUTES = get_args(EntranceRoute)
InterviewResult = Literal["pending", "selected", "not_selected"]
INTERVIEW_RESULTS = get_args(InterviewResult)

FellowshipScheme = Literal["ugc_jrf", "ugc_srf", "csir", "inspire", "institute", "other"]
FELLOWSHIP_SCHEMES = get_args(FellowshipScheme)
FellowshipStatus = Literal["active", "completed", "terminated"]
FELLOWSHIP_STATUSES = get_args(FellowshipStatus)
ProjectStatus = Literal["ongoing", "completed", "closed"]
PROJECT_STATUSES = get_args(ProjectStatus)
LedgerKind = Literal["disbursement", "expense"]
LEDGER_KINDS = get_args(LedgerKind)
LedgerHead = Literal[
    "fellowship_salary", "equipment", "consumables", "travel", "contingency", "overhead"
]
LEDGER_HEADS = get_args(LedgerHead)
LedgerWarning = Literal["over_balance", "over_sanction", "future_date", "outside_period"]

LeftReason = Literal["withdrawn", "cancelled"]
LEFT_REASONS = get_args(LeftReason)

# Scholar profile (PRD F6): the values AISHE and UGC returns ask for.
StudyMode = Literal["full_time", "part_time"]
STUDY_MODES = get_args(StudyMode)
Gender = Literal["female", "male", "transgender"]
GENDERS = get_args(Gender)
Category = Literal["general", "obc", "sc", "st", "ews"]
CATEGORIES = get_args(Category)
# Time records against the UGC maximum duration (Phase 4): extensions and the women/PwD
# relaxation move the limit; leave is recorded and checked against its own limit.
TimeKind = Literal["extension", "relaxation", "maternity_leave", "medical_leave", "other_leave"]
TIME_KINDS = get_args(TimeKind)

# Groups a supervisor can share meeting minutes with (PRD F7); unticked groups see only the date.
MeetingShare = Literal["unit_heads", "research_office", "admins"]
MEETING_SHARES = get_args(MeetingShare)

# Records comments can hang off (DATABASE.md §3.7); visibility = the record's.
CommentTarget = Literal[
    "scholars",
    "meetings",
    "progress_reports",
    "milestones",
    "publications",
    "conferences",
    "documents",
    "thesis_submissions",
    "coursework_clearances",
    "no_dues_clearances",
    "fellowship_claims",
    "viva_arrangements",
]
COMMENT_TARGETS = get_args(CommentTarget)

# Tables files may hang off; each phase adds its owners (with a migration widening the CHECK).
FileOwner = Literal[
    "scholars",
    "progress_reports",
    "publications",
    "conferences",
    "documents",
    "thesis_submissions",
    "examiner_reports",
    "vivas",
    "shodhganga_deposits",
    "utilisation_certificates",
    "thesis_reviews",
    "ethics_clearances",
    "signed_copies",
]
FILE_OWNER_TABLES = get_args(FileOwner)
FileStatus = Literal["pending", "ready"]
FILE_STATUSES = get_args(FileStatus)
# Named places for a scholar's own documents in the PhD file (files.slot, owner `scholars`).
FileSlot = Literal["employer_noc", "entrance_minutes"]
FILE_SLOTS = get_args(FileSlot)
# The PhD file's annexures, in the order of the career (PRD F17; titles in phd_file.py).
PhdAnnexure = Literal[
    "admission",
    "employer_noc",
    "supervision",
    "advisory_committee",
    "coursework",
    "comprehensive",
    "registration_seminar",
    "decisions",
    "progress",
    "publications",
    "pre_synopsis_seminar",
    "submission",
    "examiners",
    "viva",
    "award",
    "copies",
]
PHD_ANNEXURES = get_args(PhdAnnexure)
# The papers an entry of the PhD file holds, each a signed copy (signed_copies.kind), in the order
# the paper file keeps them (PRD F17b). Which entry takes which: phd_file.py.
DOCUMENT_KINDS: dict[str, str] = {
    "signed_copy": "Signed copy",
    "mark_sheet": "Coursework mark sheet",
    "notice": "Notification",
    "report": "Report",
    "attendance": "Attendance sheet",
    "drc_minutes": "Minutes of the DRC",
    "drc_notice": "Notice of the DRC chairperson",
    "fee_due": "Examination fee due creation",
    "corrections": "Modifications made at the examiners' request",
    "examiner_panel": "Panel of examiners",
    "invite_national": "Email to the national examiner",
    "accept_national": "Acceptance of the national examiner",
    "invite_international": "Email to the international examiner",
    "accept_international": "Acceptance of the international examiner",
    "viva_approval": "Approval to conduct the viva",
    "viva_board": "Constitution of the examination board",
    "viva_notice": "Notification of the viva",
    "viva_examiner_email": "Email to the viva examiner",
    "viva_report": "Viva-voce examination report",
}
DocumentKind = Literal[
    "signed_copy",
    "mark_sheet",
    "notice",
    "report",
    "attendance",
    "drc_minutes",
    "drc_notice",
    "fee_due",
    "corrections",
    "examiner_panel",
    "invite_national",
    "accept_national",
    "invite_international",
    "accept_international",
    "viva_approval",
    "viva_board",
    "viva_notice",
    "viva_examiner_email",
    "viva_report",
]
assert get_args(DocumentKind) == tuple(DOCUMENT_KINDS)
# Papers naming the examiners: the Research Office, the Exam Office and the admin over the
# scholar's unit handle them; never the scholar or their supervisor (owner, 2026-11-19).
# The coursework mark sheet comes from the exam cell: theirs and the department admin's count at
# once; a scholar's own upload waits for the department admin (owner, 2026-11-20).
MARK_SHEETS = frozenset({"mark_sheet"})
EXAMINER_DOCUMENTS = frozenset(
    {
        "examiner_panel",
        "invite_national",
        "accept_national",
        "invite_international",
        "accept_international",
    }
)

# PRD F3 defaults: who starts an item, and the default chain.
INITIATOR: dict[str, str] = {
    "progress_report": "scholar",
    "publication": "scholar",
    "thesis_submission": "scholar",
    "coursework_clearance": "exam_office",
    "no_dues_clearance": "scholar",
    "fellowship_claim": "scholar",
    "viva_arrangement": "exam_office",
}
DEFAULT_CHAINS: dict[str, tuple[str, ...]] = {
    "progress_report": ("supervisor", "department", "research_office"),
    "publication": ("supervisor", "library", "research_office"),
    "coursework_clearance": ("department", "exam_office", "research_office"),
    # PRD M3: lab dues (supervisor), department, books (library), fees (research office)
    "no_dues_clearance": ("supervisor", "department", "library", "research_office"),
    # PRD M6: the guide certifies the month, the department forwards, the office accepts
    "fellowship_claim": ("supervisor", "department", "research_office"),
    # PRD M3: the Exam Office proposes the viva (Form X) and its board (Form XI); the VC approves
    "viva_arrangement": ("vice_chancellor",),
    "thesis_submission": (
        "supervisor",
        "department",
        "library",
        "exam_office",
        "research_office",
    ),
}


FACULTY_REQUEST_KINDS = ("seminar_panel", "co_supervisor")
FACULTY_REQUEST_STATUSES = ("pending", "accepted", "declined", "cancelled")


def sql_in(values: tuple[str, ...]) -> str:
    """Render a tuple as a SQL IN-list for CHECK constraints (values are code constants)."""
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)
