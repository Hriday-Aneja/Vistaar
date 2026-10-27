"use client";
import { useState } from "react";
import { Async, Badge, Empty, Head, Table } from "@/components/ui";
import { api } from "@/lib/api";
import { toast } from "@/lib/toast";
import { LiveAlert, useLiveAlerts } from "@/lib/useLiveAlerts";
import { useLoad } from "@/lib/useLoad";

export default function Pulse() {
  const { data, error, loading, reload, refresh } = useLoad(() => api<any>("/pulse"));
  const drops = useLoad(() => api<any>("/pulse/drops"));
  const drop = drops.data?.drop;
  const [live, setLive] = useState<LiveAlert[]>([]);
  const refreshAll = () => { refresh(); drops.refresh(); };
  // Pushed alerts show as a toast and a card. If the socket is not available we poll the same APIs every 30 s.
  const { mode } = useLiveAlerts((a) => {
    setLive((prev) => [a, ...prev].slice(0, 5));
    toast(a.title);
    refreshAll();
  }, refreshAll);
  return (
    <>
      <Head title="Mohalla Pulse" sub="Jab paas ki kai dukaanon me ek saath bikri badhe, to pehle se khabar." />
      {mode !== "connecting" ? (
        <p className="note" aria-live="polite">
          {mode === "live" ? "Live alerts chalu hain." : "Live connection nahi mila, har 30 second me khud check kar rahe hain."}
        </p>
      ) : null}
      {live.map((a) => (
        <div key={(a.id ?? "drop") + a.created_at} className="section" role="status"
             style={{ border: "1px solid var(--line)", borderRadius: 8, background: "var(--surface)", padding: 16 }}>
          <strong className={a.kind === "sales_drop" ? "flag" : undefined}>{a.title}</strong>{" "}
          <span className="sub">abhi abhi, {new Date(a.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</span>
          <p>{a.action}</p>
          <div className="sub">{a.why}</div>
        </div>
      ))}
      <Async loading={loading} error={error} reload={reload}>
        {drop ? (
          <div className="section" style={{ border: "1px solid var(--line)", borderRadius: 8, background: "var(--surface)", padding: 16 }}>
            <strong className="flag">Bikri gir rahi hai</strong>
            <p>Pichhle {drop.recent_days} din roz ~{drop.recent} units bike, aam din ~{drop.baseline} ({drop.drop_pct}% kam).</p>
            <p className="note">Pata karo: koi maal khatam to nahi hua, ya dukaan band to nahi rahi? Aaj ki bikri shamil nahi hai.</p>
          </div>
        ) : null}
        {data && data.alerts.length ? (
          <Table head={[{ label: "Maal" }, { label: "Dukaan", num: true }, { label: "Uchhaal", num: true }, { label: "Karan" }, { label: "Kya karein" }, { label: "Kyun?" }]}>
            {data.alerts.map((a: any) => (
              <tr key={a.product_id}>
                <td><strong>{a.product}</strong><div className="sub">{a.category}</div></td>
                <td className="num">{a.shops_spiking}{a.includes_me ? <div className="sub">aapki bhi</div> : null}</td>
                <td className="num"><span className="serif">{a.uplift}x</span></td>
                <td>{a.cause ? <Badge kind="medium">{String(a.cause.label).replace(/\s*\(demo calendar\)/, "")}</Badge> : <Badge kind="none">Pata nahi</Badge>}</td>
                <td><strong>{a.action}</strong><div className="sub">{a.stock} bache, roz ~{a.expected_daily} chahiye</div></td>
                <td><div className="why">{a.why}</div></td>
              </tr>
            ))}
          </Table>
        ) : <Empty title="Abhi sab shaant hai" text={data?.message} />}
        <p className="note">
          Kaise pata chalta hai: pichhle 2 din ki bikri ko usse pehle ke aam din se z-score par naapte hain. Doosri
          dukaanon ke naam ya numbers nahi dikhte, sirf kitni dukaan aur kitna uchhaal.
        </p>
      </Async>
    </>
  );
}