import Link from "next/link";
import { Owl, OwlMark } from "@/components/brand/Owl";
import "@/components/ui/ui.css";
import "./landing.css";

/** The public front page at `/` (UX_FLOWS.md Flow 0): what Anveshan is, and the way in to log in. */

const ICONS = {
  check: "M5 12.5l4.2 4.2L19 7",
  cross: "M7 7l10 10M17 7L7 17",
  arrow: "M5 12h13M13 6l6 6-6 6",
  door: "M5 21V5a2 2 0 012-2h8l4 4v14M3 21h18M14 12h.01",
  book: "M4 5.5C4 4.7 4.7 4 5.5 4H11v16H5.5A1.5 1.5 0 014 18.5zM20 5.5c0-.8-.7-1.5-1.5-1.5H13v16h5.5a1.5 1.5 0 001.5-1.5z",
  seminar: "M3 4h18v11H3zM8 20l4-5 4 5M7 9h6M7 12h10",
  paper: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6",
  thesis: "M6 3h11a1 1 0 011 1v16a1 1 0 01-1 1H6a2 2 0 01-2-2V5a2 2 0 012-2zM4 18a2 2 0 012-2h12M9 8h5",
  viva: "M12 3l9 4-9 4-9-4zM6 9v5c0 1.7 2.7 3 6 3s6-1.3 6-3V9M21 7v6",
  deposit: "M12 3v11M7 9l5 5 5-5M4 16v3a2 2 0 002 2h12a2 2 0 002-2v-3",
  lock: "M6 11h12v9H6zM8.5 11V8a3.5 3.5 0 017 0v3",
  server: "M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01",
  trail: "M12 7v5l3 2M21 12a9 9 0 11-3-6.7M21 4v4h-4",
} as const;

type IconName = keyof typeof ICONS;

function Icon({ name }: { name: IconName }) {
  return (
    <svg className="lp-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d={ICONS[name]} />
    </svg>
  );
}

const CHAIN = [
  { who: "Scholar", what: "Submitted with seminar marks attached", when: "12 Dec", state: "done" },
  { who: "Supervisor", what: "Dr. R. Iyer approved: “Good progress on Ch. 3”", when: "14 Dec", state: "done" },
  { who: "Department", what: "Waiting for the HoD or the department admin", when: "3 days", state: "current" },
  { who: "Research Office", what: "Final approval", when: "Next", state: "upcoming" },
] as const;

const TODAY = [
  ["Progress reports", "are passed around by hand and nobody knows whose desk they are on."],
  ["RDC / DPGC decisions", "live in minute books and a resolution number is hard to find."],
  ["Publications", "are checked for Scopus and UGC-CARE indexing only at thesis time."],
  ["Coursework grades", "and fellowship money sit in separate office spreadsheets."],
  ["Audits", "mean weeks of collecting files from every department."],
];

const WITH_ANVESHAN = [
  ["Every report shows its step,", "who acted, when, and what they said."],
  ["The committee register is searchable", "by scholar, resolution number or date."],
  ["The Library verifies each paper", "when it is added, with journal, indexing and DOI."],
  ["Coursework, CGPA, fellowships and grants", "sit on the same scholar record."],
  ["Audit files are an export:", "the register as PDF or CSV, any scholar's full record as a PDF."],
];

const ROLES = [
  {
    tag: "Scholar",
    tone: "badge-draft",
    size: "wide",
    title: "A clear trail from day one",
    text: "Meetings, drafts with supervisor feedback, progress reports and seminar marks in one timeline. They always know their stage and their next deadline.",
    points: ["To-do list from seminar feedback", "Reminders 14 days before a report is due"],
  },
  {
    tag: "Supervisor",
    tone: "badge-approved",
    size: "wide",
    title: "One queue for every scholar",
    text: "Approve or send back everything waiting for them in one sitting. Meeting minutes get logged once and stay private unless they choose to share.",
    points: [
      "Load shown against the UGC cap",
      "AI drafts to-do points from panel comments; they edit and finalise",
    ],
  },
  {
    tag: "HoD & Dean",
    tone: "badge-in_review",
    size: "narrow",
    title: "The unit at a glance",
    text: "Scholars by stage, overdue reports, items stuck more than 14 days, and supervisor loads. Deans get the same view per department.",
    points: [],
  },
  {
    tag: "Research & Exam Office",
    tone: "badge-sent_back",
    size: "narrow",
    title: "Final word, kept on record",
    text: "Final approvals, the RDC register, coursework grades and clearance, thesis receipt, examiners and viva, all with history.",
    points: [],
  },
  {
    tag: "Library",
    tone: "badge-draft",
    size: "narrow",
    title: "Verification at its step",
    text: "Checks each publication's journal, indexing (Scopus, Web of Science, UGC-CARE) and DOI. Records the thesis plagiarism score and the Shodhganga deposit.",
    points: [],
  },
];

