import Link from "next/link";
import LandingNav from "@/components/LandingNav";
import "./landing.css";

const SEP = "\u00a0\u00a0/\u00a0\u00a0";
const PHRASES = [
  "Diwali ka maal plan karo",
  "Kaunsa maal expire hoga?",
  "Rahul bhai ko udhaar du?",
  "Bikri kaisi chal rahi hai?",
];

const HERO_LINES = [
  { words: ["Your", "mohalla", "buys"], start: 0.1, italic: false },
  { words: ["better", "together."], start: 0.45, italic: true },
];

const FACTS = [
  { title: "You stay in control", text: "Every action that moves money or stock needs your approval." },
  { title: "Speaks Hinglish", text: "Ask about plans, udhaar, swaps and sales the way you talk." },
  { title: "Private by design", text: "Cross-shop numbers show only when 5 or more shops contribute." },
];

const ROWS = [
  {
    title: "Buy together",
    body: "Vistaar forecasts what your shop needs, pools it with shops within 3 km, and runs a distributor auction. Every quantity comes with a plain reason, and you approve before anything is ordered.",
    note: "A pooled number only shows when at least 5 shops contribute.",
  },
  {
    title: "Swap surplus",
    body: "Stock that will not sell before it expires goes to a nearby shop running short. You see why: distance, expiry pressure, demand and margin.",
    note: "The shop receiving the stock approves the swap.",
  },
  {
    title: "Lend safely",
    body: "Get a risk view built from nearby shops without seeing their private books. With too little data, it says so instead of guessing.",
    note: "Reminders with a UPI link go out only after you approve.",
  },
];

const STEPS = [
  { title: "Forecast", text: "Average daily sales and a festival factor, minus stock" },
  { title: "Pool", text: "Nearby shops join, 5 or more needed" },
  { title: "Auction", text: "Distributors bid under price rules set by code" },
  { title: "Approve", text: "You review each quantity and its reason" },
  { title: "Purchase order", text: "A PDF you send to the distributor" },
];

const SAY = [
  { who: "You", text: "Kaunsa maal expire hoga?", delay: 0 },
  { who: "Vistaar", text: "Marie Gold Biscuits. Gupta Kirana me inki bikri zyada hai. Swap bhej du?", delay: 3 },
  { who: "You", text: "Diwali ka maal plan karo", delay: 7 },
  { who: "Vistaar", text: "12 cheezein, 6 dukaan ka pool. Approve karoge to PO ban jayega.", delay: 10 },
];

function Arrow() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 9h12M10 4l5 5-5 5" />
    </svg>
  );
}

