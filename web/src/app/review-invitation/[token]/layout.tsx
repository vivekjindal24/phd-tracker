import type { Metadata } from "next";
import type { ReactNode } from "react";

// A private link: reachable from the email, never by a search engine.
export const metadata: Metadata = { title: "Thesis review invitation", robots: { index: false, follow: false } };

export default function InvitationLayout({ children }: { children: ReactNode }) {
  return children;
}
