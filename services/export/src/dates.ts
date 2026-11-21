/** How the university writes a date (settings.date_format), the same way the API and the
 *  screens do: month names fixed in English, India's time zone. The API sends the format with
 *  every view (branding.export_fields); fetchView passes it here before a PDF is drawn. One
 *  university per installation, so one format at a time. */
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const FULL_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
  "September", "October", "November", "December"];

let current = "d_mon_yyyy";
export const setDateFormat = (format: string) => { current = format; };

const INDIA = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});

/** Year, month, day (and the time, for a moment) in India: a plain date is taken as it is. */
function parts(iso: string) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
    const [y, m, d] = iso.split("-").map(Number);
    return { y: y!, m: m!, d: d!, h: 0, min: 0 };
  }
  const p = Object.fromEntries(INDIA.formatToParts(new Date(iso)).map((x) => [x.type, x.value]));
  return { y: Number(p.year), m: Number(p.month), d: Number(p.day), h: Number(p.hour), min: Number(p.minute) };
}

/** "21 Nov 2026", "21/11/2026" …, as the university chose; "—" for none. */
export function day(iso: string | null, format = current): string {
  if (!iso) return "—";
  const { y, m, d } = parts(iso);
  const dd = String(d).padStart(2, "0");
  const mm = String(m).padStart(2, "0");
  const formats: Record<string, string> = {
    d_mon_yyyy: `${d} ${MONTHS[m - 1]} ${y}`,
    d_month_yyyy: `${d} ${FULL_MONTHS[m - 1]} ${y}`,
    "dd/mm/yyyy": `${dd}/${mm}/${y}`,
    "dd-mm-yyyy": `${dd}-${mm}-${y}`,
    "dd.mm.yyyy": `${dd}.${mm}.${y}`,
    "yyyy-mm-dd": `${y}-${mm}-${dd}`,
    "mm/dd/yyyy": `${mm}/${dd}/${y}`,
  };
  return formats[format] ?? formats.d_mon_yyyy!;
}

/** "21 Nov 2026, 4:30 pm": a moment in India's time. */
export function stamp(iso: string): string {
  const { h, min } = parts(iso);
  return `${day(iso)}, ${h % 12 || 12}:${String(min).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`;
}
