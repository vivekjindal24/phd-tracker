import type { ButtonHTMLAttributes, ReactNode } from "react";
import "./ui.css";

type ButtonKind = "primary" | "secondary" | "ghost" | "danger" | "plain";

export function Button({
  kind = "plain",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { kind?: ButtonKind }) {
  const kindClass = kind === "plain" ? "" : ` btn-${kind}`;
  return <button type={type} className={`btn${kindClass} ${className}`.trim()} {...props} />;
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      {label}
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function ErrorText({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p className="error-text" role="alert">
      {children}
    </p>
  );
}

export function Card({
  children,
  className = "",
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article" | "form";
}) {
  return <Tag className={`clay card ${className}`.trim()}>{children}</Tag>;
}

export function PageHeader({
  title,
  eyebrow,
  actions,
}: {
  title: string;
  eyebrow?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </header>
  );
}

export function Switch({
  checked,
  label,
  onChange,
  disabled,
}: {
  checked: boolean;
  label: string;
  onChange: (next: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className="switch"
      disabled={disabled}
      onClick={() => onChange(!checked)}
    />
  );
}

/** Registers and lists: one clay card, flat readable rows inside (DESIGN_SYSTEM.md §4). */
export function ShowMore({
  hasMore,
  more,
  shown,
  total,
}: {
  hasMore: boolean;
  more: () => void;
  shown?: number;
  total?: number | null;
}) {
  // The count of everything that matches the search and filters, not only the rows loaded.
  const count = total != null && total > 0 && shown != null && (
    <p className="muted" role="status">Showing {Math.min(shown, total)} of {total}</p>
  );
  if (!hasMore && !count) return null;
  return (
    <div className="show-more">
      {count}
      {hasMore && <Button kind="ghost" onClick={more}>Show more</Button>}
    </div>
  );
}

/** Server-side column sorting (API `sort=key` / `sort=-key`): `keys` gives each column's sort key,
 *  null for a column that does not sort; "" is the list's default order. */
export type ColumnSort = { by: string; keys: (string | null)[]; onChange: (by: string) => void };

// Ascending, then descending, then back to the list's default order.
const nextSort = (by: string, key: string) => (by === key ? `-${key}` : by === `-${key}` ? "" : key);

function HeadCell({ title, sortKey, sort }: { title: string; sortKey?: string | null; sort?: ColumnSort }) {
  if (!sort || !sortKey) return <th scope="col">{title}</th>;
  const dir = sort.by === sortKey ? "ascending" : sort.by === `-${sortKey}` ? "descending" : undefined;
  return (
    <th scope="col" aria-sort={dir}>
      <button type="button" className="th-sort" onClick={() => sort.onChange(nextSort(sort.by, sortKey))}>
        {title}
        <span aria-hidden="true" className="th-sort-mark">{dir === "ascending" ? "↑" : dir === "descending" ? "↓" : "↕"}</span>
      </button>
    </th>
  );
}

export function Table({
  head,
  children,
  empty,
  label,
  sort,
}: {
  head: string[];
  children: ReactNode;
  empty?: ReactNode;
  label: string;
  sort?: ColumnSort;
}) {
  const hasRows = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return (
    <div className="table-card clay">
      {hasRows ? (
        <table aria-label={label}>
          <thead>
            <tr>
              {head.map((h, i) => (
                <HeadCell key={h || i} title={h} sortKey={sort?.keys[i]} sort={sort} />
              ))}
            </tr>
          </thead>
          <tbody>{children}</tbody>
        </table>
      ) : (
        empty
      )}
    </div>
  );
}
