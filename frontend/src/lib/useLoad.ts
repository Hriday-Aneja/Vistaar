"use client";
import { useCallback, useEffect, useState } from "react";

/** Load data once, expose loading/error and a reload(). */
export function useLoad<T>(fn: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    setLoading(true);
    fn().then((d) => { setData(d); setError(null); })
      .catch((e) => setError(e.message || "Kuch gadbad hui. Dobara try karo."))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(reload, [reload]);
  return { data, error, loading, reload };
}
