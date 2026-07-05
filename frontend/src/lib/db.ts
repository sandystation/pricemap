import { Pool } from "pg";

// Singleton pg pool for the Auth.js Postgres adapter. Reused across route
// invocations (and dev hot-reloads) so we don't exhaust Postgres connections.
// Connects lazily — constructing the Pool does not open a socket, so this is
// safe to import at build time even when AUTH_DATABASE_URL is unset.
const globalForPg = globalThis as unknown as { authPool?: Pool };

export const pool =
  globalForPg.authPool ??
  new Pool({ connectionString: process.env.AUTH_DATABASE_URL, max: 5 });

// Without an 'error' handler, node-postgres rethrows errors on idle clients
// (e.g. a Postgres restart/failover drops the connection) as an uncaught
// exception that would crash the single frontend replica. Log and let the pool
// discard the dead client. Never log the connection string.
if (!globalForPg.authPool) {
  pool.on("error", (err) => console.error("[db] idle client error:", err.message));
}

if (process.env.NODE_ENV !== "production") globalForPg.authPool = pool;
