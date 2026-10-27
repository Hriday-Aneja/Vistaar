"use client";
import Link from "next/link";
import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { Badge, Head } from "@/components/ui";
import { api, inr, openPdf } from "@/lib/api";
import { toast } from "@/lib/toast";

type Msg = { id: number; from: "me" | "bot"; body: ReactNode };

const RISK: Record<string, string> = { Low: "Kam risk", Medium: "Thoda risk", High: "Zyada risk" };
const CHIPS = ["Diwali ka maal plan karo", "Rahul bhai ko udhaar du?", "Kaunsa maal expire hoga?", "Bikri kaisi chal rahi hai?"];

function PlanBubble({ plan }: { plan: any }) {
  const [orders, setOrders] = useState<number[] | null>(null);
  const [busy, setBusy] = useState(false);
  const mine = plan.lines.filter((l: any) => l.my_qty > 0);

  async function approve() {
    setBusy(true);
    try {
      const r = await api("/orders/" + plan.thread_id + "/approve", { method: "POST" });
      setOrders(r.order_ids);
      toast("Order place ho gaya");
    } catch (e: any) { toast(e.message, true); }
    finally { setBusy(false); }
  }

  if (!mine.length) {
    return <p>Abhi aapke liye koi maal order karne layak nahi mila. Pool me kam se kam 5 dukaan chahiye, aur stock kam hona chahiye.</p>;
  }
  return (
    <div>
      <p>{plan.cohort_size} dukaan ek saath. Aapki bachat: <strong>{inr(plan.savings_estimate)}</strong> <span className="sub">({plan.savings_basis})</span></p>
      {mine.map((l: any) => (
        <div key={l.product_id} style={{ marginTop: 8 }}>
          <strong>{l.product}</strong>: {l.my_qty} @ {l.unit_price} ({l.distributor}, {l.delivery_days} din)
          {l.flag_on_list_price ? <div className="flag">List quote {l.flag_on_list_price.pct_over}% mehenga tha</div> : null}
          <div className="sub">{l.reason}</div>
        </div>
      ))}
      <p className="note">Forecast: {plan.forecast_method}. Live auction Bulk-buy page par dikhta hai.</p>
      <div className="row">
        {orders ? orders.map((id) => (
          <button key={id} className="btn ghost" onClick={() => openPdf(`/orders/${id}/po.pdf`).catch((e) => toast(e.message, true))}>PO #{id} dekho</button>
        )) : <button className="btn" onClick={approve} disabled={busy}>Approve order</button>}
      </div>
    </div>
  );
}

function UdhaarBubble({ d }: { d: any }) {
  const n = d.network;
  return (
    <div>
      <p><strong>{d.customer.display_name}</strong>: aapke yahan Rs {d.customer.pending} baaki.</p>
      {n.status !== "ok" ? (
        <div><Badge kind="none">Data kam hai</Badge><p className="sub">{n.message}</p></div>
      ) : (
        <div>
          <Badge kind={n.level.toLowerCase()}>{RISK[n.level]}</Badge>{" "}
          <span>Suggested limit: <strong>{inr(n.suggested_limit)}</strong></span>
          <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{n.reasons.map((r: string) => <li key={r}>{r}</li>)}</ul>
        </div>
      )}
      <p className="note">Privacy: {n.privacy}</p>
    </div>
  );
}

function PickBubble({ q, matches, onPick }: { q: string; matches: any[]; onPick: (id: number) => void }) {
  return (
    <div>
      <p>{q}</p>
      <div className="row">
        {matches.map((m) => <button key={m.id} className="btn ghost" onClick={() => onPick(m.id)}>{m.display_name} ({m.phone_masked})</button>)}
      </div>
    </div>
  );
}

function SwapBubble({ s }: { s: any }) {
  if (!s.proposals.length) return <p>{s.message ?? "Abhi koi swap nahi."}</p>;
  return (
    <div>
      {s.proposals.map((p: any) => (
        <div key={p.batch_id + "-" + p.to_shop_id} style={{ marginTop: 8 }}>
          <strong>{p.role === "send" ? "Bhejo" : "Aane wala"}:</strong> {p.qty} {p.product}, {p.from_shop} se {p.to_shop}
          <div className="sub">{p.why}</div>
        </div>
      ))}
      <p className="note">Swap approve karne ke liye <Link href="/swaps">Swap page</Link> kholo. Maal lene wali dukaan approve karti hai.</p>
    </div>
  );
}

