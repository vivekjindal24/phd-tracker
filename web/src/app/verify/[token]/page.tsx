"use client";

import { useParams } from "next/navigation";
import { Owl } from "@/components/brand/Owl";
import { formatDate } from "@/lib/format";
import type { CertificateCheck } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import "@/components/ui/ui.css";

export default function VerifyPage() {
  const { token } = useParams<{ token: string }>();
  const { data, error } = useFetch<CertificateCheck>(`/verify/${encodeURIComponent(token)}`);

  return (
    <main className="empty-state">
      <Owl pose={data?.status === "valid" ? "reading" : "empty"} size={110} />
      <h1>Provisional certificate</h1>
      {error && <p role="alert">We could not verify this certificate. Check the link or QR code.</p>}
      {data && (
        <>
          <p role="status">
            <strong>{data.status === "valid" ? "Valid" : "Revoked"}</strong>
          </p>
          <dl>
            <dt>Name</dt><dd>{data.name}</dd>
            <dt>Thesis</dt><dd>{data.thesis_title}</dd>
            <dt>Unit</dt><dd>{data.unit}</dd>
            <dt>Viva held</dt><dd>{formatDate(data.viva_date)}</dd>
            <dt>Issued</dt><dd>{formatDate(data.issued_on)}</dd>
          </dl>
        </>
      )}
    </main>
  );
}
