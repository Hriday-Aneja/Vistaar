"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import AuthSide from "@/components/AuthSide";
import { Field } from "@/components/ui";
import { api, session } from "@/lib/api";
import { toast } from "@/lib/toast";

export default function Login() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    try {
      const data = await api("/auth/login", { method: "POST", auth: false,
        body: { phone: f.get("phone"), password: f.get("password") } });
      session.set(data.token);
      router.replace("/bulk");
    } catch (err: any) { toast(err.message, true); setBusy(false); }
  }

  return (
    <div className="auth-page">
      <AuthSide />
      <section className="auth-main">
        <div className="auth-card">
      <h2 className="auth-title">Login karo</h2>
      <p className="sub">Apni dukaan me wapas aao.</p>
      <form className="auth-form" onSubmit={submit}>
        <Field label="Mobile number"><input name="phone" inputMode="numeric" autoComplete="tel" maxLength={14} required /></Field>
        <Field label="Password"><input name="password" type="password" autoComplete="current-password" required /></Field>
        <button className="btn" type="submit" disabled={busy}>Login karo</button>
      </form>
      <p className="note">Naye ho? <Link href="/register">Dukaan jodo</Link></p>
      <p className="note">Demo: 9000000001 / vistaar123</p>
        </div>
      </section>
    </div>
  );
}