"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { track } from "@/lib/analytics";
import { card, cardWrap, errorBanner, mutedLink, primaryBtn, successBanner } from "@/lib/ui";

type Status = "loading" | "success" | "error";

function VerifyInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const email = params.get("email");
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    track("verify_viewed", {});
    if (!token || !email) {
      setStatus("error");
      return;
    }
    fetch("/api/auth/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, email }),
    })
      .then((res) => setStatus(res.ok ? "success" : "error"))
      .catch(() => setStatus("error"));
  }, [token, email]);

  return (
    <main className={cardWrap}>
      <div className={`${card} text-center`}>
        <h1 className="text-2xl font-bold text-[var(--color-primary)]">Casaval</h1>
        {status === "loading" && (
          <p className="mt-6 text-sm text-[var(--color-text-secondary)]">Verifying your email…</p>
        )}
        {status === "success" && (
          <>
            <div className={`${successBanner} mt-6 text-left`}>
              Your email is verified. You can now sign in.
            </div>
            <Link href="/login" className={`${primaryBtn} mt-6 inline-block`}>Continue to sign in</Link>
          </>
        )}
        {status === "error" && (
          <>
            <div className={`${errorBanner} mt-6 text-left`}>
              This verification link is invalid or has expired.
            </div>
            <p className="mt-6 text-sm text-[var(--color-text-secondary)]">
              <Link href="/signup" className={mutedLink}>Create an account</Link>
              {" · "}
              <Link href="/login" className={mutedLink}>Sign in</Link>
            </p>
          </>
        )}
      </div>
    </main>
  );
}

export default function VerifyPage() {
  return (
    <Suspense>
      <VerifyInner />
    </Suspense>
  );
}
