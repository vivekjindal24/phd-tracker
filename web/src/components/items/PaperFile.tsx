"use client";

import { Attachments } from "@/components/Attachments";
import type { FileOwner, SettingsData } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

/** A publication's paper (a scholar's or a faculty member's). Optional unless the university
 *  asks for it (Settings → Rules); the API enforces that, this only says so. */
export function PaperFile({ table, recordId, canUpload, when }: {
  table: Extract<FileOwner, "publications" | "faculty_publications">;
  recordId: string;
  canUpload: boolean;
  /** When it is needed, if required: "before you submit" / "before the Library verifies it". */
  when: string;
}) {
  const required = useFetch<SettingsData>("/settings").data?.publication_file_required ?? false;
  const hint = required
    ? `The published paper or acceptance letter. The university asks for it ${when}.`
    : "The published paper or acceptance letter, for the Library to check (optional).";
  return <Attachments table={table} recordId={recordId} canUpload={canUpload} title="The paper" hint={hint} />;
}
