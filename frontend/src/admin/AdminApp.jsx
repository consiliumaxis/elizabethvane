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
import {
  PERMISSIONS,
  SETTINGS_PERMISSIONS,
  hasAnyPermission,
  hasPermission,
} from './permissions';
import './admin.css';

function AdminAppContent({ adminUser, authError }) {
  const { language, tr } = useAdminLocale();
  const [activeTab, setActiveTab] = useState('statistics');
  const [studioMode, setStudioMode] = useState(false);

  const tabs = useMemo(() => [
    { id: 'statistics', label: tr('Statistics', 'Статистика'), visible: hasPermission(adminUser, PERMISSIONS.statisticsView) },
    { id: 'dashboard', label: tr('Dashboard', 'Дашборд'), visible: hasPermission(adminUser, PERMISSIONS.dashboardView) },
    { id: 'users', label: tr('Users', 'Пользователи'), visible: hasPermission(adminUser, PERMISSIONS.usersView) },
    { id: 'managers', label: tr('Managers', 'Менеджеры'), visible: hasPermission(adminUser, PERMISSIONS.staffView) },
    { id: 'broadcast', label: tr('Broadcast', 'Рассылка'), visible: hasPermission(adminUser, PERMISSIONS.broadcastManage) },
    { id: 'settings', label: tr('Settings', 'Настройки'), visible: hasAnyPermission(adminUser, SETTINGS_PERMISSIONS) },
    { id: 'strategies', label: tr('Strategies', 'Стратегии'), visible: hasPermission(adminUser, PERMISSIONS.strategiesManage) },
    { id: 'aichatter', label: 'AI CHATTER', visible: hasPermission(adminUser, PERMISSIONS.aiChatterManage) },
  ].filter((tab) => tab.visible), [adminUser, tr]);
  const effectiveActiveTab = tabs.some((tab) => tab.id === activeTab)
    ? activeTab
    : tabs[0]?.id;

  const title = useMemo(() => {
    const tab = tabs.find((item) => item.id === effectiveActiveTab);
    return tab ? tab.label : tr('Admin Center', 'Админ-центр');
  }, [effectiveActiveTab, tabs, tr]);

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
            {adminUser?.display_name || adminUser?.first_name || adminUser?.username || tr('Admin', 'Админ')} | ID {adminUser?.user_id || '-'}
          </div>
        </div>
      </header>

      <nav className="admin-tabs admin-card">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`admin-tab-btn ${effectiveActiveTab === tab.id ? 'active' : ''}`}
            onClick={() => selectTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="admin-page">
        {effectiveActiveTab === 'statistics' && (
          <StudioStatisticsPage
            studioMode={studioMode}
            onStudioModeChange={setStudioMode}
            canManageDays={hasPermission(adminUser, PERMISSIONS.statisticsManage)}
          />
        )}
        {effectiveActiveTab === 'dashboard' && <StatsPage />}
        {effectiveActiveTab === 'users' && <UsersPage adminUser={adminUser} />}
        {effectiveActiveTab === 'managers' && <ManagersPage adminUser={adminUser} />}
        {effectiveActiveTab === 'broadcast' && <BroadcastPage />}
        {effectiveActiveTab === 'settings' && <SettingsPage adminUser={adminUser} />}
        {effectiveActiveTab === 'strategies' && <StrategiesPage />}
        {effectiveActiveTab === 'aichatter' && <AIChatterPage />}
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
