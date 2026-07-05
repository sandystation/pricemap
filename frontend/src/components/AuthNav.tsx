"use client";

import { signOut, useSession } from "next-auth/react";
import Link from "next/link";

const linkCls = "text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text)]";

// Auth-aware header controls: History + Sign out when signed in, otherwise Sign in.
export function AuthNav() {
  const { data: session, status } = useSession();
  if (status === "loading") return null;

  if (session?.user) {
    return (
      <div className="flex items-center gap-4">
        <Link href="/account/history" className={linkCls}>History</Link>
        <button type="button" onClick={() => signOut({ callbackUrl: "/" })} className={linkCls}>
          Sign out
        </button>
      </div>
    );
  }
  return (
    <Link href="/login" className={linkCls}>Sign in</Link>
  );
}
