import Link from "next/link";

/**
 * Shared app-shell header: a sticky, glassy limestone bar with the Fraunces
 * "Casaval" wordmark. Pages pass their own right-side nav/CTAs as children.
 * Mirrors the landing header so the whole product reads as one place.
 */
export function AppHeader({ children }: { children?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-bg)_84%,transparent)] backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-4">
        <Link
          href="/"
          className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight text-[var(--color-primary)]"
        >
          Casaval
        </Link>
        {children ? (
          <div className="flex items-center gap-4 text-sm">{children}</div>
        ) : null}
      </div>
    </header>
  );
}
