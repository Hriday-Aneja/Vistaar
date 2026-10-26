"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { session } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  useEffect(() => { router.replace(session.token ? "/bulk" : "/login"); }, [router]);
  return null;
}
