"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useTable } from "@refinedev/core";

import { api, ApiError } from "@/lib/api";
import { Badge, ErrorState, PageHeader, queryError } from "@/components/ui";
import { Column, DataTable, Pager } from "@/components/data-table";
import { AttachmentsPanel, CommentThread } from "@/components/record-panels";
import { Tabs } from "@/components/tabs";

interface Scholar {
	id: string;
	scholar_name: string;
	roll_number: string;
	scholar_email: string | null;
	department: string;
	admission_date: string;
	stage: string;
	github_url: string | null;
}

interface TimelineEvent {
	kind: "meeting" | "report" | "transition" | "milestone" | "comment";
	at: string;
	data: Record<string, unknown>;
}

const KIND_LABEL: Record<TimelineEvent["kind"], string> = {
	meeting: "Meeting",
	report: "Report filed",
	transition: "Workflow",
	milestone: "Milestone",
	comment: "Comment",
};

const str = (v: unknown) => (v == null ? "" : String(v));

function eventBody(e: TimelineEvent): string {
	switch (e.kind) {
		case "meeting":
			return str(e.data.agenda) || "Supervision meeting";
		case "report":
			return `APR ${str(e.data.report_year)} · ${str(e.data.period)}`;
		case "transition":
			return `Report moved ${str(e.data.from_state) || "—"} → ${str(e.data.to_state)}`;
		case "milestone":
			return `${str(e.data.milestone_type)}${e.data.resolution_date ? ` · resolved ${str(e.data.resolution_date)}` : ""}`;
		case "comment":
			return str(e.data.body);
	}
}

export default function ScholarDetailPage() {
	const params = useParams<{ id: string }>();
	const router = useRouter();
	const id = params.id;
	const [scholar, setScholar] = useState<Scholar | null>(null);
	const [events, setEvents] = useState<TimelineEvent[] | null>(null);
	const [error, setError] = useState("");

	const load = useCallback(async () => {
		try {
			setScholar(await api<Scholar>(`/scholars/${id}`));
			const tl = await api<{ events: TimelineEvent[] }>(`/scholars/${id}/timeline`);
			setEvents(tl.events);
		} catch (err) {
			setError(err instanceof ApiError ? err.message : "Could not load the scholar");
		}
	}, [id]);

	useEffect(() => {
		if (id) void load();
	}, [id, load]);

	// each tab is its own scoped server query — scholar_id is a permanent filter
	const reports = useTable({
		resource: "reports",
		pagination: { pageSize: 10 },
		filters: { permanent: [{ field: "scholar_id", operator: "eq", value: id }] },
		sorters: { initial: [{ field: "created_at", order: "desc" }] },
	});
	const meetings = useTable({
		resource: "meetings",
		pagination: { pageSize: 10 },
		filters: { permanent: [{ field: "scholar_id", operator: "eq", value: id }] },
		sorters: { initial: [{ field: "meeting_date", order: "desc" }] },
	});
	const milestones = useTable({
		resource: "milestones",
		pagination: { pageSize: 10 },
		filters: { permanent: [{ field: "scholar_id", operator: "eq", value: id }] },
		sorters: { initial: [{ field: "created_at", order: "desc" }] },
	});

	if (error) {
		return (
			<>
				<PageHeader title="Scholar" />
				<ErrorState>{error}</ErrorState>
				<Link href="/scholars">← Back to scholars</Link>
			</>
		);
	}
	if (!scholar) return <p className="soft">Loading…</p>;

	const reportCols: Column<Record<string, unknown>>[] = [
		{ key: "year", head: "Year", sort: "report_year", cell: (r) => String(r.report_year) },
		{ key: "period", head: "Period", cell: (r) => str(r.period) },
		{ key: "state", head: "State", sort: "state", cell: (r) => <Badge value={str(r.state)} /> },
	];
	const meetingCols: Column<Record<string, unknown>>[] = [
		{ key: "date", head: "Date", sort: "meeting_date", cell: (m) => str(m.meeting_date) },
		{ key: "agenda", head: "Agenda", cell: (m) => str(m.agenda) || "—" },
		{ key: "actions", head: "Action items", cell: (m) => str(m.action_items) || "—" },
	];
	const milestoneCols: Column<Record<string, unknown>>[] = [
		{ key: "type", head: "Milestone", sort: "milestone_type", cell: (m) => str(m.milestone_type) },
		{ key: "status", head: "Status", sort: "status", cell: (m) => <Badge value={str(m.status)} /> },
		{ key: "res", head: "Resolution", sort: "resolution_date", cell: (m) => str(m.resolution_date) || "—" },
	];

	function tableBlock(
		q: ReturnType<typeof useTable>,
		cols: Column<Record<string, unknown>>[],
		empty: string,
		onRowClick?: (row: Record<string, unknown>) => void,
	) {
		return (
			<DataTable
				columns={cols}
				rows={(q.tableQuery.data?.data as Record<string, unknown>[] | undefined) ?? []}
				rowId={(r) => str(r.id)}
				loading={q.tableQuery.isLoading}
				error={queryError(q.tableQuery.error)}
				empty={empty}
				sort={q.sorters[0]}
				onSort={(s) => q.setSorters([s])}
				onRowClick={onRowClick}
				footer={
					<Pager
						page={q.currentPage}
						perPage={q.pageSize}
						total={q.tableQuery.data?.total ?? 0}
						onPage={q.setCurrentPage}
					/>
				}
			/>
		);
	}

	return (
		<>
			<PageHeader
				title={scholar.scholar_name}
				sub={`${scholar.roll_number} · ${scholar.department} · admitted ${scholar.admission_date}`}
				actions={
					<Link href="/scholars" className="btn btn-ghost btn-sm">
						← Scholars
					</Link>
				}
			/>
			<div className="toolbar">
				<Badge value={scholar.stage} tone="accent" />
				{scholar.scholar_email && <span className="soft">{scholar.scholar_email}</span>}
				{scholar.github_url && <span className="soft">{scholar.github_url}</span>}
			</div>
			<Tabs
				tabs={[
					{
						id: "timeline",
						label: "Timeline",
						panel:
							events === null ? (
								<p className="soft">Loading…</p>
							) : events.length === 0 ? (
								<p className="soft">No history yet.</p>
							) : (
								<ul className="timeline">
									{events.map((e, i) => (
										// biome-ignore lint/suspicious/noArrayIndexKey: server-ordered feed, no stable id exists
										<li key={i}>
											<span className="tl-at">{new Date(e.at).toLocaleDateString()}</span>
											<div className="tl-body">
												<span className="tl-kind">{KIND_LABEL[e.kind]}</span>
												<p>{eventBody(e)}</p>
											</div>
										</li>
									))}
								</ul>
							),
					},
					{
						id: "reports",
						label: "Reports",
						panel: tableBlock(reports, reportCols, "No reports yet.", (r) =>
							router.push(`/reports/${str(r.id)}`),
						),
					},
					{ id: "meetings", label: "Meetings", panel: tableBlock(meetings, meetingCols, "No meetings yet.") },
					{
						id: "milestones",
						label: "Milestones",
						panel: tableBlock(milestones, milestoneCols, "No milestones yet."),
					},
					{ id: "comments", label: "Comments", panel: <CommentThread tableName="scholars" recordId={id} /> },
					{ id: "documents", label: "Documents", panel: <AttachmentsPanel tableName="scholars" recordId={id} /> },
				]}
			/>
		</>
	);
}