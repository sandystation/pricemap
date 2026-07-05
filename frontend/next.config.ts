import type { NextConfig } from "next";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return {
      // Serve the Malta professional-beta landing page at the bare apex ("/").
      // beforeFiles runs before filesystem routes, so it overrides app/page.tsx
      // while keeping the URL as "/".
      beforeFiles: [{ source: "/", destination: "/mt/professional-beta" }],
      // Only proxy the backend API (/api/v1/*) to FastAPI. /api/auth/* and
      // /api/token are Auth.js route handlers that must stay in Next.js — a
      // broad /api/:path* rewrite would forward them to the backend (404).
      afterFiles: [{ source: "/api/v1/:path*", destination: `${API}/api/v1/:path*` }],
    };
  },
};

export default nextConfig;
