// In-memory fixed-window rate limiter. Per-instance (prod runs a single frontend
// replica), so counters reset on redeploy — acceptable abuse protection for beta.
// If the frontend is ever scaled to multiple replicas, back this with Redis.
const buckets = new Map<string, { n: number; exp: number }>();

// Returns true if the key is still UNDER the limit (request allowed).
export function underLimit(key: string, max: number, windowSec: number): boolean {
  const now = Date.now();
  const entry = buckets.get(key);
  if (!entry || entry.exp < now) {
    buckets.set(key, { n: 1, exp: now + windowSec * 1000 });
    // Opportunistic sweep so abandoned keys don't accumulate unbounded.
    if (buckets.size > 5000) {
      for (const [k, v] of buckets) if (v.exp < now) buckets.delete(k);
    }
    return true;
  }
  entry.n += 1;
  return entry.n <= max;
}

// Trust ONLY the proxy-set header. Caddy overwrites X-Real-IP with the true peer
// and strips inbound X-Forwarded-For, so a client can't spoof this to rotate
// rate-limit buckets. Do NOT fall back to the client-controllable XFF.
export function clientIp(req: Request): string {
  return req.headers.get("x-real-ip") || "unknown";
}
