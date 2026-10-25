import type { Metadata } from "next";
import { Landing } from "@/components/landing/Landing";
import { SignedInRedirect } from "@/components/landing/SignedInRedirect";

export const metadata: Metadata = {
  title: { absolute: "Anveshan · The research system for Indian universities" },
  description:
    "Scholars, supervisors, departments and the central offices work in one place, and UGC 2022 records come from daily work.",
};

export default function Index() {
  return (
    <>
      <SignedInRedirect />
      <Landing />
    </>
  );
}
