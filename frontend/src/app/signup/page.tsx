"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { GoogleButton, OrDivider } from "@/components/GoogleButton";
import { track } from "@/lib/analytics";
import {
  card,
  cardWrap,
  errorBanner,
  inputClass,
  labelClass,
  mutedLink,
  primaryBtn,
  successBanner,
} from "@/lib/ui";

function SignupInner() {
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") || "/mt/valuation";
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) return setError("Password must be at least 8 characters.");
    if (password !== confirm) return setError("Passwords don't match.");
    setLoading(true);
    track("signup_submitted", {});
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name || undefined, email, password }),
      });
      setLoading(false);
      if (!res.ok) {
        setError("Couldn't create the account. Check your details and try again.");
        return;
      }
      setDone(true);
    } catch {
      setLoading(false);
      setError("Network error. Please try again.");
    }
  }

  if (done) {
    return (
      <main className={cardWrap}>
        <div className={`${card} text-center`}>
          <h1 className="text-2xl font-bold text-[var(--color-primary)]">Check your email</h1>
          <div className={`${successBanner} mt-4 text-left`}>
            We sent a confirmation link to <strong>{email}</strong>. Click it to activate your
            account, then sign in. The link expires in 24 hours.
          </div>
          <p className="mt-6 text-sm">
            <Link href="/login" className={mutedLink}>Back to sign in</Link>
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className={cardWrap}>
      <div className={card}>
        <div className="text-center">
          <h1 className="text-2xl font-bold text-[var(--color-primary)]">Create your account</h1>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
            Start running Malta property valuations.
          </p>
        </div>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div>
            <label className={labelClass} htmlFor="name">Name (optional)</label>
            <input id="name" type="text" autoComplete="name" value={name}
              onChange={(e) => setName(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass} htmlFor="email">Email</label>
            <input id="email" type="email" autoComplete="email" required value={email}
              onChange={(e) => setEmail(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass} htmlFor="password">Password</label>
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
            {loading ? "Creating account…" : "Create account"}
          </button>
        </form>

        <div className="my-6"><OrDivider /></div>
        <GoogleButton callbackUrl={callbackUrl} />

        <p className="mt-6 text-center text-xs text-[var(--color-text-secondary)]">
          Already have an account?{" "}
          <Link href="/login" className={mutedLink}>Sign in</Link>
        </p>
      </div>
    </main>
  );
}

export default function SignupPage() {
  return (
    <Suspense>
      <SignupInner />
    </Suspense>
  );
}
