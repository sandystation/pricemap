import NextAuth from "next-auth";

import { authConfig } from "@/auth.config";

// Edge-safe middleware: built from the base config only (no Postgres adapter /
// `pg`), so it runs in the Edge runtime. Currently gates only /account/* (the
// future signed-in area); the valuation form stays PUBLIC during beta (soft
// rollout, backend enforces per-IP limits). To require login for valuations
// later, add "/mt/valuation" to the matcher + flip REQUIRE_AUTH=true.
export const { auth: middleware } = NextAuth(authConfig);

export const config = {
  matcher: ["/account/:path*"],
};
