import * as Sentry from "@sentry/nextjs";

// Browser Sentry init (Next.js 15.3+ loads this automatically). No-op without a DSN.
const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
if (dsn) {
  Sentry.init({
    dsn,
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
  });
}

// Captures navigation errors in the App Router (safe no-op if Sentry is disabled).
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
