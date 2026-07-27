import { useContext } from 'react';
import { AdminLocaleContext } from './adminLocaleContext';

export function useAdminLocale() {
  const context = useContext(AdminLocaleContext);
  if (!context) {
    throw new Error('useAdminLocale must be used inside AdminLocaleProvider');
  }
  return context;
}
