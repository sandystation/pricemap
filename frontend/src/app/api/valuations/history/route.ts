import { auth } from "@/auth";
import { pool } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// List the signed-in user's saved valuations (summaries only).
export async function GET() {
  const session = await auth();
  const uid = session?.user?.id;
  if (!uid) return Response.json({ error: "unauthenticated" }, { status: 401 });

  const { rows } = await pool.query(
    `SELECT id, created_at, address, listing_type, property_type, area_sqm, estimate_eur
       FROM saved_valuations
      WHERE user_id = $1
      ORDER BY created_at DESC
      LIMIT 200`,
    [Number(uid)],
  );
  return Response.json({ valuations: rows });
}
