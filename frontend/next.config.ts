import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Pinned so Turbopack does not walk up and adopt an unrelated lockfile from a
  // parent directory as the workspace root.
  turbopack: { root: path.resolve(process.cwd()) },
};

export default nextConfig;
