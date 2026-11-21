/** How the university writes a date (Settings → Date format), the same on every screen, PDF and
 *  email: month names fixed in English, whatever language the viewer's browser is set to; times
 *  in the viewer's time zone. The session sets the format before any signed-in page renders. */
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const FULL_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export type DateFormat = "d_mon_yyyy" | "d_month_yyyy" | "dd/mm/yyyy" | "dd-mm-yyyy" | "dd.mm.yyyy"
  | "yyyy-mm-dd" | "mm/dd/yyyy";
let current: DateFormat = "d_mon_yyyy";
export const setDateFormat = (format: DateFormat) => { current = format; };

/** A calendar day as the university writes it; "21 Nov 2026" by default. */
export function writeDay(y: number, m: number, d: number, format: DateFormat = current): string {
  const dd = String(d).padStart(2, "0");
  const mm = String(m).padStart(2, "0");
  switch (format) {
    case "d_month_yyyy": return `${d} ${FULL_MONTHS[m - 1]} ${y}`;
    case "dd/mm/yyyy": return `${dd}/${mm}/${y}`;
    case "dd-mm-yyyy": return `${dd}-${mm}-${y}`;
    case "dd.mm.yyyy": return `${dd}.${mm}.${y}`;
    case "yyyy-mm-dd": return `${y}-${mm}-${dd}`;
    case "mm/dd/yyyy": return `${mm}/${dd}/${y}`;
    default: return `${d} ${MONTHS[m - 1]} ${y}`;
  }
}

/** A stored date (YYYY-MM-DD), read as a calendar date, not UTC midnight. */
export const formatDate = (iso: string) => {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return writeDay(y!, m!, d!);
};

/** "October 2026" from the first day of a month (YYYY-MM-01). */
export const formatMonth = (iso: string) => {
  const [y, m] = iso.split("-").map(Number);
  return `${FULL_MONTHS[m! - 1]} ${y}`;
};

/** The day of a timestamp, in the viewer's time zone. */
export const formatDay = (iso: string) => {
  const t = new Date(iso);
  return writeDay(t.getFullYear(), t.getMonth() + 1, t.getDate());
};

const time = (iso: string) => {
  const t = new Date(iso);
  return `${t.getHours() % 12 || 12}:${String(t.getMinutes()).padStart(2, "0")} ${t.getHours() < 12 ? "am" : "pm"}`;
};

/** "21 Nov 2026, 2:30 pm": when something happened (a timestamp). */
export const formatStamp = (iso: string) => `${formatDay(iso)}, ${time(iso)}`;

/** "Wed, 22 Sep 2027, 4:30 pm": when something is scheduled. */
export const formatWhen = (iso: string) => `${WEEKDAYS[new Date(iso).getDay()]}, ${formatStamp(iso)}`;

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 0, maximumFractionDigits: 2 });

/** "₹12,50,000" — Indian digit grouping, paise only when present. */
export const formatMoney = (amount: number) => INR.format(amount);
