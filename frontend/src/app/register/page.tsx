"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useRef, useState } from "react";
import { Field } from "@/components/ui";
import { api, session } from "@/lib/api";
import { toast } from "@/lib/toast";

export default function Register() {
  const router = useRouter();
  const form = useRef<HTMLFormElement>(null);
  const [busy, setBusy] = useState(false);

  function locate() {
    if (!navigator.geolocation) return toast("Is phone me location nahi mil rahi", true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const f = form.current!;
        (f.elements.namedItem("lat") as HTMLInputElement).value = pos.coords.latitude.toFixed(5);
        (f.elements.namedItem("lng") as HTMLInputElement).value = pos.coords.longitude.toFixed(5);
        toast("Dukaan ki location mil gayi");
      },
      () => toast("Location nahi mili, haath se daalo", true),
    );
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    try {
      const data = await api("/auth/register", { method: "POST", auth: false, body: {
        phone: f.get("phone"), name: f.get("name"), password: f.get("password"),
        shop_name: f.get("shop_name"), area: f.get("area"),
        lat: parseFloat(String(f.get("lat"))), lng: parseFloat(String(f.get("lng"))),
        upi_vpa: f.get("upi_vpa") || null } });
      session.set(data.token);
      router.replace("/bulk");
    } catch (err: any) { toast(err.message, true); setBusy(false); }
  }

  return (
    <div className="auth">
      <div className="brand">Vistaar</div>
      <p className="sub">Apni dukaan jodo. Sab data aapka apna rahega.</p>
      <form className="box" ref={form} onSubmit={submit}>
        <Field label="Aapka naam"><input name="name" autoComplete="name" required /></Field>
        <Field label="Mobile number"><input name="phone" inputMode="numeric" autoComplete="tel" maxLength={14} required /></Field>
        <Field label="Password (kam se kam 6)"><input name="password" type="password" minLength={6} autoComplete="new-password" required /></Field>
        <Field label="Dukaan ka naam"><input name="shop_name" required /></Field>
        <Field label="Area / mohalla"><input name="area" required /></Field>
        <Field label="UPI ID (khata reminder ke liye, optional)"><input name="upi_vpa" placeholder="naam@bank" /></Field>
        <div className="form-grid">
          <Field label="Latitude"><input name="lat" inputMode="decimal" required /></Field>
          <Field label="Longitude"><input name="lng" inputMode="decimal" required /></Field>
        </div>
        <button className="btn ghost" type="button" onClick={locate}>Meri location lo</button>
        <button className="btn" type="submit" disabled={busy}>Dukaan jodo</button>
      </form>
      <p className="note">Pehle se account hai? <Link href="/login">Login karo</Link></p>
    </div>
  );
}
