"use client";
import { ReactNode } from "react";
import { ErrorState, Head, Loading } from "@/components/ui";
import { api, inr } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

function Card({ title, value, sub, tag }: { title: string; value: ReactNode; sub: string; tag?: string }) {
  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 8, background: "var(--surface)", padding: 16 }}>
      <p className="sub">{title}{tag ? <> · <span style={{ color: "var(--gold)", fontWeight: 500 }}>{tag}</span></> : null}</p>
      <div className="stat">{value}</div>
      <p className="note">{sub}</p>
    </div>
  );
}

function Bar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
  return (
    <div style={{ marginTop: 8 }}>
      <div className="row" style={{ justifyContent: "space-between" }}><span>{label}</span><strong>{inr(value)}</strong></div>
      <div style={{ background: "var(--line)", borderRadius: 4, height: 10 }}>
        <div style={{ width: pct + "%", height: 10, borderRadius: 4, background: "var(--green)" }} />
      </div>
    </div>
  );
}

export default function Impact() {
  const { data, error, loading, reload } = useLoad(() => api("/impact"));
  if (loading) return <Loading />;
  if (error || !data) return <ErrorState message={error ?? "Impact load nahi hua"} onRetry={reload} />;

  const d: any = data;
  const sim = d.simulated ? "projected (simulation)" : undefined;
  const maxUdhaar = Math.max(d.udhaar.recovered_total, d.udhaar.pending);

  return (
    <>
      <Head title="Impact" sub="Vistaar ne aapki dukaan ke liye kya badla." />
      {d.simulated ? (
        <p className="note">Ye numbers demo data par based hain, asli dukaanon ke nahi. Slide par inhe "projected (simulation)" hi likhna.</p>
      ) : null}

      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginTop: 16 }}>
        <Card title="Bulk-buy se bachat" value={inr(d.bulk.saved_estimate)} tag={sim}
              sub={d.bulk.orders ? `${d.bulk.orders} order, ${inr(d.bulk.spent)} ka maal. ${d.bulk.basis}`
                                 : "Abhi koi approved order nahi. Bulk-buy se plan approve karo."} />
        <Card title="Dukaan ek saath" value={d.pool.shops} tag={sim}
              sub={`${d.pool.radius_km} km ke andar. ${d.pool.basis}`} />
        <Card title={`Udhaar wapas (${d.udhaar.recent_days} din)`} value={inr(d.udhaar.recovered_recent)} tag={sim}
              sub={`Ab tak kul ${inr(d.udhaar.recovered_total)} wapas aaya.`} />
        <Card title="Expiry se bacha maal" value={inr(d.swaps.value_moved_out)} tag={sim}
              sub={`${d.swaps.units_moved_out} units doosri dukaan gaye (swap), ${d.swaps.units_received} units aaye.`} />
      </div>

      <div className="section" style={{ border: "1px solid var(--line)", borderRadius: 8, background: "var(--surface)", padding: 16 }}>
        <strong>Udhaar: wapas vs baaki</strong>
        <Bar label="Wapas aaya (kul)" value={d.udhaar.recovered_total} max={maxUdhaar} />
        <Bar label="Abhi baaki" value={d.udhaar.pending} max={maxUdhaar} />
      </div>
    </>
  );
}