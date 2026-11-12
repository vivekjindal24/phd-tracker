"""Enumerated values. DB CHECK constraints and Pydantic Literals are both built from these
tuples, so they cannot drift apart (DATABASE.md §2)."""

from typing import Literal, get_args

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
]
ITEM_TYPES = get_args(ItemType)

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

# Ethics clearances (PRD F9c): a committee's approval, or a recorded "not required".
EthicsKind = Literal["human", "animal", "biosafety", "not_required"]
ETHICS_KINDS = get_args(EthicsKind)

DocKind = Literal["proposal", "chapter", "synopsis", "draft", "other"]
DOC_KINDS = get_args(DocKind)
Recommendation = Literal["accept", "minor_revision", "major_revision", "reject"]
RECOMMENDATIONS = get_args(Recommendation)
ReviewStatus = Literal["invited", "accepted", "declined", "expired", "submitted"]
REVIEW_STATUSES = get_args(ReviewStatus)
CopyKind = Literal["view", "download"]
COPY_KINDS = get_args(CopyKind)
VivaOutcome = Literal["pass", "redefend", "fail"]
VIVA_OUTCOMES = get_args(VivaOutcome)

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
]
FILE_OWNER_TABLES = get_args(FileOwner)
FileStatus = Literal["pending", "ready"]
FILE_STATUSES = get_args(FileStatus)

# PRD F3 defaults: who starts an item, and the default chain.
INITIATOR: dict[str, str] = {
    "progress_report": "scholar",
    "publication": "scholar",
    "thesis_submission": "scholar",
    "coursework_clearance": "exam_office",
    "no_dues_clearance": "scholar",
}
DEFAULT_CHAINS: dict[str, tuple[str, ...]] = {
    "progress_report": ("supervisor", "department", "research_office"),
    "publication": ("supervisor", "library", "research_office"),
    "coursework_clearance": ("department", "exam_office", "research_office"),
    # PRD M3: lab dues (supervisor), department, books (library), fees (research office)
    "no_dues_clearance": ("supervisor", "department", "library", "research_office"),
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
