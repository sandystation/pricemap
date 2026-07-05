"use client";

import { SessionProvider, useSession } from "next-auth/react";
import { usePathname, useSearchParams } from "next/navigation";
import posthog from "posthog-js";
import { PostHogProvider as PHProvider } from "posthog-js/react";
import { Suspense, useEffect } from "react";

// Initializes PostHog once on the client. No-op when NEXT_PUBLIC_POSTHOG_KEY is
// unset, so dev/preview builds without a key stay quiet.
// GDPR note: person profiles are created only for identified (logged-in) users;
// a full consent banner should land before any public marketing push.
function PostHogInit() {
  useEffect(() => {
    const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
    if (!key || posthog.__loaded) return;
    posthog.init(key, {
      api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://eu.i.posthog.com",
      capture_pageview: false, // captured manually below (App Router has no full page loads)
      capture_pageleave: true,
      person_profiles: "identified_only",
      autocapture: false,
      // Defense-in-depth: redact single-use auth secrets from any URL property
      // before an event leaves the browser (the /verify + /reset-password links
      // carry token/email in the query string).
      sanitize_properties: (props) => {
        for (const k of ["$current_url", "$referrer", "$pathname"]) {
          const v = props[k];
          if (typeof v === "string" && (v.includes("token=") || v.includes("email="))) {
            props[k] = v.replace(/([?&](?:token|email)=)[^&]*/gi, "$1[redacted]");
          }
        }
        return props;
      },
    });
  }, []);
  return null;
}

// App Router doesn't fire a full navigation, so capture $pageview on path change.
function PageviewTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  useEffect(() => {
    if (!posthog.__loaded || !pathname) return;
    // Never let auth secrets (verify/reset token + email) reach analytics.
    const sp = new URLSearchParams(searchParams?.toString() ?? "");
    sp.delete("token");
    sp.delete("email");
    const qs = sp.toString();
    posthog.capture("$pageview", {
      $current_url: window.origin + pathname + (qs ? `?${qs}` : ""),
    });
  }, [pathname, searchParams]);
  return null;
}

// Attach analytics events to the logged-in user (DB id from the session).
function Identify() {
  const { data: session } = useSession();
  const uid = session?.user?.id;
  useEffect(() => {
    if (!posthog.__loaded) return;
    if (uid) {
      posthog.identify(uid, {
        email: session?.user?.email ?? undefined,
        name: session?.user?.name ?? undefined,
      });
    }
  }, [uid, session?.user?.email, session?.user?.name]);
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <PHProvider client={posthog}>
        <PostHogInit />
        <Suspense fallback={null}>
          <PageviewTracker />
        </Suspense>
        <Identify />
        {children}
      </PHProvider>
    </SessionProvider>
  );
}
