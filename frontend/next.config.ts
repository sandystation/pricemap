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
      afterFiles: [{ source: "/api/:path*", destination: `${API}/api/:path*` }],
    };
  },
};

export default nextConfig;
