"use client";

import { useState, useEffect } from "react";

interface PersistedData<T> {
  result: T;
  fetchedAt: string; // ISO string
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}/${(d.getMonth() + 1).toString().padStart(2, "0")}/${d.getDate().toString().padStart(2, "0")} ${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
}

/**
 * APIレスポンスをlocalStorageに永続化するフック。
 * タブ切替・リロードでも前回の結果を保持する。
 * seedUrlが指定されていてlocalStorageに既存データがない場合、JSONを自動ロードする。
 */
export function usePersistedResult<T>(storageKey: string, seedUrl?: string) {
  const [result, setResult] = useState<T | null>(null);
  const [fetchedAt, setFetchedAt] = useState<string | null>(null);

  useEffect(() => {
    // localStorageから復元
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const parsed: PersistedData<T> = JSON.parse(raw);
        setResult(parsed.result);
        setFetchedAt(parsed.fetchedAt);
        return;
      }
    } catch {
      // parse失敗は無視
    }

    // localStorageになければseedURLからロード
    if (seedUrl) {
      fetch(seedUrl)
        .then((r) => r.ok ? r.json() : null)
        .then((data: PersistedData<T> | null) => {
          if (data?.result) {
            setResult(data.result);
            setFetchedAt(data.fetchedAt);
            try {
              localStorage.setItem(storageKey, JSON.stringify(data));
            } catch { /* ignore */ }
          }
        })
        .catch(() => { /* seed not found, ignore */ });
    }
  }, [storageKey, seedUrl]);

  const saveResult = (data: T) => {
    const now = new Date().toISOString();
    setResult(data);
    setFetchedAt(now);
    try {
      localStorage.setItem(storageKey, JSON.stringify({ result: data, fetchedAt: now }));
    } catch {
      // storage full等は無視
    }
  };

  return { result, fetchedAt: fetchedAt ? formatDate(fetchedAt) : null, saveResult };
}