export default function Landing() {
  const belt = PHRASES.join(SEP) + SEP;
  return (
    <div className="lp">
      <div className="lp-progress" aria-hidden="true" />

      <header className="lp-header">
        <div className="lp-wrap lp-header-in">
          <span className="lp-brand">Vistaar</span>
          <LandingNav />
        </div>
      </header>

      <section className="lp-hero">
        <h1 className="lp-h1">
          {HERO_LINES.map((line) => (
            <span key={line.words[0]} className={line.italic ? "lp-line lp-it" : "lp-line"}>
              {line.words.map((w, i) => (
                <span key={w}>
                  <span className="lp-wd">
                    <span className="lp-wi" style={{ animationDelay: `${(line.start + i * 0.1).toFixed(2)}s` }}>{w}</span>
                  </span>
                  {i < line.words.length - 1 ? " " : ""}
                </span>
              ))}
            </span>
          ))}
        </h1>
        <div className="lp-uline" aria-hidden="true" />
        <p className="lp-lead lp-fade" style={{ animationDelay: "0.6s" }}>
          Vistaar is a business teammate for kirana owners. It pools nearby shops for better prices, moves stock that will not sell, and shows who is safe to give udhaar.
        </p>
        <div className="lp-ask lp-fade" style={{ animationDelay: "0.8s" }}>
          <span className="lp-serif">Ask Vistaar:</span>
          <span className="lp-rot lp-serif">
            {PHRASES.map((t, i) => (
              <span key={t} style={{ animationDelay: `${i * 4}s` }}>{t}</span>
            ))}
          </span>
        </div>
        <div className="lp-cta-row lp-fade" style={{ animationDelay: "1s" }}>
          <Link href="/register" className="lp-btn lp-pulse">Add your shop<Arrow /></Link>
          <Link href="/login" className="lp-btn lp-btn-ghost">Log in</Link>
        </div>
        <div className="lp-facts">
          {FACTS.map((f, i) => (
            <div key={f.title} className="lp-fact lp-fade" style={{ animationDelay: `${1.2 + i * 0.15}s` }}>
              <div className="lp-fact-title lp-serif">{f.title}</div>
              <p>{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="lp-dashes" aria-hidden="true">
        <div className="lp-dash" />
        <div className="lp-dash lp-gold" />
        <div className="lp-dash lp-still" />
      </div>

      <div className="lp-band" aria-label="Examples of what you can ask Vistaar">
        <div className="lp-belt">
          {[0, 1, 2, 3].map((n) => (
            <span key={n} className="lp-serif">{belt}</span>
          ))}
        </div>
      </div>
      <div className="lp-dash lp-gold lp-rev" aria-hidden="true" />

      <section className="lp-wrap lp-loop">
        <h2 className="lp-h2">One loop that keeps a small shop healthy.</h2>
        {ROWS.map((r) => (
          <div key={r.title} className="lp-row">
            <div className="lp-sweep" />
            <h3 className="lp-h3">{r.title}</h3>
            <div>
              <p className="lp-body">{r.body}</p>
              <p className="lp-small">{r.note}</p>
            </div>
          </div>
        ))}
        <div className="lp-rule" />
      </section>

      <section className="lp-process">
        <div className="lp-wrap">
          <h2 className="lp-h2">From plan to purchase order</h2>
          <p className="lp-sub">Nothing is ordered before the fourth step, and that step is yours.</p>
          <div className="lp-rail" aria-hidden="true"><div className="lp-pfill" /></div>
          <div className="lp-steps">
            {STEPS.map((s, i) => (
              <div key={s.title}>
                <div className={`lp-tk lp-t${i + 1}`} />
                <div className="lp-step-title lp-serif">{s.title}</div>
                <p>{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-wrap lp-chat">
        <h2 className="lp-h2 lp-narrow">Ask in Hinglish. Approve when you are ready.</h2>
        <p className="lp-sub">Today the chat understands plans, udhaar, swaps and sales. Ask anything else and it tells you what it can do.</p>
        <div className="lp-say-list">
          {SAY.map((s) => (
            <div key={s.text} className="lp-say">
              <span className={s.who === "Vistaar" ? "lp-who lp-me" : "lp-who"}>{s.who}</span>
              <span className="lp-t lp-serif" style={{ animationDelay: `${s.delay}s` }}>{s.text}</span>
            </div>
          ))}
          <div className="lp-say-note">Sample conversation from the demo data.</div>
        </div>
      </section>

      <section className="lp-wrap lp-sim">
        <div className="lp-sim-box">
          <h2 className="lp-serif">What is simulated in this version</h2>
          <p>
            Purchase orders are PDFs and are not sent to distributors yet. WhatsApp reminders are simulated. Savings are labelled &quot;projected (simulation)&quot;. The forecast is rule-based, not machine learning.
          </p>
        </div>
      </section>

      <section className="lp-cta">
        <div className="lp-dash lp-gold lp-edge-top" aria-hidden="true" />
        <div className="lp-wrap lp-cta-in">
          <h2 className="lp-h2 lp-cta-h">Bring your shop into the mohalla.</h2>
          <Link href="/register" className="lp-btn lp-btn-gold">Add your shop<Arrow /></Link>
        </div>
        <div className="lp-dash lp-gold lp-edge-bottom lp-rev" aria-hidden="true" />
      </section>

      <footer className="lp-footer">
        <div className="lp-wrap lp-footer-in">
          <span>Vistaar, built for the Paytm AI Hackathon, Track 1.</span>
          <span>
            <Link href="/login" className="lp-link">Log in</Link>
            <Link href="/register" className="lp-link">Register</Link>
          </span>
        </div>
      </footer>
    </div>
  );
}