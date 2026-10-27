"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { session } from "@/lib/api";

export default function LandingRedirect() {
  const router = useRouter();
  useEffect(() => {
    if (session.token) router.replace("/bulk");
  }, [router]);
  return null;
}