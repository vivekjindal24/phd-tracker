"use client";

import { Refine } from "@refinedev/core";
import routerProvider from "@refinedev/nextjs-router";
import { type ReactNode } from "react";

import { authProvider } from "@/providers/auth-provider";
import { dataProvider } from "@/providers/data-provider";

/** Mounted in the root layout so login and (app) pages share one auth/data context. */

export function RefineRoot({ children }: { children: ReactNode }) {
	return (
		<Refine
			routerProvider={routerProvider}
			dataProvider={dataProvider}
			authProvider={authProvider}
			resources={[{ name: "scholars" }, { name: "supervisors" }, { name: "meetings" }, { name: "reports" }, { name: "milestones" }]}
			options={{ syncWithLocation: false, disableTelemetry: true }}
		>
			{children}
		</Refine>
	);
}