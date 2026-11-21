/** Dates read the same for everyone, as Indian forms write them: "21 Nov 2026" — whatever
 *  language the viewer's browser is set to. Times are in the viewer's time zone. */
const LOCALE = "en-IN";

/** "21 Nov 2026" from an ISO date (YYYY-MM-DD), read as a calendar date, not UTC midnight. */
export const formatDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(LOCALE, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

/** "October 2026" from the first day of a month (YYYY-MM-01). */
export const formatMonth = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(LOCALE, { month: "long", year: "numeric" });

/** "21 Nov 2026": the day of a timestamp, in the viewer's time zone. */
export const formatDay = (iso: string) =>
  new Date(iso).toLocaleDateString(LOCALE, { day: "numeric", month: "short", year: "numeric" });

const time = (iso: string) =>
  new Date(iso).toLocaleTimeString(LOCALE, { hour: "numeric", minute: "2-digit" });

/** "21 Nov 2026, 2:30 pm": when something happened (a timestamp). */
export const formatStamp = (iso: string) => `${formatDay(iso)}, ${time(iso)}`;

/** "Wed, 22 Sep 2027, 4:30 pm": when something is scheduled. Built from parts: the locale
 *  alone would write "Wed, 22 Sep, 2027". */
export const formatWhen = (iso: string) =>
  `${new Date(iso).toLocaleDateString(LOCALE, { weekday: "short" })}, ${formatStamp(iso)}`;

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 0, maximumFractionDigits: 2 });

/** "₹12,50,000" — Indian digit grouping, paise only when present. */
export const formatMoney = (amount: number) => INR.format(amount);
