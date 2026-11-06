"use client";

import { RequireRole } from "@/components/ui/RequireRole";
import { useRouter } from "next/navigation";
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
        <p className="muted">Saved as a draft. Attach the paper on the next page, then submit it for your supervisor and the Library to verify.</p>
        <PublicationForm initial={EMPTY_PUBLICATION} submitLabel="Save draft"
          onSubmit={async (value) => {
            const item = await api<ItemView>("/publications", { method: "POST", body: JSON.stringify(value) });
            router.push(`/items/publication/${item.id}`);
          }} />
      </Card>
    </>
  );
}

export default function NewPublicationPage() {
  return <RequireRole roles={["scholar"]}><NewPublicationForm /></RequireRole>;
}
