import { useMemo, useState } from 'react';
import StatsPage from './pages/StatsPage';
import UsersPage from './pages/UsersPage';
import BroadcastPage from './pages/BroadcastPage';
import SettingsPage from './pages/SettingsPage';
import StrategiesPage from './pages/StrategiesPage';
import './admin.css';

const TABS = [
  { id: 'stats', label: 'Статистика' },
  { id: 'users', label: 'Пользователи' },
  { id: 'broadcast', label: 'Рассылка' },
  { id: 'settings', label: 'Настройки' },
  { id: 'strategies', label: 'Стратегии' },
];

export default function AdminApp({ adminUser, authError }) {
  const [activeTab, setActiveTab] = useState('stats');

  const title = useMemo(() => {
    const tab = TABS.find((item) => item.id === activeTab);
    return tab ? tab.label : 'Админ-панель';
  }, [activeTab]);

  if (authError) {
    return (
      <div className="admin-shell">
        <div className="admin-card">
          <h2 className="admin-title">Доступ запрещен</h2>
          <p className="admin-muted">{authError}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-shell">
      <header className="admin-topbar admin-card">
        <div>
          <div className="admin-badge">Админ-центр</div>
          <h1 className="admin-title">{title}</h1>
          <div className="admin-muted">
            {adminUser?.first_name || adminUser?.username || 'Админ'} | ID {adminUser?.user_id || '-'}
          </div>
        </div>
      </header>

      <nav className="admin-tabs admin-card">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`admin-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="admin-page">
        {activeTab === 'stats' && <StatsPage />}
        {activeTab === 'users' && <UsersPage />}
        {activeTab === 'broadcast' && <BroadcastPage />}
        {activeTab === 'settings' && <SettingsPage adminUser={adminUser} />}
        {activeTab === 'strategies' && <StrategiesPage />}
      </main>
    </div>
  );
}
