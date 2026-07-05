import { pool } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Recent nearby listings for the comparables panel. Public (no auth) — same
// exposure as the valuation itself. Spatial query via PostGIS ST_DWithin over
// the `listings` table, filtered by type + area tolerance, nearest first.
export async function GET(req: Request) {
  const p = new URL(req.url).searchParams;
  const lat = Number(p.get("lat"));
  const lon = Number(p.get("lon"));
  const area = Number(p.get("area"));
  const propertyType = p.get("type") || "apartment";
  const listingType = p.get("listing_type") || "sale";
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return Response.json({ comparables: [] });
  }

  const radiusM = 3000; // 3 km
  const hasArea = Number.isFinite(area) && area > 0;
  const minArea = hasArea ? area * 0.6 : null;
  const maxArea = hasArea ? area * 1.4 : null;

  try {
    const { rows } = await pool.query(
      `SELECT id, source, locality, lat, lon, property_type, area_sqm, price_eur, price_per_sqm,
              url, listing_date,
              ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography) AS distance_m
         FROM listings
        WHERE property_type = $3 AND listing_type = $4
          AND price_eur IS NOT NULL AND area_sqm IS NOT NULL
          AND ($5::float8 IS NULL OR area_sqm BETWEEN $5 AND $6)
          AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography, $7)
        ORDER BY distance_m ASC
        LIMIT 8`,
      [lon, lat, propertyType, listingType, minArea, maxArea, radiusM],
    );

    const comparables = rows.map((r) => ({
      id: r.id,
      address: r.locality,
      lat: r.lat,
      lon: r.lon,
      property_type: r.property_type,
      area_sqm: r.area_sqm,
      price_eur: r.price_eur,
      price_per_sqm: r.price_per_sqm,
      distance_m: Math.round(Number(r.distance_m)),
      listing_date: r.listing_date ? new Date(r.listing_date).toISOString() : null,
      source: r.source ?? "mt_remax",
      url: r.url ?? null,
    }));
    return Response.json({ comparables });
  } catch (err) {
    // Missing table/extension or DB hiccup → empty comps, never break the result.
    console.error("[comparables] query failed:", err);
    return Response.json({ comparables: [] });
  }
}
