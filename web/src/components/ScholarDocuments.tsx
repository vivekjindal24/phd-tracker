"use client";

import { Attachments } from "@/components/Attachments";
import { FILE_SLOT_LABELS } from "@/lib/types";
import type { FileSlot } from "@/lib/types";

/** The scholar's own papers the PhD file needs (PRD F17): each in its named place. The admin
 *  over the scholar's unit adds them; the API decides. */
export function ScholarDocuments({ scholarId, canUpload }: { scholarId: string; canUpload: boolean }) {
  return (
    <div className="profile-grid">
      {(Object.keys(FILE_SLOT_LABELS) as FileSlot[]).map((slot) => (
        <Attachments key={slot} table="scholars" recordId={scholarId} slot={slot} canUpload={canUpload}
          title={FILE_SLOT_LABELS[slot]}
          hint={slot === "employer_noc" ? "For an employed candidate." : undefined} />
      ))}
    </div>
  );
}
