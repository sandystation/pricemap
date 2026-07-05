import jwt from "jsonwebtoken";

import { auth } from "@/auth";

// Mints a short-lived HS256 API token for the logged-in user, which the FastAPI
// backend verifies (shared API_JWT_SECRET). Same-origin; called by the api-client
// before hitting the cross-origin API.
export const dynamic = "force-dynamic";

export async function GET() {
  const session = await auth();
  const uid = session?.user?.id;
  if (!uid) {
    return Response.json({ error: "unauthenticated" }, { status: 401 });
  }
  const secret = process.env.API_JWT_SECRET;
  if (!secret) {
    return Response.json({ error: "auth not configured" }, { status: 503 });
  }
  const token = jwt.sign({ sub: uid }, secret, { algorithm: "HS256", expiresIn: "10m" });
  return Response.json({ token });
}
