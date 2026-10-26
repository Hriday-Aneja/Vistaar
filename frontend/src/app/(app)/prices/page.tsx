"use client";
import { Async, Empty, Head, Table } from "@/components/ui";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

export default function Prices() {
  const { data, error, loading, reload } = useLoad(() => api<any[]>("/prices/radar"));
  return (
    <>
      <Head title="Fair-price radar" sub="Distributor ka quote us daam se milao jo doosre pool ne sach me diya." />
      <Async loading={loading} error={error} reload={reload}>
        {data && data.length ? (
          <Table head={[{ label: "Maal" }, { label: "Benchmark", num: true }, { label: "Quotes" }, { label: "Auction ke baad" }]}>
            {data.map((r: any) => (
              <tr key={r.product_id}>
                <td><strong>{r.product}</strong><div className="sub">MRP {r.mrp}</div></td>
                <td className="num">{r.benchmark ?? "-"}</td>
                <td>
                  {r.quotes.map((q: any) => (
                    <div key={q.distributor}>
                      {q.distributor}: {q.unit_price}
                      {q.flag ? <span className="flag"> {q.flag.pct_over}% upar</span> : null}
                      <span className="sub"> (min {q.min_qty})</span>
                    </div>
                  ))}
                </td>
                <td>{r.quotes.map((q: any) => <div key={q.distributor}>{q.after_auction}</div>)}</td>
              </tr>
            ))}
          </Table>
        ) : <Empty title="Abhi koi quote nahi" />}
        <p className="note">
          Benchmark doosre pools ke asli bhare daam ka median hai, aur tabhi dikhta hai jab kam se kam 5 orders hon.
          Kisi ek order ka daam kabhi nahi dikhta.
        </p>
      </Async>
    </>
  );
}
