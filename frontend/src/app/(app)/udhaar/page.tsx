"use client";
import { FormEvent, useState } from "react";
import { Async, Badge, Empty, Field, Head, Table } from "@/components/ui";
import { api, fmtDate, inr } from "@/lib/api";
import { toast } from "@/lib/toast";
import { useLoad } from "@/lib/useLoad";

const RISK: Record<string, string> = { Low: "Kam risk", Medium: "Thoda risk", High: "Zyada risk" };

function Network({ n }: { n: any }) {
  if (n.status !== "ok") {
    return <div><Badge kind="none">Data kam hai</Badge><p className="sub">{n.message}</p></div>;
  }
  return (
    <div>
      <div className="row">
        <Badge kind={n.level.toLowerCase()}>{RISK[n.level]}</Badge>
        <span>Limit: <span className="serif">{inr(n.suggested_limit)}</span></span>
        <span>Abhi ki gunjaish: <span className="serif">{inr(n.room_left)}</span></span>
      </div>
      <div className="why" style={{ marginTop: 8 }}>
        <strong>Kyun?</strong>
        <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{n.reasons.map((r: string) => <li key={r}>{r}</li>)}</ul>
      </div>
    </div>
  );
}

function CustomerCard({ id, onChange }: { id: number; onChange: () => void }) {
  const { data, error, loading, reload } = useLoad(() => api<any>("/udhaar/customers/" + id));
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");

  async function send(kind: "credit" | "payment") {
    const value = Number(amount);
    if (!value) return toast("Rupaye daalo", true);
    const room = data.network.room_left;
    if (kind === "credit" && room !== null && value > room && !confirm("Ye suggested limit se zyada hai. Phir bhi likhna hai?")) return;
    try {
      await api("/udhaar/entries", { method: "POST", body: { customer_id: id, kind, amount: value, note: note || null } });
      toast(kind === "credit" ? "Udhaar likh liya" : "Payment likh li");
      setAmount(""); setNote(""); reload(); onChange();
    } catch (e: any) { toast(e.message, true); }
  }

  return (
    <div className="section">
      <Async loading={loading} error={error} reload={reload}>
        {data ? (
          <div className="table-wrap" style={{ padding: 16 }}>
            <div className="head" style={{ marginBottom: 8 }}>
              <div>
                <h2>{data.customer.display_name}</h2>
                <p className="sub">{data.customer.phone_masked} | Last visit: {fmtDate(data.customer.last_visit)}</p>
              </div>
              <div className="serif" style={{ fontSize: 28 }}>{inr(data.customer.pending)}<div className="sub">baaki yahan</div></div>
            </div>
            {data.customer.aliases.length ? <p className="sub">Nickname: {data.customer.aliases.join(", ")}</p> : null}
            <h3 style={{ marginTop: 16 }}>Mohalla ka bharosa</h3>
            <Network n={data.network} />
            <p className="note">Privacy: {data.network.privacy}</p>
            <h3 style={{ marginTop: 24 }}>Entry likho</h3>
            <div className="form-grid">
              <Field label="Kitne rupaye"><input type="number" min={1} step="1" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
              <Field label="Note"><input maxLength={200} placeholder="Optional" value={note} onChange={(e) => setNote(e.target.value)} /></Field>
            </div>
            <div className="row">
              <button className="btn" onClick={() => send("credit")}>Udhaar diya</button>
              <button className="btn ghost" onClick={() => send("payment")}>Payment mili</button>
            </div>
          </div>
        ) : null}
      </Async>
    </div>
  );
}

function AddCustomer({ prefill, onDone }: { prefill?: string; onDone: () => void }) {
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await api("/udhaar/customers", { method: "POST", body: { name: f.get("name"), phone: f.get("phone"),
        aliases: String(f.get("aliases")).split(",").map((a) => a.trim()).filter(Boolean) } });
      toast("Customer jud gaya"); onDone();
    } catch (err: any) { toast(err.message, true); }
  }
  return (
    <form onSubmit={submit}>
      <div className="form-grid">
        <Field label="Naam (sirf label)"><input name="name" defaultValue={prefill} required /></Field>
        <Field label="Mobile number (asli pehchaan)"><input name="phone" inputMode="numeric" required /></Field>
        <Field label="Nickname (comma se alag)"><input name="aliases" placeholder="Rahul bhai, Rahul painter" /></Field>
      </div>
      <button className="btn" type="submit">Customer jodo</button>
    </form>
  );
}

