import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The self-hosted container runs the standalone server (ARCHITECTURE.md §4).
  output: "standalone",
  experimental: {
    // The repo lives on an exFAT volume, which breaks Turbopack's cache database.
    turbopackFileSystemCacheForDev: false,
    turbopackFileSystemCacheForBuild: false,
  },
};

export default nextConfig;
