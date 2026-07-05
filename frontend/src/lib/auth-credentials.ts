import { compare, hashSync } from "bcryptjs";
import Credentials from "next-auth/providers/credentials";
import { z } from "zod";

import { pool } from "@/lib/db";
import { clientIp, underLimit } from "@/lib/rate-limit";

// NODE-ONLY. Imported solely by auth.ts. `pg` + `bcryptjs` are not Edge-safe, so
// this must never be reachable from auth.config.ts / middleware.
const schema = z.object({ email: z.string().email(), password: z.string().min(1) });

// Same cost factor (12) as register hashing, so a no-such-user login costs the
// same wall-clock time as a real one (defeats timing-based email enumeration).
const DUMMY_HASH = hashSync("timing-equalization-dummy", 12);

export const credentialsProvider = Credentials({
  credentials: { email: { type: "email" }, password: { type: "password" } },
  async authorize(raw, request) {
    // Per-IP login throttle. Returning null looks identical to bad credentials,
    // so this leaks nothing.
    const ip = clientIp(request);
    if (!underLimit(`login:${ip}`, 20, 900)) return null; // 20 / 15 min

    const parsed = schema.safeParse(raw);
    if (!parsed.success) return null;
    const email = parsed.data.email.trim().toLowerCase();

    const { rows } = await pool.query(
      `SELECT id, "emailVerified", password_hash
         FROM users WHERE LOWER(email) = $1 LIMIT 1`,
      [email],
    );
    const user = rows[0];

    // ALWAYS run one compare — real hash or dummy — so latency is constant.
    const ok = await compare(parsed.data.password, user?.password_hash ?? DUMMY_HASH);

    // One generic failure for: no user, OAuth-only (no hash), bad password, or
    // unverified. Never distinguish these (anti-enumeration).
    if (!user || !user.password_hash || !ok) return null;
    if (user.emailVerified == null) return null;

    return { id: String(user.id), email }; // String() matches the Google/adapter path
  },
});
