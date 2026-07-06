// Shared Tailwind class strings for the auth pages — keeps /login, /signup,
// /verify, /forgot-password, /reset-password visually consistent with the
// existing Casaval card styling (CSS custom properties, solid colors).
// A warm-white card floats on a limestone ground.
export const cardWrap =
  "flex min-h-screen items-center justify-center bg-[var(--color-bg-secondary)] px-6";
export const card =
  "w-full max-w-sm rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 shadow-sm";
export const inputClass =
  "w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]";
export const labelClass = "mb-1 block text-sm font-medium text-[var(--color-text)]";
export const primaryBtn =
  "w-full rounded-lg bg-[var(--color-primary)] py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--color-primary-dark)] disabled:cursor-not-allowed disabled:opacity-50";
export const errorBanner =
  "rounded-lg border border-[var(--color-danger)] bg-[var(--color-danger-bg)] p-3 text-sm text-[var(--color-danger)]";
export const successBanner =
  "rounded-lg border border-[var(--color-success)] bg-[var(--color-success-bg)] p-3 text-sm text-[var(--color-success)]";
export const infoBanner =
  "rounded-lg border border-[var(--color-border)] bg-[var(--color-info-bg)] p-3 text-sm text-[var(--color-primary)]";
export const mutedLink = "text-[var(--color-primary)] hover:underline";
