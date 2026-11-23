"use client";

import { useRouter } from "next/navigation";
import { EMPTY_PATENT, PatentForm } from "@/components/items/PatentForm";
import { NotForYourRole } from "@/components/ui/RequireRole";
import { Card, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Patent } from "@/lib/types";

export default function NewPatentPage() {
  const { me } = useSession();
  const router = useRouter();
  if (!me) return null;
  if (me.faculty_id === null && me.scholar_id === null) return <NotForYourRole />;
  return (
    <>
      <PageHeader eyebrow="Research record" title="Add your patent" />
      <Card>
        <p className="muted">It goes to be checked against the patent office&apos;s record. Attach the filing receipt or grant certificate on the next page.</p>
        <PatentForm initial={EMPTY_PATENT} submitLabel="Save and send to be checked"
          onSubmit={async (value) => {
            const patent = await api<Patent>("/patents", { method: "POST", body: JSON.stringify(value) });
            router.push(`/patents/${patent.id}`);
          }} />
      </Card>
    </>
  );
}
