import Link from "next/link";

export default function AuthSide() {
  return (
    <aside className="auth-side">
      <Link href="/" className="auth-back">Back to home</Link>
      <div>
        <div className="auth-brand">Vistaar</div>
        <h1 className="auth-h1">
          <span>Your mohalla</span>
          <span className="it">buys better together.</span>
        </h1>
        <p className="auth-lede">Dukaan ka stock, udhaar aur mohalla, ek jagah.</p>
      </div>
      <div className="auth-dash" aria-hidden="true" />
    </aside>
  );
}