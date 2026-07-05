import { Resend } from "resend";

// Transactional email via Resend. When RESEND_API_KEY is unset the helper logs
// loudly and returns {ok:false} instead of throwing, so register/forgot-password
// still return their generic success response (email is best-effort).
const RESEND_API_KEY = process.env.RESEND_API_KEY;
const EMAIL_FROM = process.env.EMAIL_FROM ?? "Casaval <onboarding@resend.dev>";
// Where replies to verification/reset emails go (e.g. hello@casaval.eu, once an
// inbound provider forwards it). Falls back to the From address when unset.
const EMAIL_REPLY_TO = process.env.EMAIL_REPLY_TO;
// AUTH_URL is already the public site origin in prod (https://casaval.eu).
const APP_URL = process.env.AUTH_URL ?? process.env.APP_URL ?? "http://localhost:3000";

let client: Resend | null = null;
const getClient = () => (RESEND_API_KEY ? (client ??= new Resend(RESEND_API_KEY)) : null);

type SendResult = { ok: true; id: string } | { ok: false; error: string };

async function send(to: string, subject: string, text: string): Promise<SendResult> {
  const resend = getClient();
  if (!resend) {
    // Don't log the recipient address (PII) — subject is enough to diagnose.
    console.error("[email] RESEND_API_KEY not set — email NOT sent.", JSON.stringify({ subject }));
    return { ok: false, error: "email_not_configured" };
  }
  try {
    const { data, error } = await resend.emails.send({
      from: EMAIL_FROM,
      to,
      subject,
      text,
      ...(EMAIL_REPLY_TO ? { replyTo: EMAIL_REPLY_TO } : {}),
    });
    if (error) {
      console.error("[email] Resend rejected:", error.name, error.message);
      return { ok: false, error: error.message };
    }
    return { ok: true, id: data!.id };
  } catch (err) {
    console.error("[email] send threw:", err);
    return { ok: false, error: "email_send_failed" };
  }
}

export function sendVerificationEmail(to: string, rawToken: string) {
  const url = `${APP_URL}/verify?token=${rawToken}&email=${encodeURIComponent(to)}`;
  return send(to, "Confirm your Casaval email", verifyBody(url));
}

export function sendPasswordResetEmail(to: string, rawToken: string) {
  const url = `${APP_URL}/reset-password?token=${rawToken}&email=${encodeURIComponent(to)}`;
  return send(to, "Reset your Casaval password", resetBody(url));
}

const verifyBody = (url: string) =>
  [
    "Welcome to Casaval.",
    "",
    "Confirm your email to activate your account and start running property",
    "valuations for Malta, Bulgaria, Cyprus and Croatia:",
    "",
    url,
    "",
    "This link expires in 24 hours. If you didn't create a Casaval account, ignore this email.",
    "",
    "— The Casaval team",
  ].join("\n");

const resetBody = (url: string) =>
  [
    "We received a request to reset your Casaval password.",
    "",
    "Set a new password here:",
    "",
    url,
    "",
    "This link expires in 1 hour and can be used once. If you didn't request a reset, ignore this email.",
    "",
    "— The Casaval team",
  ].join("\n");