function PulseBubble({ pulse, drops }: { pulse: any; drops: any }) {
  return (
    <div>
      {drops.drop ? (
        <p><strong className="flag">Bikri gir rahi hai:</strong> pichhle {drops.drop.recent_days} din roz ~{drops.drop.recent} units, aam din ~{drops.drop.baseline} ({drops.drop.drop_pct}% kam).</p>
      ) : <p>{drops.message}</p>}
      {pulse.alerts.length ? pulse.alerts.map((a: any) => (
        <div key={a.product_id} style={{ marginTop: 8 }}>
          <strong>{a.product}</strong>: {a.shops_spiking} dukaan me {a.uplift}x uchhaal. <strong>{a.action}</strong>
          <div className="sub">{a.why}</div>
        </div>
      )) : <p className="sub">{pulse.message}</p>}
    </div>
  );
}

export default function Chat() {
  const [msgs, setMsgs] = useState<Msg[]>([
    { id: 0, from: "bot", body: "Namaste! Main Vistaar hoon. Maal ka plan, udhaar ka risk, expiry swap ya bikri, kuch bhi poochho." },
  ]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const nextId = useRef(1);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [msgs]);

  const push = (from: "me" | "bot", body: ReactNode) =>
    setMsgs((m) => [...m, { id: nextId.current++, from, body }]);

  async function showCustomer(id: number) {
    try {
      push("bot", <UdhaarBubble d={await api("/udhaar/customers/" + id)} />);
    } catch (e: any) { push("bot", e.message); }
  }

  // The backend decides which feature the message is about (LLM first, keyword rules as the fallback).
  // Every feature below is still its own API call; the model never decides quantities, prices or approvals.
  async function route(q: string) {
    const { intent, entities } = await api<{ intent: string; entities: { customer_name?: string } }>(
      "/chat/intent", { method: "POST", body: { text: q } });
    switch (intent) {
      case "udhaar_check": {
        const r = await api("/udhaar/resolve?q=" + encodeURIComponent(entities.customer_name || q));
        if (r.status === "resolved") return showCustomer(r.matches[0].id);
        if (r.status === "ambiguous") return push("bot", <PickBubble q={r.question} matches={r.matches} onPick={showCustomer} />);
        return push("bot", "Is naam ka koi customer aapke khate me nahi mila. Udhaar page par pehle customer jodo.");
      }
      case "swap":
        return push("bot", <SwapBubble s={await api("/swaps/suggestions")} />);
      case "plan_order":
        return push("bot", <PlanBubble plan={await api("/orders/plan", { method: "POST" })} />);
      case "pulse": {
        const [pulse, drops] = await Promise.all([api("/pulse"), api("/pulse/drops")]);
        return push("bot", <PulseBubble pulse={pulse} drops={drops} />);
      }
      case "price_check":
        return push("bot", <p>Distributor ke daam aur unka fair-price check <Link href="/prices">Prices page</Link> par dikhta hai.</p>);
      case "stock":
        return push("bot", <p>Abhi ka stock aur expiry <Link href="/stock">Stock page</Link> par dikhta hai.</p>);
      default:
        return push("bot", "Ye abhi samajh nahi aaya. Maal plan, udhaar risk, expiry swap ya bikri ke baare me poochho.");
    }
  }

  async function ask(q: string) {
    const clean = q.trim();
    if (!clean || busy) return;
    push("me", clean);
    setText("");
    setBusy(true);
    try { await route(clean); }
    catch (e: any) { push("bot", e.message || "Kuch gadbad hui, dobara try karo"); }
    finally { setBusy(false); }
  }

  function onSubmit(e: FormEvent) { e.preventDefault(); ask(text); }

  return (
    <>
      <Head title="Vistaar se poochho" sub="Hinglish me likho. Kuch bhi order ya swap tabhi hota hai jab aap approve karo." />
      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 16 }}>
        {msgs.map((m) => (
          <div key={m.id} style={{
            alignSelf: m.from === "me" ? "flex-end" : "flex-start", maxWidth: "min(560px, 92%)", padding: "10px 14px",
            borderRadius: 12, border: "1px solid var(--line)",
            background: m.from === "me" ? "var(--green-soft)" : "var(--surface)",
          }}>{m.body}</div>
        ))}
        {busy ? <div className="sub" aria-live="polite">Soch raha hoon...</div> : null}
        <div ref={end} />
      </div>
      <div className="row" style={{ marginTop: 16 }}>
        {CHIPS.map((c) => <button key={c} className="btn ghost small" onClick={() => ask(c)} disabled={busy}>{c}</button>)}
      </div>
      <form onSubmit={onSubmit} className="row" style={{ marginTop: 12 }}>
        <input aria-label="Apna sawaal likho" style={{ flex: 1, minWidth: 200 }} value={text}
               onChange={(e) => setText(e.target.value)} placeholder="Jaise: Diwali ka maal kaise karun?" />
        <button className="btn" type="submit" disabled={busy || !text.trim()}>Bhejo</button>
      </form>
    </>
  );
}