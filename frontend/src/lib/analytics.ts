import posthog from "posthog-js";

// Thin wrapper around PostHog capture. No-op until PostHog is initialized (i.e.
// when NEXT_PUBLIC_POSTHOG_KEY is set) and never throws, so analytics can't
// break the app or a valuation flow.
export function track(event: string, properties?: Record<string, unknown>): void {
  try {
    if (typeof window !== "undefined" && posthog.__loaded) {
      posthog.capture(event, properties);
    }
  } catch {
    // swallow — telemetry must never surface to the user
  }
}
