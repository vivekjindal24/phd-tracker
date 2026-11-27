import type { PrivacyNotice } from "@/lib/types";

/** The notice as the university wrote it (or Anveshan's draft), who to write to, and the outside
 *  services this installation sends data to. Plain text: paragraphs split on blank lines. */
export function NoticeText({ notice }: { notice: PrivacyNotice }) {
  return (
    <div className="privacy-notice">
      {notice.text.split(/\n\s*\n/).map((para, i) => <p key={i}>{para}</p>)}
      <h3>Who to write to</h3>
      <p>
        {notice.officer
          ? <>{notice.officer.name}, <a href={`mailto:${notice.officer.email}`}>{notice.officer.email}</a> — the University&apos;s privacy officer.</>
          : "The University's administrators, through My account → Your data, until it names a privacy officer."}
      </p>
      <h3>Outside services that receive data</h3>
      <ul>
        {notice.processors.map((p) => (
          <li key={p.service}><strong>{p.service}</strong> <span className="muted">({p.where})</span>: {p.what}</li>
        ))}
      </ul>
    </div>
  );
}
