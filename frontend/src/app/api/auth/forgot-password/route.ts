import { z } from "zod";

import { RESET_TTL_MS, createToken } from "@/lib/auth-tokens";
import { pool } from "@/lib/db";
import { sendPasswordResetEmail } from "@/lib/email";
import { clientIp, underLimit } from "@/lib/rate-limit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const Body = z.object({ email: z.string().email() });

export async function POST(req: Request) {
  let json: unknown;
  try {
    json = await req.json();
  } catch {
    return Response.json({ error: "invalid_input" }, { status: 400 });
  }
  const p = Body.safeParse(json);
  if (!p.success) return Response.json({ error: "invalid_input" }, { status: 400 });
  const email = p.data.email.trim().toLowerCase();

  // Per-IP AND per-email limit (mail-bomb / quota protection). Still generic on trip.
  const generic = { ok: true, message: "If that email is registered, we've sent a reset link." };
  if (
    !underLimit(`forgot:ip:${clientIp(req)}`, 5, 3600) ||
    !underLimit(`forgot:email:${email}`, 3, 3600)
  ) {
    return Response.json(generic);
  }

  const { rows } = await pool.query(
    `SELECT id FROM users WHERE LOWER(email) = $1 AND password_hash IS NOT NULL`,
    [email],
  );
  if (rows.length) {
    // Token creation + email off the request path so response latency doesn't
    // depend on whether the account exists (timing-oracle enumeration).
    void (async () => {
      const token = await createToken("reset", email, RESET_TTL_MS);
      await sendPasswordResetEmail(email, token);
    })().catch((err) => console.error("[forgot] reset email failed:", err));
  }
  // ALWAYS 200 with an identical body — no enumeration.
  return Response.json(generic);
}
