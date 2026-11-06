import type { Metadata } from "next";
import type { ReactNode } from "react";

// A public page with a person's name: reachable by its link, never by a search engine.
export const metadata: Metadata = { title: "Verify certificate", robots: { index: false, follow: false } };

export default function VerifyLayout({ children }: { children: ReactNode }) {
  return children;
}
