"use client";

/** Server-backed data table: sortable headers (server sort via onSort), row links,
 * pagination footer, loading skeleton, empty/error states. */

import { type ReactNode } from "react";

import { Button, EmptyState, ErrorState, SkeletonRows } from "./ui";

export type Column<T> = {
	key: string;
	head: string;
	/** server-sortable column name (SORTABLE whitelist on the API); omit for unsortable */
	sort?: string;
	cell: (row: T) => ReactNode;
};

type DataTableProps<T> = {
	columns: Column<T>[];
	rows: T[];
	rowId: (row: T) => string;
	loading?: boolean;
	error?: string;
	empty?: string;
	sort?: { field: string; order: "asc" | "desc" };
	onSort?: (sort: { field: string; order: "asc" | "desc" }) => void;
	onRowClick?: (row: T) => void;
	footer?: ReactNode;
};

export function DataTable<T>({
	columns,
	rows,
	rowId,
	loading,
	error,
	empty = "No records yet.",
	sort,
	onSort,
	onRowClick,
	footer,
}: DataTableProps<T>) {
	if (loading && rows.length === 0) return <SkeletonRows cols={columns.length} />;
	if (error) return <ErrorState>{error}</ErrorState>;
	if (rows.length === 0) return <EmptyState>{empty}</EmptyState>;

	function toggle(col: Column<T>) {
		if (!onSort || !col.sort) return;
		if (sort?.field === col.sort) {
			onSort({ field: col.sort, order: sort.order === "asc" ? "desc" : "asc" });
		} else {
			onSort({ field: col.sort!, order: "asc" });
		}
	}

	return (
		<div className="table-wrap">
			<table>
				<thead>
					<tr>
						{columns.map((col) => {
							const active = sort && col.sort === sort.field;
							const arrow = active ? (sort!.order === "asc" ? " ↑" : " ↓") : "";
							if (!col.sort) {
								return <th key={col.key}>{col.head}</th>;
							}
							return (
								<th
									key={col.key}
									className="sortable"
									scope="col"
									aria-sort={active ? (sort!.order === "asc" ? "ascending" : "descending") : "none"}
									onClick={() => toggle(col)}
								>
									{col.head}
									{arrow}
								</th>
							);
						})}
					</tr>
				</thead>
				<tbody>
					{rows.map((row) => (
						<tr
							key={rowId(row)}
							className={onRowClick ? "rowlink" : undefined}
							onClick={onRowClick ? () => onRowClick(row) : undefined}
						>
							{columns.map((col) => (
								<td key={col.key}>{col.cell(row)}</td>
							))}
						</tr>
					))}
				</tbody>
			</table>
			{footer && (
				<div
					style={{
						display: "flex",
						alignItems: "center",
						justifyContent: "space-between",
						gap: "0.75rem",
						padding: "0.6rem 0.9rem",
						borderTop: "1px solid var(--rule)",
						fontSize: "var(--text-sm)",
						color: "var(--ink-soft)",
						flexWrap: "wrap",
					}}
				>
					{footer}
				</div>
			)}
		</div>
	);
}

export function Pager({
	page,
	perPage,
	total,
	onPage,
}: {
	page: number;
	perPage: number;
	total: number;
	onPage: (page: number) => void;
}) {
	const last = Math.max(1, Math.ceil(total / perPage));
	return (
		<>
			<span>
				{total === 0 ? "No records" : `${(page - 1) * perPage + 1}–${Math.min(page * perPage, total)} of ${total}`}
			</span>
			<span style={{ display: "flex", gap: "0.25rem" }}>
				<Button size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
					← Prev
				</Button>
				<Button size="sm" disabled={page >= last} onClick={() => onPage(page + 1)}>
					Next →
				</Button>
			</span>
		</>
	);
}