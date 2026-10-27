"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { session } from "@/lib/api";

const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000") + "/api";

export default function LandingNav() {
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    const token = session.token;
    if (!token) return;
    fetch(BASE + "/auth/me", { headers: { Authorization: "Bearer " + token } })
      .then((res) => {
        if (res.ok) setSignedIn(true);
        else if (res.status === 401) session.clear();
      })
      .catch(() => {});
  }, []);

  return (
    <nav className="lp-nav">
      {signedIn ? (
        <Link href="/bulk" className="lp-btn lp-btn-sm">Open your dashboard</Link>
      ) : (
        <>
          <Link href="/login" className="lp-navlink">Log in</Link>
          <Link href="/register" className="lp-btn lp-btn-sm">Add your shop</Link>
        </>
      )}
    </nav>
  );
}