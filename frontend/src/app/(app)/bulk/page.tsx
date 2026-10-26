"use client";
import { useState } from "react";
import { Empty, Head, Table } from "@/components/ui";
import { api, inr, openPdf } from "@/lib/api";
import { toast } from "@/lib/toast";

export default function Bulk() {
  const [plan, setPlan] = useState<any>(null);
  const [orders, setOrders] = useState<number[] | null>(null);
  const [busy, setBusy] = useState(false);

  async function makePlan() {
    setBusy(true); setOrders(null);
    try { setPlan(await api("/orders/plan", { method: "POST" })); }
    catch (e: any) { toast(e.message, true); }
    finally { setBusy(false); }
  }

  async function approve() {
    setBusy(true);
    try {
      const r = await api("/orders/" + plan.thread_id + "/approve", { method: "POST" });
      setOrders(r.order_ids);
      toast("Order place ho gaya");
    } catch (e: any) { toast(e.message, true); }
    finally { setBusy(false); }
  }

  return (
    <>
      <Head title="Mohalla Bulk-buy" sub="Paas ki dukaanon ke saath milkar kharido, sasta maal, ek tap me." />
      <div className="row">
        <button className="btn" onClick={makePlan} disabled={busy}>Diwali ka maal plan karo</button>
      </div>

      {!plan ? <Empty title="Abhi koi plan nahi" text="Button dabao, hum forecast, mohalla pool aur distributor quotes nikal denge." /> : (
        <>
          <p className="sub">
            {plan.cohort_size} dukaan ek saath. Aapki bachat: <span className="stat">{inr(plan.savings_estimate)}</span>
            {" "}({plan.savings_basis})
          </p>
          <Table head={[{ label: "Maal" }, { label: "Pool qty", num: true }, { label: "Aapki qty", num: true },
                        { label: "Distributor" }, { label: "Daam", num: true }, { label: "Bachat", num: true }]}>
            {plan.lines.map((l: any) => (
              <tr key={l.product_id}>
                <td><strong>{l.product}</strong>
                  {l.flag_on_list_price ? <div className="flag">Quote {l.flag_on_list_price.pct_over}% mehenga tha (benchmark {l.benchmark})</div> : null}
                </td>
                <td className="num">{l.pooled_qty}</td>
                <td className="num">{l.my_qty}</td>
                <td>{l.distributor}<div className="sub">{l.delivery_days} din me delivery</div></td>
                <td className="num">{l.unit_price}<div className="sub">list {l.list_price}</div></td>
                <td className="num">{inr(l.my_saving)}</td>
              </tr>
            ))}
          </Table>
          {plan.auction_log.length ? (
            <details className="panel section">
              <summary>Distributor auction ({plan.auction_log.length} bid)</summary>
              <ul className="log">
                {plan.auction_log.map((e: any, i: number) => (
                  <li key={i}>Round {e.round}: {e.product}, distributor #{e.distributor_id} ne daam {e.price} kiya</li>
                ))}
              </ul>
            </details>
          ) : null}
          <p className="note">
            Pool ki qty privacy ke liye thodi noisy hoti hai, aur sirf tab dikhti hai jab kam se kam 5 dukaan judi hon.
            Demo me paas ki dukaanen pool me pehle se judi maani gayi hain.
          </p>
          <div className="row" style={{ marginTop: 16 }}>
            {orders ? orders.map((id) => (
              <button key={id} className="btn ghost" onClick={() => openPdf(`/orders/${id}/po.pdf`).catch((e) => toast(e.message, true))}>
                PO #{id} dekho
              </button>
            )) : <button className="btn" onClick={approve} disabled={busy || !plan.lines.length}>Approve order</button>}
          </div>
        </>
      )}
    </>
  );
}
