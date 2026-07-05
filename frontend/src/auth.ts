import PostgresAdapter from "@auth/pg-adapter";
import NextAuth from "next-auth";

import { authConfig } from "@/auth.config";
import { pool } from "@/lib/db";

// Full server-side config: the edge-safe base + the Postgres adapter, which
// persists a real user row (users/accounts tables) on first sign-in. Imported
// by the route handlers and server components — NOT by middleware, which uses
// auth.config directly to stay Edge-compatible (the adapter needs Node/`pg`).
export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  adapter: PostgresAdapter(pool),
});
