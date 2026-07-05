import { createHash, randomBytes } from "node:crypto";

import { pool } from "@/lib/db";

// Email-verification + password-reset tokens, both stored in the Auth.js
// `verification_token` table (identifier namespaced by kind). The raw token is
// emailed to the user; only its SHA-256 hash is stored, so a DB leak can't be
// replayed. Tokens are single-use (deleted on redeem) and time-boxed.
export const VERIFY_TTL_MS = 24 * 60 * 60 * 1000; // 24h
export const RESET_TTL_MS = 60 * 60 * 1000; // 1h

const sha256 = (s: string) => createHash("sha256").update(s).digest("hex");
const ident = (kind: "verify" | "reset", email: string) => `${kind}:${email.toLowerCase()}`;

// Returns the RAW token (email it). Latest-wins: issuing a new token for an
// (kind,email) invalidates any prior one.
export async function createToken(
  kind: "verify" | "reset",
  email: string,
  ttlMs: number,
): Promise<string> {
  const raw = randomBytes(32).toString("base64url"); // 256-bit
  const id = ident(kind, email);
  await pool.query(`DELETE FROM verification_token WHERE identifier = $1`, [id]);
  await pool.query(
    `INSERT INTO verification_token (identifier, expires, token) VALUES ($1, $2, $3)`,
    [id, new Date(Date.now() + ttlMs), sha256(raw)],
  );
  return raw;
}

// Atomic delete + expiry check. Returns true iff a live token was consumed.
export async function redeemToken(
  kind: "verify" | "reset",
  email: string,
  raw: string,
): Promise<boolean> {
  const { rows } = await pool.query(
    `DELETE FROM verification_token
       WHERE identifier = $1 AND token = $2 AND expires > now()
       RETURNING identifier`,
    [ident(kind, email), sha256(raw)],
  );
  return rows.length > 0;
}
