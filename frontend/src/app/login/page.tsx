"use client";

import { signIn } from "next-auth/react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { GoogleButton, OrDivider } from "@/components/GoogleButton";
import { track } from "@/lib/analytics";
import { card, cardWrap, errorBanner, inputClass, labelClass, mutedLink, primaryBtn } from "@/lib/ui";

function LoginInner() {
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") || "/mt/valuation";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    track("login_clicked", { provider: "credentials" });
    const res = await signIn("credentials", { email, password, redirect: false });
    setLoading(false);
    if (!res || res.error) {
      setError("Invalid email or password, or your email isn't verified yet.");
      return;
    }
    window.location.href = res.url ?? callbackUrl;
  }

  return (
    <main className={cardWrap}>
      <div className={card}>
        <div className="text-center">
          <h1 className="text-2xl font-bold text-[var(--color-primary)]">Casaval</h1>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
            Sign in to run Malta property valuations.
          </p>
        </div>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div>
            <label className={labelClass} htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
          </div>
          {error && <div className={errorBanner} role="alert">{error}</div>}
          <button type="submit" disabled={loading} className={primaryBtn}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="mt-3 text-right">
          <Link href="/forgot-password" className={`text-xs ${mutedLink}`}>Forgot password?</Link>
        </div>

        <div className="my-6"><OrDivider /></div>
        <GoogleButton callbackUrl={callbackUrl} />

        <p className="mt-6 text-center text-xs text-[var(--color-text-secondary)]">
          Don&apos;t have an account?{" "}
          <Link href={`/signup?callbackUrl=${encodeURIComponent(callbackUrl)}`} className={mutedLink}>
            Create one
          </Link>
        </p>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  );
}
