"use client";

import { useState } from "react";
import { Card, Switch } from "@/components/ui/kit";
import { MODULE_LABELS } from "@/lib/types";
import type { ModuleKey } from "@/lib/types";
import type { Save } from "./save";

export function Modules({ modules, save }: { modules: Record<ModuleKey, boolean>; save: Save }) {
  const [busy, setBusy] = useState<ModuleKey | null>(null);

  async function toggle(key: ModuleKey, enabled: boolean) {
    setBusy(key);
    try {
      await save(`/settings/modules/${key}`, "PUT", { enabled });
    } catch {
      // the page shows the error; the switch keeps the server's state
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className="settings-modules">
      <h2>Modules</h2>
      <p className="muted">Switched-off modules disappear for everyone.</p>
      <ul className="module-list">
        {(Object.keys(MODULE_LABELS) as ModuleKey[]).map((key) => (
          <li key={key}>
            <span>{MODULE_LABELS[key]}</span>
            <Switch
              checked={modules[key]}
              label={MODULE_LABELS[key]}
              disabled={busy === key}
              onChange={(next) => toggle(key, next)}
            />
          </li>
        ))}
      </ul>
    </Card>
  );
}
