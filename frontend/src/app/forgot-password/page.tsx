"use client";

import Link from "next/link";
import { Suspense, useState } from "react";

import { track } from "@/lib/analytics";
import { card, cardWrap, errorBanner, inputClass, labelClass, mutedLink, primaryBtn, successBanner } from "@/lib/ui";

function ForgotInner() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    track("forgot_submitted", {});
    try {
      await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      // Always show the generic confirmation — never reveal whether the email exists.
      setSubmitted(true);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={cardWrap}>
      <div className={card}>
        <div className="text-center">
          <h1 className="text-2xl font-bold text-[var(--color-primary)]">Reset your password</h1>
        </div>
        {submitted ? (
          <>
            <div className={`${successBanner} mt-6`}>
              If an account exists for <strong>{email}</strong>, we&apos;ve sent a link to reset your
              password. The link expires in 1 hour.
            </div>
            <p className="mt-6 text-center text-sm">
              <Link href="/login" className={mutedLink}>Back to sign in</Link>
            </p>
          </>
        ) : (
          <>
            <p className="mt-2 text-center text-sm text-[var(--color-text-secondary)]">
              Enter your email and we&apos;ll send a reset link.
            </p>
            <form onSubmit={onSubmit} className="mt-6 space-y-4">
              <div>
                <label className={labelClass} htmlFor="email">Email</label>
                <input id="email" type="email" autoComplete="email" required value={email}
                  onChange={(e) => setEmail(e.target.value)} className={inputClass} />
              </div>
              {error && <div className={errorBanner} role="alert">{error}</div>}
              <button type="submit" disabled={loading} className={primaryBtn}>
                {loading ? "Sending…" : "Send reset link"}
              </button>
            </form>
            <p className="mt-6 text-center text-sm">
              <Link href="/login" className={mutedLink}>Back to sign in</Link>
            </p>
          </>
        )}
      </div>
    </main>
  );
}

export default function ForgotPasswordPage() {
  return (
    <Suspense>
      <ForgotInner />
    </Suspense>
  );
}
