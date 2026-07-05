export { auth as middleware } from "@/auth";

// Gate the valuation form: unauthenticated users are redirected to /login
// (via the authorized() callback in src/auth.ts). The landing page stays public.
export const config = {
  matcher: ["/mt/valuation"],
};
