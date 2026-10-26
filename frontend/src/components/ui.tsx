"use client";
import { ReactNode } from "react";

export function Badge({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={"badge " + kind}>{children}</span>;
}

export function Empty({ title, text }: { title: string; text?: string | null }) {
  return (
    <div className="state">
      <h2>{title}</h2>
      {text ? <p>{text}</p> : null}
    </div>
  );
}

export function Loading() {
  return <div className="state"><span className="spin" aria-label="Loading" /></div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="state error">
      <h2>{message}</h2>
      <button className="btn ghost" onClick={onRetry}>Dobara try karo</button>
    </div>
  );
}

export function Head({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="head">
      <div>
        <h1>{title}</h1>
        {sub ? <p className="sub">{sub}</p> : null}
      </div>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="field">{label}{children}</label>;
}

export function Table({ head, children }: { head: { label: string; num?: boolean }[]; children: ReactNode }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{head.map((h) => <th key={h.label} className={h.num ? "num" : ""}>{h.label}</th>)}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

/** Wraps a page body with loading / error states. */
export function Async({ loading, error, reload, children }: {
  loading: boolean; error: string | null; reload: () => void; children: ReactNode;
}) {
  if (loading) return <Loading />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  return <>{children}</>;
}