const JOURNEY: { icon: IconName; title: string; text: string }[] = [
  { icon: "door", title: "Admission", text: "NET/JRF, GATE or entrance test, interview outcome. One click creates the scholar and their login." },
  { icon: "book", title: "Coursework", text: "Grades, credits and CGPA, cleared through Department and Exam Office." },
  { icon: "seminar", title: "Seminars & reports", text: "Six-monthly seminars with rubric marks, then the progress report through its chain." },
  { icon: "paper", title: "Publications", text: "Papers, conferences and talks, with indexing verified by the Library." },
  { icon: "thesis", title: "Thesis", text: "Drafts with versions, then submission with the plagiarism certificate." },
  { icon: "viva", title: "Examiners & viva", text: "Examiner reports, viva panel and outcome, with examiner names kept confidential." },
  { icon: "deposit", title: "Shodhganga", text: "Deposit date, handle and certificate recorded by the Library." },
];

const RULES = [
  ["Supervisor caps", "Professor 8, Associate 6, Assistant 4. Assigning beyond the cap is refused."],
  ["Maximum duration", "Six years, with allowed extensions, relaxation and leave. Warns as the limit nears."],
  ["Coursework", "Minimum credits and CGPA checked before clearance."],
  ["Six-monthly review", "Progress seminars set the report due date. Reminders go out 14 days before."],
  ["Plagiarism check", "The Library records tool, score and certificate at its step of the thesis chain."],
  ["Committee decisions", "RDC / DPGC / DRC / RAC register with resolution numbers and dates."],
];

const EXPORTS = [
  ["PDF", "Progress report", "With the full approval history"],
  ["PDF · CSV", "RDC / committee register", "Filtered by unit, period or milestone"],
  ["PDF", "Scholar's complete record", "For the registrar or an external committee"],
  ["PDF", "Unit summary", "For HoDs and Deans"],
];

const CORE_MODULES = [
  "Directory & org tree",
  "Meetings",
  "Progress reports & seminars",
  "RDC register",
  "Dashboards & search",
  "Notifications & exports",
];

const OPTIONAL_MODULES = [
  "Publications",
  "Conferences & talks",
  "Documents & thesis",
  "Coursework",
  "Admissions",
  "Fellowships",
  "Research projects",
  "Grant ledger",
];

const FAQ = [
  ["Our committee is called DRC, not RDC. Does that matter?", "No. The register records the approval body (RDC, DPGC, DRC or RAC), the resolution number and the date. That pattern works across universities whatever the committee is called."],
  ["Can we match the approval steps to our ordinance?", "Yes. The root admin sets one chain per item type: progress report, publication, coursework clearance and thesis submission. Changing a chain affects only items submitted after the change, so nothing in flight is disturbed."],
  ["Do external examiners need an account?", "No. Examiners and outside RAC members get PDFs and email. The Exam Office records their reports, and examiner names stay confidential until the viva outcome is recorded."],
  ["Is AI required? Where does our data go?", "AI is optional. It only drafts to-do points from seminar comments, and the supervisor edits and approves every point. On your server it can run on a local model, so seminar comments never leave campus. Without AI, supervisors write the points themselves."],
  ["Does it replace our ERP or accounts software?", "No. Anveshan covers the research side: scholars, committees, reports, publications and theses. The grant ledger records expenses and utilisation certificates, but it does not make payments."],
  ["Will it work on phones?", "Yes. Scholars and supervisors can log a meeting, check a report's step or approve an item from a phone browser. Nothing needs to be installed."],
];

function LoginButton({ label = "Log in" }: { label?: string }) {
  return (
    <Link className="btn btn-primary lp-btn" href="/login">
      {label} <Icon name="arrow" />
    </Link>
  );
}

function SectionHead({ id, eyebrow, title, lede }: { id: string; eyebrow: string; title: string; lede?: string }) {
  return (
    <div className="lp-head">
      <span className="lp-eyebrow">{eyebrow}</span>
      <h2 id={id}>{title}</h2>
      {lede && <p className="lp-lede">{lede}</p>}
    </div>
  );
}

