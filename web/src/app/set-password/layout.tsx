import type { Metadata } from "next";
import type { ReactNode } from "react";

// The set-password token sits in this page's URL: never send it on as a Referer.
export const metadata: Metadata = { title: "Set your password · Anveshan", referrer: "no-referrer" };

export default function SetPasswordLayout({ children }: { children: ReactNode }) {
  return children;
}
