"use client";

import { useRouter } from "next/navigation";
import { OrcidImport } from "@/components/items/OrcidImport";
import { attachChosenPaper } from "@/components/items/PaperFile";
import { EMPTY_PUBLICATION, PublicationForm } from "@/components/items/PublicationForm";
import { NotForYourRole } from "@/components/ui/RequireRole";
import { Card, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { FacultyPublication } from "@/lib/types";

const BASE = "/faculty-publications";

export default function NewFacultyPublicationPage() {
  const { me } = useSession();
  const router = useRouter();
  if (!me) return null;
  if (me.faculty_id === null) return <NotForYourRole />;
  return (
    <>
      <PageHeader eyebrow="Research record" title="Add your publication" />
      <Card>
        <p className="muted">It goes to the Library to verify. Start from the paper&apos;s PDF, or attach it on the next page.</p>
        <PublicationForm base={BASE} initial={EMPTY_PUBLICATION} submitLabel="Save and send to the Library" withPaper
          onSubmit={async (value, file) => {
            const paper = await api<FacultyPublication>(BASE, { method: "POST", body: JSON.stringify(value) });
            router.push(`${BASE}/${paper.id}${await attachChosenPaper("faculty_publications", paper.id, file)}`);
          }} />
      </Card>
      <OrcidImport base={BASE} />
    </>
  );
}