function Hero() {
  return (
    <section className="lp-hero" aria-labelledby="lp-hero-heading">
      <div className="lp-wrap lp-hero-grid">
        <div className="lp-hero-copy">
          <span className="lp-reg">
            <b>UGC 2022</b> Built around the PhD Regulations
          </span>
          <h1 id="lp-hero-heading">
            Every PhD in your university, <em>in one place.</em>
          </h1>
          <p className="lp-lede">
            Anveshan is the research system scholars and supervisors open every week. HoDs, Deans, the
            research office, the exam office and the library each see their part, live. The UGC records
            come from that daily work, not from a rush before the audit.
          </p>
          <div className="lp-cta">
            <LoginButton label="Log in to Anveshan" />
            <a className="btn lp-btn" href="#pilot">
              Start with one department
            </a>
          </div>
          <p className="lp-note">One installation per university, on your own server. Your data stays on campus.</p>
        </div>
        <div className="lp-hero-visual">
          <article className="clay lp-chain" aria-label="Example: a progress report moving through its approval chain">
            <div className="lp-chain-top">
              <div>
                <div className="lp-chain-kind">Six-monthly progress report · example</div>
                <div className="lp-chain-title">Jul–Dec 2026 · Priya Sharma</div>
                <div className="lp-chain-meta">Roll no. PHD/CHEM/2024/017 · Dept. of Chemistry</div>
              </div>
              <span className="badge badge-in_review">In review · Department</span>
            </div>
            <ol className="lp-steps">
              {CHAIN.map((s, i) => (
                <li key={s.who} className={`lp-step lp-step-${s.state}`}>
                  <span className="lp-step-dot">{s.state === "done" ? <Icon name="check" /> : i + 1}</span>
                  <div>
                    <div className="lp-step-who">{s.who}</div>
                    <div className="lp-step-what">{s.what}</div>
                  </div>
                  <span className={s.state === "current" ? "lp-wait" : "lp-step-when"}>{s.when}</span>
                </li>
              ))}
            </ol>
          </article>
          <p className="lp-bubble" aria-hidden="true">
            No more “where is my approval?” Everyone sees the step.
          </p>
          <div className="lp-hero-owl">
            <Owl pose="reading" size={150} />
          </div>
        </div>
      </div>
    </section>
  );
}

