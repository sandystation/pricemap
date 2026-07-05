import PostgresAdapter from "@auth/pg-adapter";
import NextAuth from "next-auth";

import { authConfig } from "@/auth.config";
import { credentialsProvider } from "@/lib/auth-credentials";
import { pool } from "@/lib/db";

// Full server-side config: the edge-safe base + the Postgres adapter (persists
// user rows) + the email/password Credentials provider. Imported by the route
// handlers and server components — NOT by middleware, which uses auth.config
// directly to stay Edge-compatible (adapter + credentials need Node/`pg`).
// Credentials is appended here (not in authConfig) so `pg`/`bcryptjs` never
// enter the Edge middleware bundle.
export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  adapter: PostgresAdapter(pool),
  providers: [...authConfig.providers, credentialsProvider],
});
