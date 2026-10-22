"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, ErrorText, PageHeader } from "@/components/ui/kit";
import { api, ApiError } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { SettingsData } from "@/lib/types";
import { ChainEditor } from "./ChainEditor";
import { CoSupervision } from "./CoSupervision";
import { Modules } from "./Modules";
import { OrgTree } from "./OrgTree";
import { SeminarSettings } from "./SeminarSettings";
import "./settings.css";

export default function SettingsPage() {
  const { me, reload } = useSession();
  const [data, setData] = useState<SettingsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api<SettingsData>("/settings"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  /** Every change goes to the API; the screen shows only what the API returns. */
  const save = useCallback(
    async (path: string, method: "PUT" | "PATCH", body: unknown) => {
      setError(null);
      try {
        setData(await api<SettingsData>(path, { method, body: JSON.stringify(body) }));
        await reload(); // modules / co-supervision change navigation and /auth/me
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
        throw e;
      }
    },
    [reload],
  );

  if (!me?.is_root_admin) {
    return (
      <Card>
        <ErrorText>Only a university administrator can open settings.</ErrorText>
      </Card>
    );
  }

  return (
    <>
      <PageHeader eyebrow="University administration" title="Settings" />
      <ErrorText>{error}</ErrorText>
      {data && (
        <div className="settings-grid">
          <OrgTree />
          <div className="settings-side">
            <Modules modules={data.modules} save={save} />
            <CoSupervision value={data.co_supervision} save={save} />
          </div>
          <SeminarSettings data={data} save={save} />
          <ChainEditor chains={data.chains} save={save} />
        </div>
      )}
    </>
  );
}