function Reminders() {
  const { data, error, loading, reload } = useLoad(() => api<any[]>("/khata/drafts"));
  const [texts, setTexts] = useState<Record<number, string>>({});

  async function send(d: any) {
    try {
      await api("/khata/send", { method: "POST", body: { customer_id: d.customer_id, message: texts[d.customer_id] ?? d.message } });
      toast("Reminder bhej diya (demo: simulated)"); reload();
    } catch (e: any) { toast(e.message, true); }
  }

  return (
    <div className="section">
      <h2>Udhaar wapas lao</h2>
      <p className="sub">7 din se zyada baaki wale customers ke liye reminder taiyaar hain. Aap dekhke bhejte ho, apne aap kuch nahi jaata.</p>
      <div style={{ marginTop: 16 }}>
        <Async loading={loading} error={error} reload={reload}>
          {data && data.length ? data.map((d) => (
            <div key={d.customer_id} className="panel" style={{ padding: 16, border: "1px solid var(--line)", borderRadius: 8, background: "#fff", marginBottom: 16 }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <strong>{d.display_name}</strong>
                <span>{inr(d.pending)} baaki, {d.overdue_days} din</span>
              </div>
              <label className="field" style={{ marginTop: 8 }}>Message
                <textarea rows={4} style={{ font: "inherit", padding: 8, border: "1px solid var(--line)", borderRadius: 6 }}
                  value={texts[d.customer_id] ?? d.message} onChange={(e) => setTexts({ ...texts, [d.customer_id]: e.target.value })} />
              </label>
              <div className="row" style={{ marginTop: 8 }}><button className="btn small" onClick={() => send(d)}>Approve aur bhejo</button></div>
            </div>
          )) : <Empty title="Abhi koi reminder nahi" text="Kisi ka bhi udhaar 7 din se zyada purana nahi hai." />}
        </Async>
      </div>
    </div>
  );
}

export default function Udhaar() {
  const customers = useLoad(() => api<any[]>("/udhaar/customers"));
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<any>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  async function search(e: FormEvent) {
    e.preventDefault();
    try {
      const r = await api<any>("/udhaar/resolve?q=" + encodeURIComponent(query));
      setResult(r);
      setOpenId(r.status === "resolved" ? r.matches[0].id : null);
    } catch (err: any) { toast(err.message, true); }
  }

  return (
    <>
      <Head title="Udhaar" sub="Pehchaan mobile number se hoti hai. Naam sirf label hai." />
      <form className="form-grid" onSubmit={search}>
        <Field label="Kisko udhaar dena hai?">
          <input placeholder="Jaise: Rahul ko udhaar du?" autoComplete="off" required value={query} onChange={(e) => setQuery(e.target.value)} />
        </Field>
        <button className="btn" type="submit" style={{ alignSelf: "end" }}>Dekho</button>
      </form>

      {result?.status === "ambiguous" ? (
        <div className="section">
          <h2>{result.question}</h2>
          <div style={{ marginTop: 16 }}>
            <Table head={[{ label: "Naam" }, { label: "Number" }, { label: "Baaki", num: true }, { label: "Last visit" }, { label: "" }]}>
              {result.matches.map((m: any) => (
                <tr key={m.id}>
                  <td><strong>{m.display_name}</strong><div className="sub">{m.aliases.join(", ")}</div></td>
                  <td>{m.phone_masked}</td><td className="num">{inr(m.pending)}</td><td>{fmtDate(m.last_visit)}</td>
                  <td><button className="btn small" onClick={() => setOpenId(m.id)}>Yehi hai</button></td>
                </tr>
              ))}
            </Table>
          </div>
        </div>
      ) : null}
      {result?.status === "none" ? (
        <div className="section">
          <h2>Ye naam nahi mila</h2>
          <p className="sub">Naya customer hai? Mobile number se jodo.</p>
          <AddCustomer prefill={result.suggested_name} onDone={() => { setResult(null); customers.reload(); }} />
        </div>
      ) : null}
      {openId !== null ? <CustomerCard key={openId} id={openId} onChange={customers.reload} /> : null}

      <Reminders />

      <details className="panel section"><summary>Naya customer</summary>
        <AddCustomer onDone={customers.reload} />
      </details>

      <div className="section">
        <h2>Sab customers</h2>
        <div style={{ marginTop: 16 }}>
          <Async loading={customers.loading} error={customers.error} reload={customers.reload}>
            {customers.data && customers.data.length ? (
              <Table head={[{ label: "Naam" }, { label: "Number" }, { label: "Baaki", num: true }, { label: "Last visit" }, { label: "" }]}>
                {customers.data.map((c: any) => (
                  <tr key={c.id}>
                    <td><strong>{c.display_name}</strong><div className="sub">{c.aliases.join(", ")}</div></td>
                    <td>{c.phone_masked}</td><td className="num">{inr(c.pending)}</td><td>{fmtDate(c.last_visit)}</td>
                    <td><button className="btn small ghost" onClick={() => setOpenId(c.id)}>Dekho</button></td>
                  </tr>
                ))}
              </Table>
            ) : <Empty title="Abhi koi customer nahi" text="Upar se pehla customer jodo." />}
          </Async>
        </div>
      </div>
    </>
  );
}
