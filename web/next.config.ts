import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // One build runs on Vercel and in the self-hosted container (ARCHITECTURE.md §4).
  output: "standalone",
  experimental: {
    // The repo lives on an exFAT volume, which breaks Turbopack's cache database.
    turbopackFileSystemCacheForDev: false,
    turbopackFileSystemCacheForBuild: false,
  },
};

export default nextConfig;
