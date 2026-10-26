"use client";
import { useEffect, useState } from "react";
import { Async, Badge, Empty, Head, Table } from "@/components/ui";
import { api, inr } from "@/lib/api";
import { toast } from "@/lib/toast";
import { useLoad } from "@/lib/useLoad";

const STATUS: Record<string, string> = { proposed: "Intezaar", approved: "Manzoor", rejected: "Mana kiya" };

export default function Swaps() {
  const [myShop, setMyShop] = useState<number | null>(null);
  useEffect(() => { api("/auth/me").then((u) => setMyShop(u.shop.id)); }, []);
  const { data, error, loading, reload } = useLoad(async () => ({
    s: await api<any>("/swaps/suggestions"), mine: await api<any[]>("/swaps"),
  }));

  async function act(path: string, body: unknown, ok: string) {
    try { await api(path, { method: "POST", body }); toast(ok); reload(); }
    catch (e: any) { toast(e.message, true); }
  }

  return (
    <>
      <Head title="Mohalla Swap" sub="Jo maal bikega nahi, wo paas ki dukaan ko do jahan kami hai. Poore mohalle ka best match ek saath nikalta hai." />
      <Async loading={loading} error={error} reload={reload}>
        {data && data.s.proposals.length ? (
          <Table head={[{ label: "Maal" }, { label: "Kahan se, kahan" }, { label: "Qty", num: true }, { label: "Bachat", num: true }, { label: "Score", num: true }, { label: "Kyun?" }, { label: "" }]}>
            {data.s.proposals.map((p: any) => (
              <tr key={`${p.batch_id}-${p.to_shop_id}`}>
                <td><strong>{p.product}</strong></td>
                <td>{p.from_shop} to {p.to_shop}</td>
                <td className="num">{p.qty}</td>
                <td className="num">{inr(p.value_saved)}</td>
                <td className="num"><span className="serif">{p.score}</span></td>
                <td>
                  <div className="why">{p.why}
                    <details><summary>Score ka hisaab</summary>
                      <table className="mini"><tbody>
                        {p.breakdown.map((b: any) => <tr key={b.factor}><td>{b.label}</td><td>{b.detail}</td><td className="num">{b.points}/{b.weight}</td></tr>)}
                      </tbody></table>
                    </details>
                  </div>
                </td>
                <td>
                  {p.role === "send"
                    ? <button className="btn small" onClick={() => act("/swaps", { batch_id: p.batch_id, to_shop_id: p.to_shop_id }, "Swap bhej diya")}>Swap bhejna hai?</button>
                    : <span className="sub">{p.from_shop} bhej sakti hai</span>}
                </td>
              </tr>
            ))}
          </Table>
        ) : <Empty title="Abhi koi swap nahi" text={data?.s.message} />}

        <div className="section">
          <h2>Mere swaps</h2>
          <div style={{ marginTop: 16 }}>
            {data && data.mine.length ? (
              <Table head={[{ label: "Maal" }, { label: "Kahan se, kahan" }, { label: "Qty", num: true }, { label: "Score", num: true }, { label: "Haal" }, { label: "" }]}>
                {data.mine.map((s: any) => (
                  <tr key={s.id}>
                    <td><strong>{s.product}</strong></td>
                    <td>{s.from_shop} to {s.to_shop}</td>
                    <td className="num">{s.qty}</td>
                    <td className="num">{s.score}</td>
                    <td><Badge kind={s.status}>{STATUS[s.status]}</Badge></td>
                    <td>
                      {s.status === "proposed" ? (
                        <div className="row">
                          {s.to_shop_id === myShop ? <button className="btn small" onClick={() => act(`/swaps/${s.id}/approve`, undefined, "Swap manzoor, stock aa gaya")}>Manzoor</button> : null}
                          <button className="btn small ghost" onClick={() => act(`/swaps/${s.id}/reject`, undefined, "Swap mana kiya")}>Mana karo</button>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </Table>
            ) : <Empty title="Abhi koi swap nahi" text="Jab swap bhejoge ya aayega, yahan dikhega." />}
          </div>
        </div>
      </Async>
    </>
  );
}
