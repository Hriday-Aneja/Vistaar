"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { api, session } from "@/lib/api";
import { Loading } from "./ui";

const NAV = [
  { href: "/chat", label: "Chat" },
  { href: "/bulk", label: "Bulk-buy" },
  { href: "/stock", label: "Stock" },
  { href: "/swaps", label: "Swap" },
  { href: "/udhaar", label: "Udhaar" },
  { href: "/pulse", label: "Pulse" },
  { href: "/prices", label: "Daam" },
  { href: "/map", label: "Mohalla" },
  { href: "/distributors", label: "Distributor" },
  { href: "/impact", label: "Impact" },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [shop, setShop] = useState<string | null>(null);

  useEffect(() => {
    if (!session.token) { router.replace("/login"); return; }
    api("/auth/me").then((u) => setShop(u.shop.name)).catch(() => router.replace("/login"));
  }, [router]);

  async function logout() {
    try { await api("/auth/logout", { method: "POST" }); } catch { /* token already gone */ }
    session.clear();
    router.replace("/login");
  }

  if (!shop) return <main className="wrap"><Loading /></main>;
  return (
    <>
      <header className="topbar">
        <div className="wrap">
          <Link href="/" className="brand">Vistaar</Link>
          <span className="shopname">{shop}</span>
          <button className="btn ghost small" onClick={logout}>Logout</button>
        </div>
        <div className="wrap">
          <nav aria-label="Main">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className={path === n.href ? "active" : ""}>{n.label}</Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="wrap">{children}</main>
    </>
  );
}