function Problem() {
  return (
    <section className="lp-band lp-band-deep" aria-labelledby="lp-problem">
      <div className="lp-wrap">
        <SectionHead
          id="lp-problem"
          eyebrow="The problem"
          title="A PhD still runs on WhatsApp, email, paper diaries and Excel."
          lede="Meetings go unrecorded. Progress reports are copied together the night before. Committee approvals sit in minute books nobody can search. Above the supervisor, nobody can see where a scholar stands without picking up the phone."
        />
        <div className="clay lp-compare">
          <div className="lp-compare-col lp-today">
            <h3>Today</h3>
            <ul>
              {TODAY.map(([lead, rest]) => (
                <li key={lead}>
                  <Icon name="cross" />
                  <span>
                    <b>{lead}</b> {rest}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="lp-compare-col lp-with">
            <h3>With Anveshan</h3>
            <ul>
              {WITH_ANVESHAN.map(([lead, rest]) => (
                <li key={lead}>
                  <Icon name="check" />
                  <span>
                    <b>{lead}</b> {rest}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

function Roles() {
  return (
    <section className="lp-band" id="roles" aria-labelledby="lp-roles">
      <div className="lp-wrap">
        <SectionHead
          id="lp-roles"
          eyebrow="Who uses it"
          title="Everyone logs in. Each person sees exactly their part."
          lede="A HoD sees their department, a Dean their faculty, the central offices the whole university. A HoD of Physics never sees a Chemistry scholar. The server enforces this, not just the screen."
        />
        <div className="lp-bento">
          {ROLES.map((r) => (
            <article key={r.tag} className={`clay lp-role lp-role-${r.size}`}>
              <span className={`badge ${r.tone}`}>{r.tag}</span>
              <h3>{r.title}</h3>
              <p>{r.text}</p>
              {r.points.length > 0 && (
                <ul>
                  {r.points.map((p) => (
                    <li key={p}>{p}</li>
                  ))}
                </ul>
              )}
            </article>
          ))}
        </div>
        <p className="lp-one-login">
          <span className="badge">One login, several roles</span> A professor who is also the HoD and the
          department admin sees one combined home page.
        </p>
      </div>
    </section>
  );
}

function Journey() {
  return (
    <section className="lp-band lp-band-deep" id="journey" aria-labelledby="lp-journey">
      <div className="lp-wrap">
        <SectionHead
          id="lp-journey"
          eyebrow="The PhD journey"
          title="From admission to Shodhganga, on one record."
          lede="Each stage is a record the next one builds on, so the scholar's file is complete when the degree is awarded."
        />
        <ol className="lp-journey">
          {JOURNEY.map((s, i) => (
            <li key={s.title} className="lp-stage">
              <span className="lp-stage-dot">
                <Icon name={s.icon} />
              </span>
              <span className="lp-stage-num">Stage {i + 1}</span>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Ugc() {
  return (
    <section className="lp-band" id="ugc" aria-labelledby="lp-ugc">
      <div className="lp-wrap lp-ugc">
        <div>
          <SectionHead
            id="lp-ugc"
            eyebrow="UGC 2022 Regulations"
            title="Rules are checked when work happens, not discovered at the audit."
            lede="Anveshan follows the UGC (Minimum Standards and Procedures for Award of PhD Degree) Regulations, 2022. It warns before a limit is crossed and blocks what must never happen."
          />
          <div className="clay lp-rules">
            <table>
              <caption>What the system checks</caption>
              <thead>
                <tr>
                  <th scope="col">Rule</th>
                  <th scope="col">How Anveshan handles it</th>
                </tr>
              </thead>
              <tbody>
                {RULES.map(([rule, how]) => (
                  <tr key={rule}>
                    <th scope="row">{rule}</th>
                    <td>{how}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="lp-exports">
          <span className="lp-eyebrow">Ready for the audit</span>
          <h3>Print-ready exports, for anyone with access</h3>
          <p className="muted">
            Each person can export what they are allowed to see. PDFs keep a print look and stay readable
            in black and white.
          </p>
          <ul>
            {EXPORTS.map(([kind, title, sub]) => (
              <li key={title} className="clay">
                <span className="lp-doc">{kind}</span>
                <div>
                  <b>{title}</b>
                  <span>{sub}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function Trust() {
  return (
    <section className="lp-band lp-band-deep" id="trust" aria-labelledby="lp-trust">
      <div className="lp-wrap">
        <SectionHead id="lp-trust" eyebrow="Data & privacy" title="Your university's records stay with your university." />
        <div className="lp-trust">
          <article className="clay lp-trust-item">
            <span className="lp-trust-ico">
              <Icon name="server" />
            </span>
            <h3>On your own server</h3>
            <p>
              Each university gets its own installation, database and file store. It runs on a campus
              server or NAS with nightly backups. No other university shares it.
            </p>
          </article>
          <article className="clay lp-trust-item">
            <span className="lp-trust-ico">
              <Icon name="lock" />
            </span>
            <h3>Minutes stay private</h3>
            <p>Supervisor–scholar meeting minutes are private by default. Others see only that a meeting took place.</p>
            <div className="lp-minutes" aria-label="Example of what an HoD sees for an unshared meeting">
              <div>
                <b>Meeting · 4 Nov 2026</b> · Priya Sharma with Dr. R. Iyer
              </div>
              <span className="lp-redacted" />
              <span className="lp-redacted lp-redacted-short" />
            </div>
          </article>
          <article className="clay lp-trust-item">
            <span className="lp-trust-ico">
              <Icon name="trail" />
            </span>
            <h3>Every change on record</h3>
            <p>
              Each approval, send-back and edit is logged with who did it and when. Approved items can't be
              changed by anyone. Nothing is ever hard-deleted.
            </p>
          </article>
        </div>
        <p className="lp-lede lp-after">
          Staff sign in with their university Google or Microsoft account. When IT closes a leaver's
          account, their access ends with it.
        </p>
      </div>
    </section>
  );
}

function Modules() {
  return (
    <section className="lp-band" aria-labelledby="lp-modules">
      <div className="lp-wrap">
        <SectionHead
          id="lp-modules"
          eyebrow="Modules"
          title="Turn on what your university needs."
          lede="The core is always on. The root admin switches on other modules, and anything switched off disappears from every screen."
        />
        <div className="lp-mods">
          <div className="lp-mod-label">Always on</div>
          <div className="lp-mod-row">
            {CORE_MODULES.map((m) => (
              <span key={m} className="clay lp-mod lp-mod-core">
                <span className="lp-toggle" aria-hidden="true" />
                {m}
              </span>
            ))}
          </div>
          <div className="lp-mod-label">Optional</div>
          <div className="lp-mod-row">
            {OPTIONAL_MODULES.map((m) => (
              <span key={m} className="clay lp-mod">
                <span className="lp-toggle" aria-hidden="true" />
                {m}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Pilot() {
  return (
    <section className="lp-band lp-band-deep" id="pilot" aria-labelledby="lp-pilot">
      <div className="lp-wrap">
        <SectionHead
          id="lp-pilot"
          eyebrow="Getting started"
          title="Start with one department. Grow to the whole university."
          lede="Your existing faculty, scholars and committee history come in from an Excel template. A dry run checks every row before anything is saved, so the department starts with its real data on the first day."
        />
        <div className="lp-plans">
          <article className="clay lp-plan lp-plan-feature">
            <span className="lp-plan-kind">Department</span>
            <h3>One department, fully running</h3>
            <div className="lp-price">
              ₹50,000 <small>/ year</small>
            </div>
            <ul>
              <li><Icon name="check" />All scholars, supervisors and the HoD of one department</li>
              <li><Icon name="check" />Research office, exam office and library steps included</li>
              <li><Icon name="check" />Help importing your existing records</li>
              <li><Icon name="check" />Installed on your server</li>
            </ul>
          </article>
          <article className="clay lp-plan">
            <span className="lp-plan-kind">University</span>
            <h3>Every school and department</h3>
            <div className="lp-price lp-price-quote">Quoted per university</div>
            <ul>
              <li><Icon name="check" />The full org tree: university, schools, departments</li>
              <li><Icon name="check" />Dean and leadership views: scholars at risk, time to completion by unit</li>
              <li><Icon name="check" />Approval chains set up to match your ordinance</li>
              <li><Icon name="check" />University Google or Microsoft sign-in</li>
            </ul>
            <p className="lp-note">Start with one department, then move to this plan once it has run for a semester.</p>
          </article>
        </div>
      </div>
    </section>
  );
}

function Faq() {
  return (
    <section className="lp-band" aria-labelledby="lp-faq">
      <div className="lp-wrap">
        <SectionHead id="lp-faq" eyebrow="Questions" title="Common questions" />
        <div className="lp-faq">
          {FAQ.map(([q, a]) => (
            <details key={q} className="clay">
              <summary>{q}</summary>
              <p>{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Landing() {
  return (
    <div className="lp">
      <header className="lp-top">
        <div className="lp-wrap">
          <div className="clay lp-top-inner">
            <Link className="lp-brand" href="/" aria-label="Anveshan, home">
              <OwlMark size={40} />
              <span>Anveshan</span>
            </Link>
            <nav className="lp-nav" aria-label="Sections">
              <a href="#roles">Who uses it</a>
              <a href="#journey">The PhD journey</a>
              <a href="#ugc">UGC 2022</a>
              <a href="#trust">Data &amp; privacy</a>
              <a href="#pilot">Pilot</a>
            </nav>
            <LoginButton />
          </div>
        </div>
      </header>
      <main>
        <Hero />
        <Problem />
        <Roles />
        <Journey />
        <Ugc />
        <Trust />
        <Modules />
        <Pilot />
        <Faq />
        <section className="lp-band lp-band-deep" aria-labelledby="lp-closing">
          <div className="lp-wrap">
            <div className="clay lp-closing">
              <div className="lp-closing-copy">
                <h2 id="lp-closing">Already part of a university on Anveshan?</h2>
                <p className="lp-lede">
                  Log in with your university email, or with the password from your invitation email.
                </p>
                <div className="lp-cta">
                  <LoginButton />
                </div>
              </div>
              <div className="lp-closing-owl">
                <Owl pose="cheering" size={150} />
              </div>
            </div>
          </div>
        </section>
      </main>
      <footer className="lp-foot">
        <div className="lp-wrap lp-foot-inner">
          <span>
            <b>Anveshan</b> · Sanskrit for <i>exploration, inquiry</i>
          </span>
          <span>The research system for Indian universities</span>
        </div>
      </footer>
    </div>
  );
}
