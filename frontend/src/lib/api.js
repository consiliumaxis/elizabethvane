export const getTelegramWebApp = () => window.Telegram?.WebApp || null;

export const getTelegramInitData = () => {
  const tg = getTelegramWebApp();
  return (tg?.initData || '').trim();
};

export const isTelegramWebAppAvailable = () => {
  return Boolean(getTelegramWebApp() && getTelegramInitData());
};

export const getTelegramUnsafeUser = () => {
  const tg = getTelegramWebApp();
  return tg?.initDataUnsafe?.user || null;
};

export const getAdminTokenFromPath = () => {
  const pathname = (window.location.pathname || '').replace(/\/+$/, '');
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length >= 2 && parts[0].toLowerCase() === 'admin') {
    return decodeURIComponent(parts[1] || '');
  }
  if (parts.length === 1 && /^[A-Za-z0-9._~-]{24,}$/.test(parts[0])) {
    return decodeURIComponent(parts[0]);
  }
  return '';
};

export const isAdminRoute = () => Boolean(getAdminTokenFromPath());

export async function apiFetch(url, options = {}) {
  const initData = getTelegramInitData();
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (initData) {
    headers.set('X-TG-Init-Data', initData);
  }
  const response = await fetch(url, {
    ...options,
    headers,
  });
  return response;
}

export async function apiFetchJson(url, options = {}) {
  const response = await apiFetch(url, options);
  const raw = await response.text();
  let data = null;
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      data = null;
    }
  }
  if (!response.ok) {
    const message = data?.detail || data?.error || raw || 'Request failed';
    throw new Error(message);
  }
  if (!data) {
    throw new Error(raw || 'Server returned invalid JSON');
  }
  return data;
}

export async function apiAdminFetch(url, options = {}) {
  const adminToken = getAdminTokenFromPath();
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (adminToken) {
    headers.set('X-Admin-Token', adminToken);
  }
  return apiFetch(url, { ...options, headers });
}

export async function apiAdminFetchJson(url, options = {}) {
  const response = await apiAdminFetch(url, options);
  const raw = await response.text();
  let data = null;
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      data = null;
    }
  }
  if (!response.ok) {
    const message = data?.detail || data?.error || raw || 'Request failed';
    throw new Error(message);
  }
  if (!data) {
    throw new Error(raw || 'Server returned invalid JSON');
  }
  return data;
}
