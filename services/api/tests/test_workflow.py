"""The approval engine end to end (TESTING.md §1.1). Uses a test-only `demo_items` table with
the same approval columns every real item type carries, so the engine is verified before the
first real item type (progress reports, Phase 2) exists."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import ForeignKey, select, update
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app import workflow
from app.auth.principal import load_principal
from app.errors import ApiError
from app.models import ApprovalActionRow, ApprovalChain, AuditLog, Notification, Settings
from app.models.base import Base, DomainRow
from app.models.workflow import ApprovalColumns, approval_constraints
from app.scope import unit_path


class DemoItem(ApprovalColumns, DomainRow, Base):
    __tablename__ = "demo_items"
    __table_args__ = approval_constraints("demo_items")

    scholar_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scholars.id"))


@pytest.fixture(scope="session", autouse=True)
async def demo_table(migrated):
    from app.db import engine

    async with engine.begin() as conn:
        await conn.run_sync(lambda c: DemoItem.__table__.create(c, checkfirst=True))


async def make_ctx(session, scholar, item_type="progress_report"):
    item = DemoItem(scholar_id=scholar.id)
    session.add(item)
    await session.flush()
    await session.refresh(item)
    return workflow.ItemContext(item_type, item, scholar, await unit_path(session, scholar.unit_id))


async def as_(session, user):
    return await load_principal(session, user)


async def violation(coro):
    with pytest.raises(ApiError) as exc:
        await coro
    assert (exc.value.status, exc.value.code) == (422, "workflow_violation")


async def notified(session, user) -> list[str]:
    rows = await session.scalars(
        select(Notification.category).where(Notification.user_id == user.id)
    )
    return list(rows)


async def test_apr_runs_full_default_chain(session, world):
    ctx = await make_ctx(session, world.s_a1b)  # A1 scholar supervised by sup_a2
    await workflow.submit(session, await as_(session, world.scholar_a1b), ctx)
    assert (ctx.item.state, ctx.item.current_step) == ("in_review", 0)
    assert await notified(session, world.sup_a2) == ["approval_waiting"]

    await workflow.approve(session, await as_(session, world.sup_a2), ctx)
    assert workflow.current_kind(ctx) == "department"
    # Nearest unit with a head/admin is A1 itself: Meera and admin_a1, not the Dean.
    assert await notified(session, world.admin_a1) == ["approval_waiting"]
    assert await notified(session, world.dean_a) == []

    await workflow.approve(session, await as_(session, world.admin_a1), ctx)
    await workflow.approve(session, await as_(session, world.research_office), ctx)
    assert (ctx.item.state, ctx.item.current_step) == ("approved", None)
    assert ctx.item.approved_at is not None
    assert "approved" in await notified(session, world.scholar_a1b)

    actions = await session.scalars(
        select(ApprovalActionRow.action).where(ApprovalActionRow.item_id == ctx.item.id)
    )
    assert list(actions) == ["submit", "approve", "approve", "approve"]
    transitions = await session.scalars(
        select(AuditLog.to_state).where(
            AuditLog.table_name == "demo_items", AuditLog.action == "transition"
        )
    )
    assert list(transitions) == ["in_review", "in_review", "in_review", "approved"]


async def test_department_step_notifies_next_level_when_nearest_head_just_acted(session, world):
    """A HoD who supervises their own scholar cannot also take the department step; with no
    other head or admin in the department, the Dean must hear about it (SECURITY.md §4)."""
    from app.models import RoleAssignment

    await session.execute(
        update(RoleAssignment)
        .where(RoleAssignment.user_id == world.admin_a1.id)
        .values(deleted_at=datetime.now(UTC))
    )
    ctx = await make_ctx(session, world.s_a1)  # supervised by Meera, HoD of A1
    await workflow.submit(session, await as_(session, world.scholar_a1), ctx)
    await workflow.approve(session, await as_(session, world.meera), ctx)
    assert workflow.current_kind(ctx) == "department"
    assert await notified(session, world.dean_a) == ["approval_waiting"]


async def test_wrong_actor_is_rejected_at_every_kind_of_step(session, world):
    ctx = await make_ctx(session, world.s_a1b)
    await workflow.submit(session, await as_(session, world.scholar_a1b), ctx)
    for outsider in (world.library, world.hod_a2, world.meera, world.scholar_a1b):
        await violation(workflow.approve(session, await as_(session, outsider), ctx))
    await workflow.approve(session, await as_(session, world.sup_a2), ctx)
    # Department step: a head of another department cannot act; the Dean (ancestor) can.
    await violation(workflow.approve(session, await as_(session, world.hod_b1), ctx))
    assert await workflow.can_act(session, await as_(session, world.dean_a), ctx)
    await workflow.approve(session, await as_(session, world.dean_a), ctx)
    await violation(workflow.approve(session, await as_(session, world.exam_office), ctx))


async def test_only_the_initiator_submits(session, world):
    ctx = await make_ctx(session, world.s_a1)
    await violation(workflow.submit(session, await as_(session, world.meera), ctx))
    await violation(workflow.submit(session, await as_(session, world.scholar_a2), ctx))


async def test_coursework_is_initiated_by_exam_office(session, world):
    ctx = await make_ctx(session, world.s_a1b, "coursework_clearance")
    await violation(workflow.submit(session, await as_(session, world.scholar_a1b), ctx))
    await workflow.submit(session, await as_(session, world.exam_office), ctx)
    assert workflow.current_kind(ctx) == "department"


async def test_send_back_to_initiator_then_resubmit_restarts_chain(session, world):
    ctx = await make_ctx(session, world.s_a1b)
    await workflow.submit(session, await as_(session, world.scholar_a1b), ctx)
    await workflow.approve(session, await as_(session, world.sup_a2), ctx)
    await workflow.send_back(session, await as_(session, world.admin_a1), ctx, "Add the RAC dates")
    assert (ctx.item.state, ctx.item.current_step) == ("sent_back", None)
    assert "sent_back" in await notified(session, world.scholar_a1b)

    scholar = await as_(session, world.scholar_a1b)
    workflow.assert_editable(scholar, ctx)  # editable again while sent back
    await workflow.resubmit(session, scholar, ctx)
    assert (ctx.item.state, ctx.item.current_step) == ("in_review", 0)


async def test_send_back_to_an_earlier_step(session, world):
    ctx = await make_ctx(session, world.s_a1b)
    await workflow.submit(session, await as_(session, world.scholar_a1b), ctx)
    await workflow.approve(session, await as_(session, world.sup_a2), ctx)
    await workflow.approve(session, await as_(session, world.admin_a1), ctx)
    office = await as_(session, world.research_office)
    await workflow.send_back(session, office, ctx, "Supervisor must re-check", to_step=0)
    assert (ctx.item.state, ctx.item.current_step) == ("in_review", 0)
    assert await notified(session, world.sup_a2) == ["approval_waiting", "sent_back"]


async def test_send_back_rules(session, world):
    ctx = await make_ctx(session, world.s_a1b)
    await workflow.submit(session, await as_(session, world.scholar_a1b), ctx)
    await workflow.approve(session, await as_(session, world.sup_a2), ctx)
    dept = await as_(session, world.admin_a1)
    await violation(workflow.send_back(session, dept, ctx, "   "))  # reason required
    await violation(workflow.send_back(session, dept, ctx, "x", to_step=1))  # not earlier
    await violation(workflow.send_back(session, dept, ctx, "x", to_step=2))  # later


async def test_no_one_approves_two_consecutive_steps(session, world):
    # Meera supervises s_a1 AND heads/administers A1.
    ctx = await make_ctx(session, world.s_a1)
    await workflow.submit(session, await as_(session, world.scholar_a1), ctx)
    meera = await as_(session, world.meera)
    await workflow.approve(session, meera, ctx)
    assert workflow.holds_step(meera, ctx, "department")  # she holds the role...
    await violation(workflow.approve(session, meera, ctx))  # ...but cannot act twice
    await workflow.approve(session, await as_(session, world.admin_a1), ctx)  # DRC coordinator
    assert workflow.current_kind(ctx) == "research_office"


async def test_no_self_approval_even_with_an_office_role(session, world, client):
    from tests.conftest import auth

    await client.post(
        "/api/v1/role-assignments",
        json={"user_id": str(world.scholar_a2.id), "role": "research_office"},
        headers=auth(world.root_admin.id),
    )
    ctx = await make_ctx(session, world.s_a2)
    scholar = await as_(session, world.scholar_a2)
    await workflow.submit(session, scholar, ctx)
    assert not workflow.holds_step(scholar, ctx, "research_office")


async def test_chain_snapshot_protects_in_flight_items(session, world):
    ctx = await make_ctx(session, world.s_a1b)
    await workflow.submit(session, await as_(session, world.scholar_a1b), ctx)
    await session.execute(
        update(ApprovalChain)
        .where(ApprovalChain.item_type == "progress_report")
        .values(steps=[{"kind": "library"}])
    )
    await workflow.approve(session, await as_(session, world.sup_a2), ctx)
    assert workflow.current_kind(ctx) == "department"  # old chain still applies
    fresh = await make_ctx(session, world.s_a2)
    await workflow.submit(session, await as_(session, world.scholar_a2), fresh)
    assert workflow.current_kind(fresh) == "library"  # new submissions use the new chain


async def test_approved_items_are_immutable(session, world):
    await session.execute(
        update(ApprovalChain)
        .where(ApprovalChain.item_type == "progress_report")
        .values(steps=[{"kind": "research_office"}])
    )
    ctx = await make_ctx(session, world.s_a2)
    scholar = await as_(session, world.scholar_a2)
    await workflow.submit(session, scholar, ctx)
    await workflow.approve(session, await as_(session, world.research_office), ctx)
    with pytest.raises(ApiError):
        workflow.assert_editable(scholar, ctx)
    await violation(workflow.approve(session, await as_(session, world.research_office), ctx))
    await violation(workflow.resubmit(session, scholar, ctx))


@pytest.mark.parametrize(("mode", "may_act"), [("off", False), ("view", False), ("approve", True)])
async def test_co_supervisor_acts_only_under_approve(session, world, mode, may_act):
    await session.execute(update(Settings).values(co_supervision=mode))
    ctx = await make_ctx(session, world.s_a1)
    await workflow.submit(session, await as_(session, world.scholar_a1), ctx)
    assert await workflow.can_act(session, await as_(session, world.co_sup), ctx) is may_act
    if may_act:
        assert await notified(session, world.co_sup) == ["approval_waiting"]


async def test_step_only_fields_belong_to_their_step(session, world):
    await session.execute(
        update(ApprovalChain)
        .where(ApprovalChain.item_type == "thesis_submission")
        .values(steps=[{"kind": "library"}, {"kind": "exam_office"}])
    )
    ctx = await make_ctx(session, world.s_a2, "thesis_submission")
    await workflow.submit(session, await as_(session, world.scholar_a2), ctx)
    await workflow.assert_step_field(session, await as_(session, world.library), ctx, "library")
    with pytest.raises(ApiError):
        await workflow.assert_step_field(
            session, await as_(session, world.exam_office), ctx, "exam_office"
        )


async def test_department_step_falls_back_to_nearest_unit_with_a_head(session, world):
    # A2 has a HoD; remove A1's people and the item should notify the Dean of School A.
    from app.models import RoleAssignment

    await session.execute(
        update(RoleAssignment)
        .where(RoleAssignment.unit_id == world.a1.id)
        .values(deleted_at=RoleAssignment.created_at)
    )
    ctx = await make_ctx(session, world.s_a1b)
    assert await workflow.step_actor_ids(session, ctx, "department", world.sup_a2.id) == [
        world.dean_a.id
    ]
