import type { NextAuthConfig } from "next-auth";
import Google from "next-auth/providers/google";

// Edge-safe base config shared by the middleware (Edge runtime) and the full
// server config in auth.ts. It MUST NOT import the Postgres adapter or `pg` —
// those use Node APIs that break the Edge bundle. The adapter is added only in
// auth.ts, which is imported by the route handlers / server components.
export const authConfig: NextAuthConfig = {
  trustHost: true,
  secret: process.env.AUTH_SECRET,
  session: { strategy: "jwt", maxAge: 60 * 60 * 24 * 30 }, // bound JWT lifetime to 30d
  pages: { signIn: "/login" },
  providers: [
    Google({
      clientId: process.env.GOOGLE_OAUTH_CLIENT_ID,
      clientSecret: process.env.GOOGLE_OAUTH_CLIENT_SECRET,
    }),
  ],
  callbacks: {
    // Used by middleware to gate protected routes.
    authorized({ auth: session }) {
      return !!session?.user;
    },
    async jwt({ token, user }) {
      // On sign-in the adapter user (with the Postgres row id) is present;
      // carry that DB id in the token so it flows to the session + API JWT.
      if (user?.id) token.uid = String(user.id);
      return token;
    },
    async session({ session, token }) {
      if (token.uid && session.user) {
        session.user.id = token.uid as string;
      }
      return session;
    },
  },
};
