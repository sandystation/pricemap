import { z } from "zod";

import { auth } from "@/auth";
import { pool } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const Body = z.object({
  input: z.record(z.unknown()),
  result: z.record(z.unknown()),
});

// Auto-called by the valuation form when a logged-in user gets a result. Silently
// 401s for anonymous users (the client ignores it) — history is a signed-in perk.
export async function POST(req: Request) {
  const session = await auth();
  const uid = session?.user?.id;
  if (!uid) return Response.json({ error: "unauthenticated" }, { status: 401 });

  let json: unknown;
  try {
    json = await req.json();
  } catch {
    return Response.json({ error: "invalid_input" }, { status: 400 });
  }
  const p = Body.safeParse(json);
  if (!p.success) return Response.json({ error: "invalid_input" }, { status: 400 });

  const { input, result } = p.data;
  const str = (v: unknown) => (typeof v === "string" ? v : null);
  const num = (v: unknown) => (v == null || Number.isNaN(Number(v)) ? null : Number(v));

  const { rows } = await pool.query(
    `INSERT INTO saved_valuations
       (user_id, address, listing_type, property_type, area_sqm, estimate_eur, input, result)
     VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)
     RETURNING id`,
    [
      Number(uid),
      str(input.address),
      str(input.listing_type),
      str(input.property_type),
      num(input.area_sqm),
      num((result as Record<string, unknown>).estimate_eur),
      JSON.stringify(input),
      JSON.stringify(result),
    ],
  );
  return Response.json({ id: rows[0].id });
}
