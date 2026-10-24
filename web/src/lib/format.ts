/** "21 Oct 2026" from an ISO date (YYYY-MM-DD), read as a calendar date, not UTC midnight. */
export const formatDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

/** "Fri, 20 Nov, 10:00" in the viewer's time zone. */
export const formatWhen = (iso: string) =>
  new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 0, maximumFractionDigits: 2 });

/** "₹12,50,000" — Indian digit grouping, paise only when present. */
export const formatMoney = (amount: number) => INR.format(amount);
