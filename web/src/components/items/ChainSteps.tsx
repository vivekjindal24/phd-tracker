import type { ItemView } from "@/lib/types";
import "./items.css";

/** The approval chain as clay step chips: done / current / upcoming (DESIGN_SYSTEM.md §4). */
export function ChainSteps({ chain }: { chain: ItemView["chain"] }) {
  return (
    <ol className="chain-track" aria-label="Approval chain">
      {chain.map((step, i) => (
        <li key={`${step.kind}-${i}`} className={`chain-chip chain-${step.status}`}
          aria-current={step.status === "current" ? "step" : undefined}>
          <span className="chain-dot" aria-hidden="true">{step.status === "done" ? "✓" : i + 1}</span>
          {step.label}
          <span className="visually-hidden"> ({step.status})</span>
        </li>
      ))}
    </ol>
  );
}
