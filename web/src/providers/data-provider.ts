"use client";

/** Refine data provider over the existing api() fetch wrapper (keeps the
 * 401-refresh-replay). Wire format is our own: ?sort=-field&k=v equality params,
 * never Refine array params on the wire. */

import type { CrudFilter, DataProvider } from "@refinedev/core";

import { api } from "@/lib/api";

interface PageShape<T> {
	items: T[];
	total: number;
	page: number;
	per_page: number;
}

function toQuery(resource: string, params: {
	pagination?: { currentPage?: number; pageSize?: number } | false;
	sorters?: { field: string; order: "asc" | "desc" }[];
	filters?: CrudFilter[];
	meta?: Record<string, unknown>;
}): string {
	const q = new URLSearchParams();
	if (params.pagination !== false) {
		q.set("page", String(params.pagination?.currentPage ?? 1));
		q.set("per_page", String(params.pagination?.pageSize ?? 20));
	}
	for (const sorter of params.sorters ?? []) {
		q.set("sort", sorter.order === "desc" ? `-${sorter.field}` : sorter.field);
	}
	for (const f of params.filters ?? []) {
		if ("field" in f && f.operator === "eq" && f.value !== undefined && f.value !== null && f.value !== "") {
			q.set(f.field, String(f.value));
		}
		// ponytail: eq-only; the API is equality-only too — add operators when it does
	}
	for (const [key, value] of Object.entries(params.meta ?? {})) {
		if (value !== undefined && value !== null && value !== "") q.set(key, String(value));
	}
	return `/${resource}?${q}`;
}

export const dataProvider: DataProvider = {
	getList: async ({ resource, pagination, sorters, filters, meta }) => {
		const page = await api<PageShape<Record<string, unknown>>>(
			toQuery(resource, { pagination, sorters, filters, meta }),
		);
		return { data: page.items, total: page.total };
	},
	getOne: async ({ resource, id }) => {
		const data = await api<Record<string, unknown>>(`/${resource}/${id}`);
		return { data };
	},
	create: async ({ resource, variables }) => {
		const data = await api<Record<string, unknown>>(`/${resource}`, {
			method: "POST",
			body: JSON.stringify(variables),
		});
		return { data };
	},
	update: async ({ resource, id, variables }) => {
		const data = await api<Record<string, unknown>>(`/${resource}/${id}`, {
			method: "PATCH",
			body: JSON.stringify(variables),
		});
		return { data };
	},
	deleteOne: async ({ resource, id }) => {
		await api(`/${resource}/${id}`, { method: "DELETE" });
		return { data: undefined as never };
	},
	getApiUrl: () => "",
	// custom: arbitrary API call — stats, timeline, comments, attachments, workflow
	custom: async ({ url, method, payload, query }) => {
		const qs = query ? `?${new URLSearchParams(Object.entries(query).map(([k, v]) => [k, String(v)]))}` : "";
		const data = await api<Record<string, unknown>>(`${url}${qs}`, {
			method,
			...(payload ? { body: JSON.stringify(payload), headers: { "Content-Type": "application/json" } } : {}),
		});
		return { data };
	},
	optionalMethods: {}, // ponytail: getMany/createMany/updateMany/deleteOne omitted — nothing uses them
} as DataProvider;