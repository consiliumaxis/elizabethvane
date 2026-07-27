import { useEffect, useMemo, useState } from 'react';
import StatsPage from './pages/StatsPage';
import StudioStatisticsPage from './pages/StudioStatisticsPage';
import UsersPage from './pages/UsersPage';
import BroadcastPage from './pages/BroadcastPage';
import SettingsPage from './pages/SettingsPage';
import StrategiesPage from './pages/StrategiesPage';
import AIChatterPage from './pages/AIChatterPage';
import ManagersPage from './pages/ManagersPage';
import { AdminLocaleProvider } from './i18n';
import { useAdminLocale } from './useAdminLocale';
import './admin.css';

function AdminAppContent({ adminUser, authError }) {
  const { language, tr } = useAdminLocale();
  const [activeTab, setActiveTab] = useState('statistics');
  const [studioMode, setStudioMode] = useState(false);

  const tabs = useMemo(() => [
    { id: 'statistics', label: tr('Statistics', 'Статистика') },
    { id: 'dashboard', label: tr('Dashboard', 'Дашборд') },
    { id: 'users', label: tr('Users', 'Пользователи') },
    { id: 'managers', label: tr('Managers', 'Менеджеры') },
    { id: 'broadcast', label: tr('Broadcast', 'Рассылка') },
    { id: 'settings', label: tr('Settings', 'Настройки') },
    { id: 'strategies', label: tr('Strategies', 'Стратегии') },
    { id: 'aichatter', label: 'AI CHATTER' },
  ], [tr]);

  const title = useMemo(() => {
    const tab = tabs.find((item) => item.id === activeTab);
    return tab ? tab.label : tr('Admin Center', 'Админ-центр');
  }, [activeTab, tabs, tr]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && studioMode) {
        setStudioMode(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [studioMode]);

  const selectTab = (tabId) => {
    setStudioMode(false);
    setActiveTab(tabId);
  };

  if (authError) {
    return (
      <div className="admin-shell">
        <div className="admin-card">
          <h2 className="admin-title">{tr('Access denied', 'Доступ запрещен')}</h2>
          <p className="admin-muted">{authError}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`admin-shell ${studioMode ? 'studio-mode' : ''}`} data-language={language}>
      <header className="admin-topbar admin-card">
        <div>
          <div className="admin-badge">{tr('Admin Center', 'Админ-центр')}</div>
          <h1 className="admin-title">{title}</h1>
          <div className="admin-muted">
            {adminUser?.first_name || adminUser?.username || tr('Admin', 'Админ')} | ID {adminUser?.user_id || '-'}
          </div>
        </div>
      </header>

      <nav className="admin-tabs admin-card">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`admin-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => selectTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="admin-page">
        {activeTab === 'statistics' && (
          <StudioStatisticsPage
            studioMode={studioMode}
            onStudioModeChange={setStudioMode}
          />
        )}
        {activeTab === 'dashboard' && <StatsPage />}
        {activeTab === 'users' && <UsersPage />}
        {activeTab === 'managers' && <ManagersPage adminUser={adminUser} />}
        {activeTab === 'broadcast' && <BroadcastPage />}
        {activeTab === 'settings' && <SettingsPage />}
        {activeTab === 'strategies' && <StrategiesPage />}
        {activeTab === 'aichatter' && <AIChatterPage />}
      </main>
    </div>
  );
}

export default function AdminApp(props) {
  return (
    <AdminLocaleProvider>
      <AdminAppContent {...props} />
    </AdminLocaleProvider>
  );
}
