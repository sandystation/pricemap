import { Pool } from "pg";

// Singleton pg pool for the Auth.js Postgres adapter. Reused across route
// invocations (and dev hot-reloads) so we don't exhaust Postgres connections.
// Connects lazily — constructing the Pool does not open a socket, so this is
// safe to import at build time even when AUTH_DATABASE_URL is unset.
const globalForPg = globalThis as unknown as { authPool?: Pool };

export const pool =
  globalForPg.authPool ??
  new Pool({ connectionString: process.env.AUTH_DATABASE_URL, max: 5 });

if (process.env.NODE_ENV !== "production") globalForPg.authPool = pool;
