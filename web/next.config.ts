import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // Local engine lives at BUSDROP_ENGINE (default 127.0.0.1:8000), proxied
  // through app/api/* route handlers so the browser stays same-origin.
  // Run it from the repo root: .venv/bin/uvicorn api:app --port 8000
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
