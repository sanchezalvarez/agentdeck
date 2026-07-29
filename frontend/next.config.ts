import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Hides the floating Next.js dev-tools badge in the bottom-left corner.
  // It only ever renders under `next dev`, never in a production build.
  devIndicators: false,
};

export default nextConfig;
