import { hash } from "bcryptjs";
import { z } from "zod";

import { redeemToken } from "@/lib/auth-tokens";
import { pool } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const Body = z.object({
  email: z.string().email(),
  token: z.string().min(1),
  password: z.string().min(8).max(72),
});

export async function POST(req: Request) {
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
  const email = p.data.email.trim().toLowerCase();

  if (!(await redeemToken("reset", email, p.data.token))) {
    return Response.json({ error: "invalid_token" }, { status: 400 }); // bad / used / expired
  }

  const passwordHash = await hash(p.data.password, 12);
  // Proving inbox control also verifies the email.
  await pool.query(
    `UPDATE users SET password_hash = $2, "emailVerified" = COALESCE("emailVerified", now())
       WHERE LOWER(email) = $1`,
    [email, passwordHash],
  );
  return Response.json({ ok: true, message: "Password updated. You can now sign in." });
}
