"use client";
import { FormEvent, useState } from "react";
import { Async, Empty, Field, Head } from "@/components/ui";
import { api, inr } from "@/lib/api";
import { toast } from "@/lib/toast";
import { useLoad } from "@/lib/useLoad";

const BOX = { border: "1px solid var(--line)", borderRadius: 8, background: "var(--surface)", padding: 16, marginBottom: 16 };
const inDays = (n: number) => new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);

function QuoteForm({ distributorId, onDone }: { distributorId: number; onDone: () => void }) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<any[]>([]);
  const [productId, setProductId] = useState("");
  const [price, setPrice] = useState("");
  const [minQty, setMinQty] = useState("10");
  const [days, setDays] = useState("2");
  const [till, setTill] = useState(inDays(7));
  const [busy, setBusy] = useState(false);

  async function search() {
    try {
      const rows = await api("/products?q=" + encodeURIComponent(q));
      setFound(rows);
      setProductId(rows.length ? String(rows[0].id) : "");
    } catch (e: any) { toast(e.message, true); }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api(`/distributors/${distributorId}/quotes`, {
        method: "POST",
        body: { product_id: Number(productId), unit_price: Number(price), min_qty: Number(minQty),
                delivery_days: Number(days), valid_till: till },
      });
      toast("Quote save ho gaya");
      setPrice("");
      onDone();
    } catch (err: any) { toast(err.message, true); }
    finally { setBusy(false); }
  }

  return (
    <form onSubmit={submit} style={{ marginTop: 12 }}>
      <div className="row">
        <input aria-label="Product khojo" placeholder="Product khojo (jaise Atta)" value={q} onChange={(e) => setQ(e.target.value)} />
        <button type="button" className="btn ghost" onClick={search}>Khojo</button>
      </div>
      {found.length ? (
        <div className="row" style={{ marginTop: 8 }}>
          <Field label="Product">
            <select value={productId} onChange={(e) => setProductId(e.target.value)}>
              {found.map((p) => <option key={p.id} value={p.id}>{p.name} (MRP {p.mrp})</option>)}
            </select>
          </Field>
          <Field label="Daam (Rs per unit)"><input type="number" step="0.01" min="0" required value={price} onChange={(e) => setPrice(e.target.value)} /></Field>
          <Field label="Kam se kam qty"><input type="number" min="1" required value={minQty} onChange={(e) => setMinQty(e.target.value)} /></Field>
          <Field label="Delivery (din)"><input type="number" min="0" max="30" required value={days} onChange={(e) => setDays(e.target.value)} /></Field>
          <Field label="Quote valid till"><input type="date" required value={till} onChange={(e) => setTill(e.target.value)} /></Field>
          <button className="btn" type="submit" disabled={busy || !price}>Quote save karo</button>
        </div>
      ) : null}
    </form>
  );
}

export default function Distributors() {
  const { data, error, loading, reload } = useLoad(() => api<any[]>("/distributors"));
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);

  async function add(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/distributors", { method: "POST", body: { name, phone: phone || null } });
      setName(""); setPhone("");
      reload();
    } catch (err: any) { toast(err.message, true); }
    finally { setBusy(false); }
  }

  return (
    <>
      <Head title="Distributor aur quotes" sub="Apne distributor ke asli daam yahan daalo. Bulk-buy inhi quotes se chalta hai." />
      <form onSubmit={add} style={BOX}>
        <strong>Naya distributor</strong>
        <div className="row" style={{ marginTop: 8 }}>
          <Field label="Naam"><input required minLength={2} value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Mobile (optional)"><input inputMode="numeric" value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
          <button className="btn" type="submit" disabled={busy || name.trim().length < 2}>Jodo</button>
        </div>
      </form>
      <Async loading={loading} error={error} reload={reload}>
        {data && data.length === 0 ? <Empty title="Abhi koi distributor nahi hai" text="Upar se jodo." /> : null}
        {(data ?? []).map((d: any) => (
          <div key={d.id} style={BOX}>
            <strong>{d.name}</strong> {d.phone ? <span className="sub">{d.phone}</span> : null}
            {d.quotes.length ? (
              <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                {d.quotes.map((q: any) => (
                  <li key={q.id}>
                    {q.product}: {inr(q.unit_price)}, kam se kam {q.min_qty}, {q.delivery_days} din, {q.valid_till} tak
                    {q.expired ? <span className="flag"> (expire ho gaya)</span> : null}
                  </li>
                ))}
              </ul>
            ) : <p className="sub">Abhi koi quote nahi.</p>}
            {d.mine ? <QuoteForm distributorId={d.id} onDone={reload} /> : <p className="note">Is distributor ke quote sirf jisne joda wahi badal sakta hai.</p>}
          </div>
        ))}
      </Async>
    </>
  );
}