import * as Sentry from "@sentry/nextjs";

// Edge runtime (middleware) Sentry init. No-op without a DSN.
const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
if (dsn) {
  Sentry.init({
    dsn,
    tracesSampleRate: 0.1,
  });
}
