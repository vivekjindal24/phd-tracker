const HERE = "http://anveshan.invalid";

/** Where to go after login: a path on this site, never a page elsewhere (open redirect). */
export function safeNext(next: string | null): string {
  if (!next) return "/home";
  try {
    const url = new URL(next, HERE);
    return url.origin === HERE ? url.pathname + url.search : "/home";
  } catch {
    return "/home";
  }
}
