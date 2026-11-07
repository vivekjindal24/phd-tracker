"use client";

import { useEffect } from "react";
import { BRANDING_CHANGED, logoUrl } from "@/lib/api";
import type { Branding } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

/** The university's name, with its logo once its admin has set one. Co-branded: this sits beside
 *  the Anveshan wordmark, and the logo takes over the favicon. */
export function UniversityMark() {
  const { data, reload } = useFetch<Branding>("/branding");
  const src = data?.has_logo ? logoUrl(data.logo_version) : null;

  useEffect(() => {
    const icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (src && icon) icon.href = src;
  }, [src]);

  useEffect(() => {
    window.addEventListener(BRANDING_CHANGED, reload);
    return () => window.removeEventListener(BRANDING_CHANGED, reload);
  }, [reload]);

  if (!data) return null;
  return (
    <span className="university-mark">
      {src && <img src={src} alt="" width={32} height={32} />}
      <span title={data.university}>{data.university}</span>
    </span>
  );
}
