"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { track } from "@/lib/analytics";
import { card, cardWrap, errorBanner, inputClass, labelClass, mutedLink, primaryBtn, successBanner } from "@/lib/ui";

function ResetInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const email = params.get("email");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  if (!token || !email) {
    return (
      <main className={cardWrap}>
        <div className={`${card} text-center`}>
          <h1 className="text-2xl font-bold text-[var(--color-primary)]">Casaval</h1>
          <div className={`${errorBanner} mt-6 text-left`}>This reset link is invalid.</div>
          <p className="mt-6 text-sm">
            <Link href="/forgot-password" className={mutedLink}>Request a new link</Link>
          </p>
        </div>
      </main>
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) return setError("Password must be at least 8 characters.");
    if (password !== confirm) return setError("Passwords don't match.");
    setLoading(true);
    track("reset_submitted", {});
    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, email, password }),
      });
      setLoading(false);
      if (!res.ok) {
        setError("This reset link is invalid or has expired.");
        return;
      }
      setDone(true);
    } catch {
      setLoading(false);
      setError("Network error. Please try again.");
    }
  }

  return (
    <main className={cardWrap}>
      <div className={card}>
        <div className="text-center">
          <h1 className="text-2xl font-bold text-[var(--color-primary)]">Set a new password</h1>
        </div>
        {done ? (
          <>
            <div className={`${successBanner} mt-6`}>
              Your password has been updated. You can now sign in.
            </div>
            <Link href="/login" className={`${primaryBtn} mt-6 inline-block text-center`}>
              Continue to sign in
            </Link>
          </>
        ) : (
          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <label className={labelClass} htmlFor="password">New password</label>
              <input id="password" type="password" autoComplete="new-password" required minLength={8}
                value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} />
              <p className="mt-1 text-xs text-gray-400">At least 8 characters.</p>
            </div>
            <div>
              <label className={labelClass} htmlFor="confirm">Confirm password</label>
              <input id="confirm" type="password" autoComplete="new-password" required minLength={8}
                value={confirm} onChange={(e) => setConfirm(e.target.value)} className={inputClass} />
            </div>
            {error && <div className={errorBanner} role="alert">{error}</div>}
            <button type="submit" disabled={loading} className={primaryBtn}>
              {loading ? "Updating…" : "Update password"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetInner />
    </Suspense>
  );
}
