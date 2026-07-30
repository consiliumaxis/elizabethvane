export const PERMISSIONS = Object.freeze({
  statisticsView: 'statistics.view',
  statisticsManage: 'statistics.manage',
  statisticsCommand: 'statistics.command',
  dashboardView: 'dashboard.view',
  usersView: 'users.view',
  usersProfileEdit: 'users.profile_edit',
  usersArchiveClear: 'users.archive_clear',
  usersAccess: 'users.access',
  usersBalance: 'users.balance',
  usersBlock: 'users.block',
  usersDelete: 'users.delete',
  staffView: 'staff.view',
  staffAdd: 'staff.add',
  staffManage: 'staff.manage',
  broadcastManage: 'broadcast.manage',
  settingsStreams: 'settings.streams',
  settingsAi: 'settings.ai',
  settingsSystemAccess: 'settings.system_access',
  settingsFunnel: 'settings.funnel',
  settingsApi: 'settings.api',
  settingsInterface: 'settings.interface',
  strategiesManage: 'strategies.manage',
  aiChatterManage: 'aichatter.manage',
});

export const SETTINGS_PERMISSIONS = Object.freeze([
  PERMISSIONS.settingsStreams,
  PERMISSIONS.settingsAi,
  PERMISSIONS.settingsSystemAccess,
  PERMISSIONS.settingsFunnel,
  PERMISSIONS.settingsApi,
  PERMISSIONS.settingsInterface,
]);

export const hasPermission = (adminUser, permission) => (
  Boolean(adminUser?.is_protected)
  || Boolean(adminUser?.permissions?.[permission])
);

export const hasAnyPermission = (adminUser, permissions) => (
  permissions.some((permission) => hasPermission(adminUser, permission))
);
