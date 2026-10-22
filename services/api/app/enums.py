"""Enumerated values. DB CHECK constraints and Pydantic Literals are both built from these
tuples, so they cannot drift apart (DATABASE.md §2)."""

from typing import Literal, get_args

AssignedRole = Literal["unit_head", "admin", "research_office", "exam_office", "library"]
ASSIGNED_ROLES = get_args(AssignedRole)
UNIT_ROLES = ("unit_head", "admin")
OFFICE_ROLES = ("research_office", "exam_office", "library")

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

ItemType = Literal["progress_report", "publication", "coursework_clearance", "thesis_submission"]
ITEM_TYPES = get_args(ItemType)

StepKind = Literal["supervisor", "department", "research_office", "exam_office", "library"]
STEP_KINDS = get_args(StepKind)

ItemState = Literal["draft", "in_review", "sent_back", "approved"]
ITEM_STATES = get_args(ItemState)

ApprovalAction = Literal["submit", "approve", "send_back", "resubmit"]
APPROVAL_ACTIONS = get_args(ApprovalAction)

AuditAction = Literal["insert", "update", "soft_delete", "restore", "transition"]
AUDIT_ACTIONS = get_args(AuditAction)

NotificationCategory = Literal[
    "approval_waiting",
    "sent_back",
    "approved",
    "apr_due",
    "meeting_tomorrow",
    "fellowship_ending",
    "seminar",
    "system",
]
NOTIFICATION_CATEGORIES = get_args(NotificationCategory)

EmailStatus = Literal["not_sent", "sent", "failed", "muted"]
EMAIL_STATUSES = get_args(EmailStatus)

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

# Groups a supervisor can share meeting minutes with (PRD F7); unticked groups see only the date.
MeetingShare = Literal["unit_heads", "research_office", "admins"]
MEETING_SHARES = get_args(MeetingShare)

# Tables files may hang off; each phase adds its owners (with a migration widening the CHECK).
FileOwner = Literal["scholars"]
FILE_OWNER_TABLES = get_args(FileOwner)
FileStatus = Literal["pending", "ready"]
FILE_STATUSES = get_args(FileStatus)

# PRD F3 defaults: who starts an item, and the default chain.
INITIATOR: dict[str, str] = {
    "progress_report": "scholar",
    "publication": "scholar",
    "thesis_submission": "scholar",
    "coursework_clearance": "exam_office",
}
DEFAULT_CHAINS: dict[str, tuple[str, ...]] = {
    "progress_report": ("supervisor", "department", "research_office"),
    "publication": ("supervisor", "library", "research_office"),
    "coursework_clearance": ("department", "exam_office", "research_office"),
    "thesis_submission": (
        "supervisor",
        "department",
        "library",
        "exam_office",
        "research_office",
    ),
}


def sql_in(values: tuple[str, ...]) -> str:
    """Render a tuple as a SQL IN-list for CHECK constraints (values are code constants)."""
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)
