"""The APR workflow state machine — the single source of lifecycle state.

TRANSITIONS maps (state, action) → (roles allowed, new state). Nothing else in the
codebase decides who may move a report where; routers only route actions here.
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from .audit import write_audit
from .errors import ApiError
from .models import ProgressReport

TRANSITIONS: dict[tuple[str, str], tuple[frozenset[str], str]] = {
	("draft", "submit"): (frozenset({"scholar", "admin"}), "submitted"),
	("submitted", "approve"): (frozenset({"supervisor", "admin"}), "approved"),
	("submitted", "send_back"): (frozenset({"supervisor", "admin"}), "rejected"),
	("rejected", "resubmit"): (frozenset({"scholar", "admin"}), "draft"),
}

ACTIONS = {action for _, action in TRANSITIONS}


async def apply_action(db: AsyncSession, report: ProgressReport, action: str, actor) -> ProgressReport:
	if action not in ACTIONS:
		raise ApiError(422, "unknown_action", f"Unknown workflow action '{action}'")
	entry = TRANSITIONS.get((report.state, action))
	if entry is None:
		raise ApiError(
			422,
			"workflow_violation",
			f"Cannot {action} a report in state '{report.state}'",
			{"state": report.state, "action": action},
		)
	roles, new_state = entry
	if actor.role not in roles:
		raise ApiError(
			422,
			"workflow_violation",
			f"Role '{actor.role}' may not {action} a report in state '{report.state}'",
			{"state": report.state, "action": action},
		)
	from_state = report.state
	report.state = new_state
	# approved_on is the compliance stamp: set on approve, cleared anywhere else.
	if action == "approve":
		report.approved_on = date.today()
	else:
		report.approved_on = None
	await write_audit(
		db,
		table_name="progress_reports",
		record_id=report.id,
		action="transition",
		actor_id=actor.user.id,
		actor_role=actor.role,
		from_state=from_state,
		to_state=new_state,
		data={"action": action},
	)
	return report