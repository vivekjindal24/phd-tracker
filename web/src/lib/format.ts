/** "21 Oct 2026" from an ISO date (YYYY-MM-DD), read as a calendar date, not UTC midnight. */
export const formatDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
