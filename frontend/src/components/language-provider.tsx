"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { normalizeLocale, translate, type Locale } from "@/lib/i18n";

type LanguageContextValue = {
  locale: Locale;
  toggleLocale: () => void;
  t: (message: string, values?: Record<string, string | number>) => string;
};
const LanguageContext = createContext<LanguageContextValue | null>(null);
const storageKey = "t2i-language";

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocale] = useState<Locale>("zh-CN");
  useEffect(() => {
    try {
      setLocale(normalizeLocale(localStorage.getItem(storageKey)));
    } catch {
      /* Use Chinese when storage is unavailable. */
    }
    const onStorage = (event: StorageEvent) => {
      if (event.key === storageKey || event.key === null)
        setLocale(normalizeLocale(event.newValue));
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  const toggleLocale = useCallback(() => {
    const next = locale === "zh-CN" ? "en-US" : "zh-CN";
    setLocale(next);
    try {
      localStorage.setItem(storageKey, next);
    } catch {
      /* Switching still works in this session. */
    }
  }, [locale]);
  const t = useCallback(
    (message: string, values?: Record<string, string | number>) =>
      translate(locale, message, values),
    [locale],
  );
  const value = useMemo(
    () => ({ locale, toggleLocale, t }),
    [locale, toggleLocale, t],
  );
  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useI18n() {
  const value = useContext(LanguageContext);
  if (!value) throw new Error("useI18n must be used inside LanguageProvider");
  return value;
}
