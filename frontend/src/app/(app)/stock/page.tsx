"use client";
import { FormEvent, useEffect, useState } from "react";
import { Async, Badge, Empty, Field, Head, Table } from "@/components/ui";
import { api, fmtDate } from "@/lib/api";
import { toast } from "@/lib/toast";
import { useLoad } from "@/lib/useLoad";

const RISK: Record<string, string> = { none: "Khatam", expired: "Expire", high: "Zyada risk", medium: "Thoda risk", low: "Theek" };
const SRC: Record<string, string> = { entered: "daali gayi", default: "andaaza", inferred: "andaaza" };

// YYYY-MM-DD in the shop's local time, for the date input (the server allows today back to 60 days ago)
const isoDay = (daysAgo = 0) => {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export default function Stock() {
  const { data, error, loading, reload } = useLoad(async () => ({
    rows: await api<any[]>("/stock"), categories: await api<any[]>("/categories"),
  }));
  const [names, setNames] = useState<string[]>([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    const t = setTimeout(() => api<any[]>("/products?q=" + encodeURIComponent(q)).then((r) => setNames(r.map((p) => p.name))).catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [q]);

  async function addBatch(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const body: any = { product_name: String(f.get("name")).trim(), category: f.get("category"), qty: Number(f.get("qty")),
      cost_price: Number(f.get("cost")), sell_price: Number(f.get("sell")) };
    if (f.get("expiry")) body.expiry_date = f.get("expiry");
    try {
      const r = await api("/stock/batches", { method: "POST", body });
      toast(`${r.product} jud gaya, expiry ${fmtDate(r.expiry_date)}`);
      form.reset(); reload();
    } catch (err: any) { toast(err.message, true); }
  }

  async function sell(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const body: any = { product_id: Number(f.get("product")), qty: Number(f.get("qty")) };
    const day = String(f.get("sold_on") ?? "");
    if (day && day !== isoDay()) body.sold_on = day; // today = no date, the server stamps "now"
    try {
      await api("/sales", { method: "POST", body });
      toast("Bikri likh li"); form.reset(); reload();
    } catch (err: any) { toast(err.message, true); }
  }

  const products = new Map<number, { name: string; qty: number }>();
  (data?.rows ?? []).forEach((r) => products.set(r.product_id, { name: r.product, qty: (products.get(r.product_id)?.qty ?? 0) + r.qty_left }));

  return (
    <>
      <Head title="Mera stock" sub="Har batch ki expiry aur risk, Kyun? ke saath." />
      <Async loading={loading} error={error} reload={reload}>
        <details className="panel"><summary>Maal aaya</summary>
          <form onSubmit={addBatch}>
            <div className="form-grid">
              <Field label="Maal ka naam"><input name="name" list="product-names" required autoComplete="off" onChange={(e) => setQ(e.target.value)} /></Field>
              <datalist id="product-names">{names.map((n) => <option key={n} value={n} />)}</datalist>
              <Field label="Category"><select name="category" required>
                {(data?.categories ?? []).map((c: any) => <option key={c.name} value={c.name}>{c.name} ({c.default_shelf_days} din)</option>)}
              </select></Field>
              <Field label="Kitna aaya"><input name="qty" type="number" min={1} required inputMode="numeric" /></Field>
              <Field label="Kharid daam"><input name="cost" type="number" min={0} step="0.01" required /></Field>
              <Field label="Bechne ka daam"><input name="sell" type="number" min={0.01} step="0.01" required /></Field>
              <Field label="Expiry"><input name="expiry" type="date" /></Field>
            </div>
            <p className="sub">Expiry nahi pata to khali chhodo</p>
            <button className="btn" type="submit">Jodo</button>
          </form>
        </details>
        {products.size ? (
          <details className="panel"><summary>Bikri likho</summary>
            <form onSubmit={sell}>
              <div className="form-grid">
                <Field label="Kya bika"><select name="product" required>
                  {[...products].map(([id, p]) => <option key={id} value={id}>{p.name} ({p.qty} bache)</option>)}
                </select></Field>
                <Field label="Kitna"><input name="qty" type="number" min={1} required inputMode="numeric" /></Field>
                <Field label="Kis din bika"><input name="sold_on" type="date" defaultValue={isoDay()} min={isoDay(60)} max={isoDay()} /></Field>
              </div>
              <p className="sub">Purani bikri likhni ho to date badlo (60 din tak).</p>
              <button className="btn" type="submit">Bikri likho</button>
            </form>
          </details>
        ) : null}
        {data && data.rows.length ? (
          <Table head={[{ label: "Maal" }, { label: "Bacha", num: true }, { label: "Expiry" }, { label: "Roz bikri", num: true }, { label: "Risk" }, { label: "Kyun?" }]}>
            {data.rows.map((r) => (
              <tr key={r.batch_id}>
                <td><strong>{r.product}</strong><div className="sub">{r.category}</div></td>
                <td className="num">{r.qty_left}</td>
                <td>{fmtDate(r.expiry_date)}<div className="sub">{SRC[r.expiry_source] ?? r.expiry_source}</div></td>
                <td className="num">{r.daily_rate.toFixed(1)}</td>
                <td><Badge kind={r.risk.level}>{RISK[r.risk.level]}</Badge></td>
                <td><div className="why">{r.risk.why}</div></td>
              </tr>
            ))}
          </Table>
        ) : <Empty title="Abhi koi stock nahi hai" text={'Upar "Maal aaya" se pehla batch jodo.'} />}
      </Async>
    </>
  );
}