"""Sorting and totals for paged lists (UX_FLOWS "Long lists"): ?sort=key ascending, ?sort=-key
descending, keys taken from each list's own whitelist. Sorting happens before LIMIT/OFFSET, so
"Show more" continues the same order; the row id is always the last key, so rows with equal
values never repeat or vanish between pages. `page_of` runs one page and reports how many rows
match in all, in the X-Total-Count header, so the list body stays a plain array."""

from collections.abc import Mapping, Sequence
from typing import Annotated, Any

from fastapi import Query, Response
from sqlalchemy import Result, Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.errors import ApiError

Sort = Annotated[str | None, Query(max_length=40, pattern=r"^-?[a-z_]+$")]


def ordered(
    stmt: Select[Any],
    sort: str | None,
    columns: Mapping[str, ColumnElement[Any] | tuple[ColumnElement[Any], ...]],
    default: Sequence[ColumnElement[Any]],
    row_id: ColumnElement[Any],
) -> Select[Any]:
    """`stmt` ordered by the requested column (one expression, or a tuple sorted together, e.g.
    year then half-year), or by the list's default order without one."""
    if not sort:
        return stmt.order_by(*default, row_id)
    key = sort.removeprefix("-")
    column = columns.get(key)
    if column is None:
        raise ApiError(
            422,
            "invalid_sort",
            f"This list cannot be sorted by {key}.",
            {"allowed": sorted(columns)},
        )
    parts = column if isinstance(column, tuple) else (column,)
    desc = sort.startswith("-")
    return stmt.order_by(*((c.desc() if desc else c.asc()).nulls_last() for c in parts), row_id)


def ranked(column: ColumnElement[Any], values: Sequence[str]) -> ColumnElement[int]:
    """A text column ranked in the order its values are listed (stages, states), not A-Z."""
    return case({v: i for i, v in enumerate(values)}, value=column, else_=len(values))


TOTAL_HEADER = "X-Total-Count"


async def page_of(
    session: AsyncSession, response: Response, stmt: Select[Any], limit: int, offset: int
) -> Result[Any]:
    """One page of `stmt`; the count of all rows it matches (same scope and filters) goes in
    the response header."""
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    response.headers[TOTAL_HEADER] = str(total)
    return await session.execute(stmt.limit(limit).offset(offset))
