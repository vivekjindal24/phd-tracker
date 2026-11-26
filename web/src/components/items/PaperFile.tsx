"use client";

import { useSearchParams } from "next/navigation";
import { Attachments } from "@/components/Attachments";
import { ErrorText } from "@/components/ui/kit";
import type { FileOwner, SettingsData } from "@/lib/types";
import { uploadFile } from "@/lib/upload";
import { errorText, useFetch } from "@/lib/useFetch";

type PaperTable = Extract<FileOwner, "publications" | "faculty_publications">;
const NOT_ATTACHED = "paper=not_attached";

/** After a new record is saved: attach the PDF chosen on the form, if any. Returns the query to
 *  open the record with, which says so there when the upload failed (the record exists now). */
export async function attachChosenPaper(table: PaperTable, recordId: string, paper: File | null): Promise<string> {
  if (!paper) return "";
  try {
    await uploadFile(table, recordId, paper);
    return "";
  } catch (err) {
    return `?${NOT_ATTACHED}&reason=${encodeURIComponent(errorText(err))}`;
  }
}

/** A publication's paper (a scholar's or a faculty member's). Optional unless the university
 *  asks for it (Settings → Rules); the API enforces that, this only says so. */
export function PaperFile({ table, recordId, canUpload, when }: {
  table: PaperTable;
  recordId: string;
  canUpload: boolean;
  /** When it is needed, if required: "before you submit" / "before the Library verifies it". */
  when: string;
}) {
  const required = useFetch<SettingsData>("/settings").data?.publication_file_required ?? false;
  const hint = required
    ? `The published paper or acceptance letter. The university asks for it ${when}.`
    : "The published paper or acceptance letter, for the Library to check (optional).";
  const params = useSearchParams();
  const failed = params.get("paper") === "not_attached";
  return (
    <>
      {failed && <ErrorText>{`Saved, but the paper you chose could not be attached: ${params.get("reason") ?? "unknown error"}. Attach it below.`}</ErrorText>}
      <Attachments table={table} recordId={recordId} canUpload={canUpload} title="The paper" hint={hint} />
    </>
  );
}
