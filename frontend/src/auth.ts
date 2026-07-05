import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

// Adapter-less JWT sessions for now: Google logins need no user table (the stable
// Google `sub` is the user id). A Postgres adapter is added when email/password
// (which needs a user store) lands alongside Resend email verification.
export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  secret: process.env.AUTH_SECRET,
  session: { strategy: "jwt" },
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
    async jwt({ token, profile }) {
      if (profile?.sub) token.uid = profile.sub;
      return token;
    },
    async session({ session, token }) {
      if (token.uid && session.user) {
        session.user.id = token.uid as string;
      }
      return session;
    },
  },
});
