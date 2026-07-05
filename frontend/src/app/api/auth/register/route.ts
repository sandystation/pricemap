import { hash } from "bcryptjs";
import { z } from "zod";

import { VERIFY_TTL_MS, createToken } from "@/lib/auth-tokens";
import { pool } from "@/lib/db";
import { sendVerificationEmail } from "@/lib/email";
import { clientIp, underLimit } from "@/lib/rate-limit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const Body = z.object({
  email: z.string().email().transform((s) => s.trim().toLowerCase()),
  password: z.string().min(8).max(72), // 72 = bcrypt byte limit; reject beyond, don't truncate
  name: z.string().max(100).optional(),
});

export async function POST(req: Request) {
  if (!underLimit(`register:${clientIp(req)}`, 10, 3600)) {
    return Response.json({ error: "rate_limited" }, { status: 429 });
  }

  let json: unknown;
  try {
    json = await req.json();
  } catch {
    return Response.json({ error: "invalid_input" }, { status: 400 });
  }
  const p = Body.safeParse(json);
  if (!p.success) {
    return Response.json({ error: "invalid_input", issues: p.error.flatten() }, { status: 400 });
  }
  const { email, password, name } = p.data;

  // Hash unconditionally (even for existing emails) so response time doesn't
  // depend on whether the account exists.
  const passwordHash = await hash(password, 12);
  const existing = await pool.query(`SELECT id FROM users WHERE LOWER(email) = $1`, [email]);

  // Only create BRAND-NEW accounts. Never mutate an existing row from this
  // unauthenticated endpoint — setting a password on someone else's account
  // (e.g. a Google-only user) would be an account-takeover vector. A Google
  // user who wants a password uses the reset flow (proves inbox control); an
  // existing email silently returns the generic response below (no enumeration).
  if (existing.rows.length === 0) {
    try {
      await pool.query(
        `INSERT INTO users (email, name, password_hash) VALUES ($1, $2, $3)`,
        [email, name ?? null, passwordHash],
      );
      // Verification email off the request path so latency doesn't leak existence.
      void (async () => {
        const token = await createToken("verify", email, VERIFY_TTL_MS);
        await sendVerificationEmail(email, token);
      })().catch((err) => console.error("[register] verification email failed:", err));
    } catch (err: unknown) {
      // Concurrent double-submit → unique-violation (23505): treat as generic success.
      if (!(typeof err === "object" && err && (err as { code?: string }).code === "23505")) {
        throw err;
      }
    }
  }

  // Generic success regardless of branch. Never auto sign-in.
  return Response.json({ ok: true, message: "Check your email to confirm your account." });
}
