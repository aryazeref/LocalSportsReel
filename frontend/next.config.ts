import type { NextConfig } from "next";

/**
 * The hackathon frontend can be exported as ordinary HTML/CSS/JS because
 * all live data, predictions and AI requests go to our separate FastAPI API.
 *
 * Netlify was publishing raw .next files and returning a 404 at the root.
 * A static export creates out/index.html and one HTML entry point per route.
 *
 * Images are unoptimized here because static hosting has no Next.js image
 * optimization server. A production SSR app would use Netlify's adapter.
 */
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
