"use client";
import { Async, Badge, Empty, Head, Table } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

export default function Pulse() {
  const { data, error, loading, reload } = useLoad(() => api<any>("/pulse"));
  return (
    <>
      <Head title="Mohalla Pulse" sub="Jab paas ki kai dukaanon me ek saath bikri badhe, to pehle se khabar." />
      <Async loading={loading} error={error} reload={reload}>
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
