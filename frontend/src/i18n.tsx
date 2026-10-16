import React, {createContext, useContext, useEffect, useMemo, useState} from 'react';
import english from './locales/en-US.json';
import traditional from './locales/zh-TW.json';

export const languages = [
  {id: 'zh-CN', name: '简体中文', font: '思源黑体 SC'},
  {id: 'zh-TW', name: '繁體中文', font: '思源黑體 TC'},
  {id: 'en-US', name: 'English', font: 'Google Sans'}
] as const;
export type Locale = typeof languages[number]['id'];
export function isLocale(value: unknown): value is Locale {
  return languages.some(language => language.id === value);
}
const catalogues: Record<string, Record<string, string>> = {'en-US': english, 'zh-TW': traditional};
const reverse = new Map([...Object.entries(english), ...Object.entries(traditional)].map(([key, value]) => [value, key]));
const patterns = Object.keys(english).filter(key => key.includes('{0}')).map(key => {
  const escaped = key.split(/\{\d+\}/).map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return {key, regex: new RegExp('^' + escaped.join('(.*?)') + '$')};
});

/** Only UI messages enter this translator; photo names, paths and identities stay verbatim. */
export function translate(locale: Locale, text: string, args?: unknown[]): string {
  const source = reverse.get(text) || text;
  const table = catalogues[locale];
  const format = (key: string, values: unknown[] = []) => (table?.[key] || key)
    .replace(/\{(\d+)\}/g, (_, index) => String(values[Number(index)] ?? ''));
  if (args) return format(source, args);
  if (source in english) return format(source);
  for (const {key, regex} of patterns) {
    const match = regex.exec(source);
    if (match) return format(key, match.slice(1).map(value => table?.[value] || value));
  }
  return text; // Keep unknown model/runtime diagnostics intact.
}

type I18n = {locale: Locale; setLocale: (locale: Locale) => void; t: (text: string, args?: unknown[]) => string};
const Context = createContext<I18n | null>(null);
export function LanguageProvider({children}: {children: React.ReactNode}) {
  const [locale, setLocale] = useState<Locale>(() => {
    const saved = localStorage.getItem('sf-language');
    return isLocale(saved) ? saved : 'zh-CN';
  });
  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = locale === 'en-US' ? 'Memivo · Photo workspace' : locale === 'zh-TW' ? 'Memivo · 影像工作臺' : 'Memivo · 影像工作台';
    localStorage.setItem('sf-language', locale);
  }, [locale]);
  const value = useMemo(() => ({locale, setLocale, t: (text: string, args?: unknown[]) => translate(locale, text, args)}), [locale]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useI18n() {
  const value = useContext(Context);
  if (!value) throw new Error('LanguageProvider is required');
  return value;
}
