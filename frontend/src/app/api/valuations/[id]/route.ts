import { auth } from "@/auth";
import { pool } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ id: string }> };

// Full detail for one saved valuation — always scoped to the owner.
export async function GET(_req: Request, { params }: Ctx) {
  const session = await auth();
  const uid = session?.user?.id;
  if (!uid) return Response.json({ error: "unauthenticated" }, { status: 401 });
  const { id } = await params;

  const { rows } = await pool.query(
    `SELECT id, created_at, address, listing_type, property_type, area_sqm, estimate_eur, input, result
       FROM saved_valuations WHERE id = $1 AND user_id = $2`,
    [Number(id), Number(uid)],
  );
  if (!rows.length) return Response.json({ error: "not_found" }, { status: 404 });
  return Response.json(rows[0]);
}

export async function DELETE(_req: Request, { params }: Ctx) {
  const session = await auth();
  const uid = session?.user?.id;
  if (!uid) return Response.json({ error: "unauthenticated" }, { status: 401 });
  const { id } = await params;

  await pool.query(`DELETE FROM saved_valuations WHERE id = $1 AND user_id = $2`, [
    Number(id),
    Number(uid),
  ]);
  return Response.json({ ok: true });
}
