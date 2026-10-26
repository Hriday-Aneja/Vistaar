const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000") + "/api";
const KEY = "vistaar_token";

export const session = {
  get token(): string | null {
    return typeof window === "undefined" ? null : localStorage.getItem(KEY);
  },
  set(token: string) { localStorage.setItem(KEY, token); },
  clear() { localStorage.removeItem(KEY); },
};

function errorText(data: any): string {
  if (!data) return "Kuch gadbad hui, dobara try karo";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d: any) => String(d.msg).replace(/^Value error, /, "")).join(". ");
  return "Kuch gadbad hui, dobara try karo";
}

export async function api<T = any>(
  path: string,
  opts: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const headers: Record<string, string> = {};
  if (body) headers["Content-Type"] = "application/json";
  if (auth && session.token) headers.Authorization = "Bearer " + session.token;
  const res = await fetch(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let data: any = null;
  try { data = await res.json(); } catch { data = null; }
  if (res.status === 401 && auth) {
    session.clear();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error(errorText(data));
  }
  if (!res.ok) throw new Error(errorText(data));
  return data as T;
}

export async function openPdf(path: string) {
  const res = await fetch(BASE + path, { headers: { Authorization: "Bearer " + (session.token ?? "") } });
  if (!res.ok) throw new Error("PDF nahi ban paya");
  window.open(URL.createObjectURL(await res.blob()), "_blank");
}

export const inr = (n: number) => "Rs " + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
export const fmtDate = (iso?: string | null) =>
  iso ? new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "-";
