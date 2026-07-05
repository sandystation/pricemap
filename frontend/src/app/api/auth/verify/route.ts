import { z } from "zod";

import { redeemToken } from "@/lib/auth-tokens";
import { pool } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const Body = z.object({ token: z.string().min(1), email: z.string().email() });

// POST (not a GET link) so an email client prefetching the link can't consume
// the single-use token — the /verify page fires this on mount.
export async function POST(req: Request) {
  let json: unknown;
  try {
    json = await req.json();
  } catch {
    return Response.json({ ok: false }, { status: 400 });
  }
  const p = Body.safeParse(json);
  if (!p.success) return Response.json({ ok: false }, { status: 400 });
  const email = p.data.email.trim().toLowerCase();

  if (!(await redeemToken("verify", email, p.data.token))) {
    return Response.json({ ok: false }, { status: 400 }); // wrong / used / expired — generic
  }
  await pool.query(`UPDATE users SET "emailVerified" = now() WHERE LOWER(email) = $1`, [email]);
  return Response.json({ ok: true });
}
