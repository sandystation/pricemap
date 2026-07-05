export { auth as middleware } from "@/auth";

// Soft rollout: the valuation form (/mt/valuation) stays PUBLIC during beta so
// anonymous visitors can still get valuations (backend enforces per-IP limits).
// Login is opt-in at /login. Only /account/* (the future signed-in area) is
// gated for now. To require login for valuations later, add "/mt/valuation"
// back to this matcher and flip REQUIRE_AUTH=true on the backend.
export const config = {
  matcher: ["/account/:path*"],
};
