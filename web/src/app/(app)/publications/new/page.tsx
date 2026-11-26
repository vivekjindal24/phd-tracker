"use client";

import { RequireRole } from "@/components/ui/RequireRole";
import { useRouter } from "next/navigation";
import { OrcidImport } from "@/components/items/OrcidImport";
import { attachChosenPaper } from "@/components/items/PaperFile";
import { EMPTY_PUBLICATION, PublicationForm } from "@/components/items/PublicationForm";
import { Card, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import type { ItemView } from "@/lib/types";

function NewPublicationForm() {
  const router = useRouter();
  return (
    <>
      <PageHeader eyebrow="Research record" title="Add publication" />
      <Card>
        <p className="muted">Saved as a draft, then submitted for your supervisor and the Library to verify. Start from the paper&apos;s PDF, or attach it on the next page.</p>
        <PublicationForm initial={EMPTY_PUBLICATION} submitLabel="Save draft" withPaper
          onSubmit={async (value, paper) => {
            const item = await api<ItemView>("/publications", { method: "POST", body: JSON.stringify(value) });
            router.push(`/items/publication/${item.id}${await attachChosenPaper("publications", item.id, paper)}`);
          }} />
      </Card>
      <OrcidImport />
    </>
  );
}

export default function NewPublicationPage() {
  return <RequireRole roles={["scholar"]}><NewPublicationForm /></RequireRole>;
}
