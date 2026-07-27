import { useCallback, useMemo, useState } from 'react';
import { AdminLocaleContext } from './adminLocaleContext';

const STORAGE_KEY = 'elizabeth_admin_language';
const SUPPORTED_LANGUAGES = new Set(['en', 'ru']);

const getInitialLanguage = () => {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return SUPPORTED_LANGUAGES.has(stored) ? stored : 'en';
  } catch {
    return 'en';
  }
};

export function AdminLocaleProvider({ children }) {
  const [language, setLanguageState] = useState(getInitialLanguage);

  const setLanguage = useCallback((nextLanguage) => {
    const normalized = SUPPORTED_LANGUAGES.has(nextLanguage) ? nextLanguage : 'en';
    setLanguageState(normalized);
    try {
      window.localStorage.setItem(STORAGE_KEY, normalized);
    } catch {
      // The interface still works if storage is blocked by the browser.
    }
  }, []);

  const value = useMemo(
    () => ({
      language,
      locale: language === 'ru' ? 'ru-RU' : 'en-US',
      setLanguage,
      tr: (english, russian) => (language === 'ru' ? russian : english),
    }),
    [language, setLanguage]
  );

  return (
    <AdminLocaleContext.Provider value={value}>
      {children}
    </AdminLocaleContext.Provider>
  );
}
