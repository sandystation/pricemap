import NextAuth from "next-auth";

import { authConfig } from "@/auth.config";

// Edge-safe middleware: built from the base config only (no Postgres adapter /
// `pg`), so it runs in the Edge runtime. Gates the signed-in area (/account/*)
// and the valuation form (/:country/valuation → redirect anon to /login). The
// landing (/ → /mt/professional-beta) is a different path and stays public.
// Backend REQUIRE_AUTH=true enforces the same gate at the API layer.
export const { auth: middleware } = NextAuth(authConfig);

export const config = {
  matcher: ["/account/:path*", "/:country/valuation"],
};
