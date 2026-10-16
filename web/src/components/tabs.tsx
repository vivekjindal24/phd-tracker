"use client";

/** Tabs + the stage-distribution bar chart. Zero chart libraries — bars are CSS widths. */

import { type ReactNode, useState } from "react";

export function Tabs({ tabs }: { tabs: { id: string; label: string; panel: ReactNode }[] }) {
	const [active, setActive] = useState(tabs[0]?.id);
	return (
		<div>
			<div className="tabs-list" role="tablist">
				{tabs.map((tab) => (
					<button
						key={tab.id}
						type="button"
						role="tab"
						aria-selected={tab.id === active}
						onClick={() => setActive(tab.id)}
					>
						{tab.label}
					</button>
				))}
			</div>
			{tabs.map((tab) => (
				<div key={tab.id} className="tabs-panel" role="tabpanel" hidden={tab.id !== active}>
					{tab.panel}
				</div>
			))}
		</div>
	);
}

export function BarChart({ data }: { data: { label: string; count: number }[] }) {
	const max = Math.max(1, ...data.map((d) => d.count));
	return (
		<div className="bar-chart">
			{data.length === 0 && <p className="soft">No distribution to show yet.</p>}
			{data.map((d) => (
				<div className="bar-row" key={d.label}>
					<span>{d.label}</span>
					<span className="bar-track" role="presentation">
						<span className="bar-fill" style={{ width: `${(d.count / max) * 100}%` }} />
					</span>
					<span className="bar-count">{d.count}</span>
				</div>
			))}
		</div>
	);
}