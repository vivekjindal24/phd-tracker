"use client";

import { useEffect } from "react";
import { logoUrl } from "@/lib/api";
import type { Branding } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

/** The university's logo and name, once its admin has set a logo. Co-branded: this sits beside
 *  the Anveshan wordmark and takes over the favicon. */
export function UniversityMark() {
  const { data } = useFetch<Branding>("/branding");
  const src = data?.has_logo ? logoUrl(data.logo_version) : null;

  useEffect(() => {
    const icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (src && icon) icon.href = src;
  }, [src]);

  if (!src) return null;
  return (
    <span className="university-mark">
      <img src={src} alt="" width={32} height={32} />
      <span>{data?.university}</span>
    </span>
  );
}
