import { useCallback, useEffect, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';
import { useAdminLocale } from '../useAdminLocale';
import { PERMISSIONS, hasPermission } from '../permissions';


const AUDIT_PAGE_SIZE = 15;

const formatAuditDate = (value, locale, emptyLabel) => {
  if (!value) return emptyLabel;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const initials = (item) => {
  const source = String(item.display_name || item.first_name || item.username || item.user_id || '?').trim();
  return source.slice(0, 2).toUpperCase();
};

const emptyPermissions = () => Object.fromEntries(
  Object.values(PERMISSIONS).map((permission) => [permission, false])
);

const PERMISSION_PARENTS = {
  [PERMISSIONS.statisticsManage]: PERMISSIONS.statisticsView,
  [PERMISSIONS.usersProfileEdit]: PERMISSIONS.usersView,
  [PERMISSIONS.usersArchiveClear]: PERMISSIONS.usersView,
  [PERMISSIONS.usersAccess]: PERMISSIONS.usersView,
  [PERMISSIONS.usersBalance]: PERMISSIONS.usersView,
  [PERMISSIONS.usersBlock]: PERMISSIONS.usersView,
  [PERMISSIONS.usersDelete]: PERMISSIONS.usersView,
  [PERMISSIONS.staffAdd]: PERMISSIONS.staffView,
  [PERMISSIONS.staffManage]: PERMISSIONS.staffView,
};

const setPermissionValue = (permissions, permission, enabled) => {
  const next = { ...emptyPermissions(), ...(permissions || {}), [permission]: enabled };
  if (enabled && PERMISSION_PARENTS[permission]) {
    next[PERMISSION_PARENTS[permission]] = true;
  }
  if (!enabled) {
    Object.entries(PERMISSION_PARENTS).forEach(([child, parent]) => {
      if (parent === permission) next[child] = false;
    });
  }
  return next;
};

const permissionGroups = (tr) => [
  {
    id: 'statistics',
    title: tr('Statistics', 'Статистика'),
    description: tr('Studio viewing and daily presentation data.', 'Режим студии и данные для презентационной статистики.'),
    items: [
      [PERMISSIONS.statisticsView, tr('Open Statistics and Studio mode', 'Открывать статистику и режим студии')],
      [PERMISSIONS.statisticsManage, tr('Add, edit and delete days', 'Добавлять, изменять и удалять дни')],
      [PERMISSIONS.statisticsCommand, tr('Use /stats and /link in the bot', 'Использовать /stats и /link в боте')],
    ],
  },
  {
    id: 'dashboard',
    title: tr('Dashboard', 'Дашборд'),
    items: [[PERMISSIONS.dashboardView, tr('Open the live dashboard', 'Открывать рабочий дашборд')]],
  },
  {
    id: 'users',
    title: tr('Users', 'Пользователи'),
    description: tr('Viewing is the parent permission for all user actions.', 'Просмотр — базовое право для всех действий с пользователями.'),
    items: [
      [PERMISSIONS.usersView, tr('Open users and view cards', 'Открывать пользователей и карточки')],
      [PERMISSIONS.usersProfileEdit, tr('Allow name and Trader ID editing', 'Разрешать изменение имени и Trader ID')],
      [PERMISSIONS.usersArchiveClear, tr('Open archives and clear cache', 'Открывать архивы и очищать кэш')],
      [PERMISSIONS.usersAccess, tr('Edit trading access', 'Редактировать доступ к торговле')],
      [PERMISSIONS.usersBalance, tr('Edit balance', 'Изменять баланс')],
      [PERMISSIONS.usersBlock, tr('Block and unblock users', 'Блокировать и разблокировать')],
      [PERMISSIONS.usersDelete, tr('Delete users', 'Удалять пользователей')],
    ],
  },
  {
    id: 'staff',
    title: tr('Managers', 'Менеджеры'),
    description: tr('Protected administrators remain immutable.', 'Защищённые администраторы всегда остаются недоступны для изменений.'),
    items: [
      [PERMISSIONS.staffView, tr('Open staff and command history', 'Открывать сотрудников и историю команд')],
      [PERMISSIONS.staffAdd, tr('Add staff members', 'Добавлять сотрудников')],
      [PERMISSIONS.staffManage, tr('Manage staff access', 'Управлять доступами сотрудников')],
    ],
  },
  {
    id: 'broadcast',
    title: tr('Broadcast', 'Рассылка'),
    items: [[PERMISSIONS.broadcastManage, tr('Create and send broadcasts', 'Создавать и отправлять рассылки')]],
  },
  {
    id: 'settings',
    title: tr('Settings', 'Настройки'),
    description: tr('Each settings card is granted separately.', 'Каждая карточка настроек выдаётся отдельно.'),
    items: [
      [PERMISSIONS.settingsStreams, tr('Streams', 'Стримы')],
      [PERMISSIONS.settingsAi, tr('AI chat', 'AI чат')],
      [PERMISSIONS.settingsSystemAccess, tr('System access', 'Доступ к системе')],
      [PERMISSIONS.settingsFunnel, tr('Bot funnel', 'Воронка бота')],
      [PERMISSIONS.settingsApi, 'API'],
      [PERMISSIONS.settingsInterface, tr('Interface language', 'Язык интерфейса')],
    ],
  },
  {
    id: 'strategies',
    title: tr('Strategies', 'Стратегии'),
    items: [[PERMISSIONS.strategiesManage, tr('Open and fully manage strategies', 'Открывать и полностью управлять стратегиями')]],
  },
  {
    id: 'aichatter',
    title: 'AI CHATTER',
    items: [[PERMISSIONS.aiChatterManage, tr('Open and fully manage AI Chatter', 'Открывать и полностью управлять AI Chatter')]],
  },
];

export default function ManagersPage({ adminUser }) {
  const { locale, tr } = useAdminLocale();
  const roleOptions = [
    {
      value: 'manager',
      label: tr('Manager', 'Менеджер'),
      hint: tr('Default template: /stats and /link commands.', 'Шаблон по умолчанию: команды /stats и /link.'),
    },
    {
      value: 'admin',
      label: tr('Administrator', 'Администратор'),
      hint: tr('Default template: full access. Available only to the system administrator.', 'Шаблон по умолчанию: полный доступ. Назначает только системный администратор.'),
    },
  ];
  const auditStatusOptions = [
    { value: '', label: tr('All results', 'Все результаты') },
    { value: 'success', label: tr('Success', 'Успешно') },
    { value: 'not_found', label: tr('Client not found', 'Клиент не найден') },
    { value: 'invalid_query', label: tr('Invalid query', 'Неверный запрос') },
    { value: 'denied', label: tr('Access denied', 'Нет доступа') },
    { value: 'private_chat_required', label: tr('Not a private chat', 'Не личный чат') },
  ];
  const auditStatusMeta = {
    success: { label: tr('Success', 'Успешно'), tone: 'success' },
    not_found: { label: tr('Client not found', 'Клиент не найден'), tone: 'warning' },
    invalid_query: { label: tr('Invalid query', 'Неверный запрос'), tone: 'warning' },
    denied: { label: tr('Access denied', 'Нет доступа'), tone: 'danger' },
    private_chat_required: { label: tr('Not a private chat', 'Не личный чат'), tone: 'warning' },
  };
  const roleLabel = (role) => (
    roleOptions.find((item) => item.value === role)?.label || tr('Manager', 'Менеджер')
  );
  const [staff, setStaff] = useState([]);
  const [permissionTemplates, setPermissionTemplates] = useState({
    manager: { ...emptyPermissions(), [PERMISSIONS.statisticsCommand]: true },
    admin: Object.fromEntries(Object.values(PERMISSIONS).map((permission) => [permission, true])),
  });
  const [staffName, setStaffName] = useState('');
  const [telegramId, setTelegramId] = useState('');
  const [newRole, setNewRole] = useState('manager');
  const [newPermissions, setNewPermissions] = useState({
    ...emptyPermissions(),
    [PERMISSIONS.statisticsCommand]: true,
  });
  const [accessEditor, setAccessEditor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState('');
  const [deleteConfirmId, setDeleteConfirmId] = useState('');
  const [auditRows, setAuditRows] = useState([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditOffset, setAuditOffset] = useState(0);
  const [auditStatus, setAuditStatus] = useState('');
  const [auditSearch, setAuditSearch] = useState('');
  const [appliedAuditSearch, setAppliedAuditSearch] = useState('');
  const [auditLoading, setAuditLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const canAddStaff = hasPermission(adminUser, PERMISSIONS.staffAdd);
  const canManageStaff = hasPermission(adminUser, PERMISSIONS.staffManage);
  const isProtectedActor = Boolean(adminUser?.is_protected);
  const canGrantPermission = (permission) => hasPermission(adminUser, permission);

  const loadStaff = useCallback(async () => {
    const result = await apiAdminFetchJson('/api/admin/staff');
    setStaff(result.staff || []);
    if (result.permission_templates) {
      setPermissionTemplates(result.permission_templates);
    }
  }, []);

  const loadAudit = useCallback(async () => {
    setAuditLoading(true);
    try {
      const params = new URLSearchParams({
        limit: String(AUDIT_PAGE_SIZE),
        offset: String(auditOffset),
      });
      if (auditStatus) params.set('status', auditStatus);
      if (appliedAuditSearch) params.set('search', appliedAuditSearch);
      const result = await apiAdminFetchJson(`/api/admin/staff/audit?${params.toString()}`);
      setAuditRows(result.audit || []);
      setAuditTotal(Number(result.total || 0));
    } catch (requestError) {
      setError(requestError.message || tr('Could not load the request history', 'Не удалось загрузить историю запросов'));
    } finally {
      setAuditLoading(false);
    }
  }, [appliedAuditSearch, auditOffset, auditStatus, tr]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadStaff()
        .catch((requestError) => setError(requestError.message || tr('Could not load staff', 'Не удалось загрузить сотрудников')))
        .finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadStaff, tr]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadAudit();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadAudit]);

  const flashSuccess = (message) => {
    setSuccess(message);
    window.setTimeout(() => setSuccess(''), 3000);
  };

  const addStaff = async () => {
    const displayName = staffName.trim();
    if (!displayName) {
      setError(tr('Enter the employee name', 'Введите имя сотрудника'));
      return;
    }
    const userId = Number(telegramId);
    if (!Number.isSafeInteger(userId) || userId <= 0) {
      setError(tr('Enter a valid staff Telegram ID', 'Введите корректный Telegram ID сотрудника'));
      return;
    }
    setSavingId('new');
    setError('');
    try {
      await apiAdminFetchJson('/api/admin/staff', {
        method: 'POST',
        body: JSON.stringify({
          user_id: userId,
          display_name: displayName,
          role: newRole,
          permissions: newPermissions,
        }),
      });
      setStaffName('');
      setTelegramId('');
      flashSuccess(tr(
        `${roleLabel(newRole)} added: ${userId}`,
        `${roleLabel(newRole)} добавлен: ${userId}`
      ));
      await loadStaff();
    } catch (requestError) {
      setError(requestError.message || tr('Could not add the staff member', 'Не удалось добавить сотрудника'));
    } finally {
      setSavingId('');
    }
  };

  const applyTemplate = (role) => {
    const template = permissionTemplates[role] || emptyPermissions();
    return Object.fromEntries(
      Object.values(PERMISSIONS).map((permission) => [
        permission,
        Boolean(template[permission]) && canGrantPermission(permission),
      ])
    );
  };

  const changeNewRole = (role) => {
    setNewRole(role);
    setNewPermissions(applyTemplate(role));
  };

  const openNewAccessEditor = () => {
    setAccessEditor({
      mode: 'new',
      user_id: null,
      display_name: staffName,
      role: newRole,
      permissions: { ...newPermissions },
    });
  };

  const openStaffAccessEditor = (item) => {
    setAccessEditor({
      mode: 'existing',
      user_id: item.user_id,
      display_name: item.display_name || item.first_name || '',
      role: item.role || 'manager',
      permissions: { ...emptyPermissions(), ...(item.permissions || {}) },
    });
  };

  const updateEditorPermission = (permission, enabled) => {
    if (!canGrantPermission(permission)) return;
    setAccessEditor((current) => ({
      ...current,
      permissions: setPermissionValue(current.permissions, permission, enabled),
    }));
  };

  const updateEditorRole = (role) => {
    setAccessEditor((current) => ({
      ...current,
      role,
      permissions: applyTemplate(role),
    }));
  };

  const saveAccessEditor = async () => {
    if (!accessEditor) return;
    const displayName = String(accessEditor.display_name || '').trim();
    if (!displayName) {
      setError(tr('Enter the employee name', 'Введите имя сотрудника'));
      return;
    }
    if (accessEditor.mode === 'new') {
      setStaffName(displayName);
      setNewRole(accessEditor.role);
      setNewPermissions(accessEditor.permissions);
      setAccessEditor(null);
      return;
    }
    const item = staff.find((row) => String(row.user_id) === String(accessEditor.user_id));
    if (!item) return;
    const saved = await updateStaff(item, {
      display_name: displayName,
      role: accessEditor.role,
      permissions: accessEditor.permissions,
    });
    if (saved) setAccessEditor(null);
  };

  async function updateStaff(item, patch) {
    setSavingId(String(item.user_id));
    setError('');
    setDeleteConfirmId('');
    try {
      await apiAdminFetchJson(`/api/admin/staff/${item.user_id}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      });
      flashSuccess(tr('Staff access has been updated', 'Доступ сотрудника обновлён'));
      await loadStaff();
      return true;
    } catch (requestError) {
      setError(requestError.message || tr('Could not update access', 'Не удалось обновить доступ'));
      return false;
    } finally {
      setSavingId('');
    }
  }

  const deleteStaff = async (item) => {
    setSavingId(String(item.user_id));
    setError('');
    try {
      await apiAdminFetchJson(`/api/admin/staff/${item.user_id}`, { method: 'DELETE' });
      setDeleteConfirmId('');
      flashSuccess(tr(`Staff member ${item.user_id} has been removed`, `Сотрудник ${item.user_id} удалён`));
      await loadStaff();
    } catch (requestError) {
      setError(requestError.message || tr('Could not remove the staff member', 'Не удалось удалить сотрудника'));
    } finally {
      setSavingId('');
    }
  };

  const applyAuditSearch = (event) => {
    event.preventDefault();
    const normalized = auditSearch.trim();
    if (normalized === appliedAuditSearch && auditOffset === 0) {
      loadAudit();
      return;
    }
    setAuditOffset(0);
    setAppliedAuditSearch(normalized);
  };

  const auditPage = Math.floor(auditOffset / AUDIT_PAGE_SIZE) + 1;
  const auditPages = Math.max(1, Math.ceil(auditTotal / AUDIT_PAGE_SIZE));

  return (
    <div className="admin-managers-layout">
      <section className="admin-card admin-managers-hero">
        <div>
          <div className="admin-badge">{tr('Staff access', 'Доступ сотрудников')}</div>
          <h3 className="admin-section-title">{tr('Managers and administrators', 'Менеджеры и администраторы')}</h3>
          <p className="admin-muted">
            {tr(
              'The role applies a starting template. Actual access is configured separately for each employee.',
              'Роль задаёт стартовый шаблон. Фактические права настраиваются отдельно для каждого сотрудника.'
            )}
          </p>
        </div>
        <div className="admin-managers-command">
          <strong>{tr('Quick client lookup', 'Быстрый поиск клиента')}</strong>
          <code>/stats @nickname</code>
          <code>/stats 123456789</code>
          <code>/link chatterfy_lead_id</code>
        </div>
      </section>

      {error ? <div className="admin-error admin-floating-notice">{error}</div> : null}
      {success ? <div className="admin-success admin-floating-notice">{success}</div> : null}

      {canAddStaff ? <section className="admin-card admin-managers-add">
        <div className="admin-section-head">
          <div>
            <h3 className="admin-section-title">{tr('Add staff member', 'Добавить сотрудника')}</h3>
            <p className="admin-muted">
              {tr(
                'Enter an internal employee name, Telegram ID and configure access before adding.',
                'Укажите внутреннее имя сотрудника, Telegram ID и настройте доступ перед добавлением.'
              )}
            </p>
          </div>
        </div>
        <div className="admin-managers-add-grid">
          <label>
            <span>{tr('Employee name', 'Имя сотрудника')}</span>
            <input
              className="admin-input"
              placeholder={tr('For example, Anna', 'Например, Анна')}
              value={staffName}
              onChange={(event) => setStaffName(event.target.value.slice(0, 100))}
            />
          </label>
          <label>
            <span>Telegram ID</span>
            <input
              className="admin-input"
              inputMode="numeric"
              placeholder={tr('For example, 123456789', 'Например 123456789')}
              value={telegramId}
              onChange={(event) => setTelegramId(event.target.value.replace(/\D/g, '').slice(0, 20))}
            />
          </label>
          <label>
            <span>{tr('Role', 'Роль')}</span>
            <select
              className="admin-input"
              value={newRole}
              onChange={(event) => changeNewRole(event.target.value)}
            >
              {roleOptions.map((option) => (
                <option
                  key={option.value}
                  value={option.value}
                  disabled={option.value === 'admin' && !isProtectedActor}
                >
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button className="admin-btn-outline admin-access-configure" type="button" onClick={openNewAccessEditor}>
            {tr('Configure access', 'Настроить доступ')}
            <span>{Object.values(newPermissions).filter(Boolean).length}</span>
          </button>
          <button className="admin-btn" type="button" disabled={savingId === 'new'} onClick={addStaff}>
            {savingId === 'new' ? tr('Adding…', 'Добавление…') : tr('Add', 'Добавить')}
          </button>
        </div>
        <div className="admin-managers-role-hint">
          {roleOptions.find((option) => option.value === newRole)?.hint}
        </div>
      </section> : null}

      <section className="admin-card">
        <div className="admin-row-between admin-managers-list-head">
          <div>
            <h3 className="admin-section-title">{tr('Staff list', 'Список сотрудников')}</h3>
            <div className="admin-muted">{tr('Total', 'Всего')}: {staff.length}</div>
          </div>
          <button className="admin-btn-outline" type="button" disabled={loading} onClick={loadStaff}>
            {tr('Refresh', 'Обновить')}
          </button>
        </div>

        {loading ? <div className="admin-muted">{tr('Loading staff…', 'Загрузка сотрудников…')}</div> : null}
        {!loading && !staff.length ? (
          <div className="admin-managers-empty">{tr('No staff members have been added yet.', 'Сотрудники пока не добавлены.')}</div>
        ) : null}

        <div className="admin-managers-list">
          {staff.map((item) => {
            const isSelf = Number(item.user_id) === Number(adminUser?.user_id);
            const isSaving = savingId === String(item.user_id);
            const active = Boolean(Number(item.is_active));
            const isProtected = Boolean(item.is_protected);
            const canEditItem = (
              canManageStaff
              && !isSelf
              && !isProtected
              && (item.role !== 'admin' || isProtectedActor)
            );
            return (
              <article
                className={`admin-manager-card ${active ? '' : 'is-disabled'}`}
                key={item.user_id}
              >
                <div className="admin-manager-profile">
                  <div className="admin-manager-avatar">
                    {item.avatar_url ? <img src={item.avatar_url} alt="" /> : initials(item)}
                  </div>
                  <div>
                    <div className="admin-manager-name">
                      {item.display_name || item.first_name || (item.username ? `@${item.username}` : tr('Profile not loaded yet', 'Профиль ещё не получен'))}
                      {isSelf ? <span>{tr('You', 'Вы')}</span> : null}
                      {isProtected ? <span className="admin-protected-badge">{tr('Protected', 'Защищён')}</span> : null}
                    </div>
                    {item.username && item.first_name ? (
                      <div className="admin-muted">@{item.username}</div>
                    ) : null}
                    <div className="admin-manager-id">ID {item.user_id}</div>
                  </div>
                </div>

                <div className="admin-manager-controls">
                  <button
                    type="button"
                    className="admin-btn-outline admin-access-configure"
                    disabled={!canEditItem || isSaving}
                    onClick={() => openStaffAccessEditor(item)}
                  >
                    {isProtected
                      ? tr('System access', 'Системный доступ')
                      : tr('Configure access', 'Настроить доступ')}
                    <span>{Object.values(item.permissions || {}).filter(Boolean).length}</span>
                  </button>
                  <button
                    type="button"
                    className={`admin-manager-status ${active ? 'is-active' : ''}`}
                    disabled={!canEditItem || isSaving}
                    onClick={() => updateStaff(item, { is_active: !active })}
                  >
                    <span />
                    {active ? tr('Access enabled', 'Доступ включён') : tr('Access disabled', 'Доступ выключен')}
                  </button>
                </div>

                <div className="admin-manager-footer">
                  <span className={`admin-manager-role-badge ${item.role || 'manager'}`}>
                    {roleLabel(item.role)}
                  </span>
                  {deleteConfirmId === String(item.user_id) ? (
                    <div className="admin-manager-confirm">
                      <span>{tr('Remove access?', 'Удалить доступ?')}</span>
                      <button type="button" disabled={isSaving} onClick={() => deleteStaff(item)}>{tr('Yes', 'Да')}</button>
                      <button type="button" disabled={isSaving} onClick={() => setDeleteConfirmId('')}>{tr('No', 'Нет')}</button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="admin-mini-action danger"
                      disabled={!canEditItem || isSaving}
                      onClick={() => setDeleteConfirmId(String(item.user_id))}
                    >
                      {tr('Remove', 'Удалить')}
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="admin-card admin-managers-audit">
        <div className="admin-row-between admin-managers-list-head">
          <div>
            <h3 className="admin-section-title">{tr('Manager command history', 'История команд менеджеров')}</h3>
            <div className="admin-muted">
              {tr(
                'Who used /stats or /link, which client was matched, and the result. Total',
                'Кто использовал /stats или /link, какой клиент был найден и чем завершился запрос. Всего'
              )}: {auditTotal}
            </div>
          </div>
          <button
            className="admin-btn-outline"
            type="button"
            disabled={auditLoading}
            onClick={loadAudit}
          >
            {tr('Refresh', 'Обновить')}
          </button>
        </div>

        <form className="admin-audit-filters" onSubmit={applyAuditSearch}>
          <label>
            <span>{tr('Search', 'Поиск')}</span>
            <input
              className="admin-input"
              value={auditSearch}
              placeholder={tr('ID, username or command', 'ID, username или команда')}
              onChange={(event) => setAuditSearch(event.target.value.slice(0, 100))}
            />
          </label>
          <label>
            <span>{tr('Result', 'Результат')}</span>
            <select
              className="admin-input"
              value={auditStatus}
              onChange={(event) => {
                setAuditOffset(0);
                setAuditStatus(event.target.value);
              }}
            >
              {auditStatusOptions.map((option) => (
                <option key={option.value || 'all'} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <button className="admin-btn" type="submit" disabled={auditLoading}>{tr('Search', 'Найти')}</button>
        </form>

        {auditLoading ? <div className="admin-muted admin-audit-loading">{tr('Loading history…', 'Загрузка истории…')}</div> : null}
        {!auditLoading && !auditRows.length ? (
          <div className="admin-managers-empty">{tr('No requests match these filters.', 'По выбранным условиям запросов пока нет.')}</div>
        ) : null}

        <div className="admin-audit-list">
          {auditRows.map((item) => {
            const statusMeta = auditStatusMeta[item.result_status] || {
              label: item.result_status || tr('Unknown', 'Неизвестно'),
              tone: 'neutral',
            };
            const requesterName = item.requester_first_name
              || (item.requester_username ? `@${item.requester_username}` : tr('Profile not loaded', 'Профиль не получен'));
            const targetName = item.target_user_id
              ? (
                item.target_first_name
                || (item.target_username ? `@${item.target_username}` : `ID ${item.target_user_id}`)
              )
              : tr('Client not identified', 'Клиент не определён');
            return (
              <article className="admin-audit-card" key={item.id}>
                <div className="admin-audit-card-head">
                  <span className={`admin-audit-status ${statusMeta.tone}`}>{statusMeta.label}</span>
                  <time>{formatAuditDate(item.created_at, locale, tr('Time not specified', 'Время не указано'))}</time>
                </div>
                <div className="admin-audit-grid">
                  <div>
                    <span className="admin-audit-label">{tr('Requested by', 'Запросил')}</span>
                    <strong>{requesterName}</strong>
                    <small>
                      ID {item.requested_by}
                      {' · '}
                      {item.requester_role ? roleLabel(item.requester_role) : tr('role not assigned', 'роль не назначена')}
                    </small>
                  </div>
                  <div>
                    <span className="admin-audit-label">{tr('Matched client', 'Найденный клиент')}</span>
                    <strong>{targetName}</strong>
                    <small>{item.target_user_id ? `ID ${item.target_user_id}` : tr('No match found', 'Совпадение не найдено')}</small>
                  </div>
                </div>
                <code className="admin-audit-query">
                  {item.target_query || `/${item.command_name || 'stats'}`}
                </code>
              </article>
            );
          })}
        </div>

        {auditTotal > AUDIT_PAGE_SIZE ? (
          <div className="admin-audit-pagination">
            <button
              className="admin-btn-outline"
              type="button"
              disabled={auditLoading || auditOffset === 0}
              onClick={() => setAuditOffset(Math.max(0, auditOffset - AUDIT_PAGE_SIZE))}
            >
              {tr('← Previous', '← Назад')}
            </button>
            <span>{tr('Page', 'Страница')} {auditPage} {tr('of', 'из')} {auditPages}</span>
            <button
              className="admin-btn-outline"
              type="button"
              disabled={auditLoading || auditOffset + AUDIT_PAGE_SIZE >= auditTotal}
              onClick={() => setAuditOffset(auditOffset + AUDIT_PAGE_SIZE)}
            >
              {tr('Next →', 'Далее →')}
            </button>
          </div>
        ) : null}
      </section>

      {accessEditor ? (
        <div
          className="admin-modal-backdrop admin-access-modal-backdrop"
          role="presentation"
          onMouseDown={() => !savingId && setAccessEditor(null)}
        >
          <div
            className="admin-modal admin-access-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="staff-access-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="admin-row-between admin-access-modal-head">
              <div>
                <div className="admin-badge">{tr('Personal access', 'Персональный доступ')}</div>
                <h3 id="staff-access-title" className="admin-section-title">
                  {accessEditor.mode === 'new'
                    ? tr('New employee permissions', 'Права нового сотрудника')
                    : `${tr('Employee access', 'Доступ сотрудника')} · ${accessEditor.user_id}`}
                </h3>
              </div>
              <button className="admin-btn-outline" type="button" onClick={() => setAccessEditor(null)}>
                {tr('Close', 'Закрыть')}
              </button>
            </div>

            <div className="admin-access-identity-grid">
              <label>
                <span>{tr('Employee name', 'Имя сотрудника')}</span>
                <input
                  className="admin-input"
                  value={accessEditor.display_name}
                  onChange={(event) => setAccessEditor((current) => ({
                    ...current,
                    display_name: event.target.value.slice(0, 100),
                  }))}
                />
              </label>
              <label>
                <span>{tr('Role template', 'Шаблон роли')}</span>
                <select
                  className="admin-input"
                  value={accessEditor.role}
                  onChange={(event) => updateEditorRole(event.target.value)}
                >
                  {roleOptions.map((option) => (
                    <option
                      key={option.value}
                      value={option.value}
                      disabled={option.value === 'admin' && !isProtectedActor}
                    >
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="admin-access-template-note">
              {tr(
                'Changing the role reapplies its recommended template. You can then adjust every switch.',
                'При смене роли применяется рекомендуемый шаблон. После этого каждый переключатель можно настроить.'
              )}
            </div>

            <div className="admin-access-groups">
              {permissionGroups(tr).map((group) => (
                <section className="admin-access-group" key={group.id}>
                  <div className="admin-access-group-head">
                    <strong>{group.title}</strong>
                    {group.description ? <p>{group.description}</p> : null}
                  </div>
                  <div className="admin-access-options">
                    {group.items.map(([permission, label]) => {
                      const enabled = Boolean(accessEditor.permissions?.[permission]);
                      const available = canGrantPermission(permission);
                      return (
                        <button
                          key={permission}
                          type="button"
                          className={`admin-access-option ${enabled ? 'is-enabled' : ''}`}
                          disabled={!available}
                          onClick={() => updateEditorPermission(permission, !enabled)}
                          aria-pressed={enabled}
                        >
                          <span className="admin-access-option-copy">
                            <b>{label}</b>
                            {!available ? (
                              <small>{tr('Unavailable: you do not have this permission', 'Недоступно: у вас нет этого права')}</small>
                            ) : null}
                          </span>
                          <span className="admin-access-switch" aria-hidden="true"><i /></span>
                        </button>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>

            <div className="admin-access-modal-footer">
              <div>
                <strong>{Object.values(accessEditor.permissions || {}).filter(Boolean).length}</strong>
                {' '}{tr('permissions enabled', 'прав включено')}
              </div>
              <div className="admin-row-actions">
                <button className="admin-btn-outline" type="button" onClick={() => setAccessEditor(null)}>
                  {tr('Cancel', 'Отмена')}
                </button>
                <button className="admin-btn" type="button" disabled={Boolean(savingId)} onClick={saveAccessEditor}>
                  {accessEditor.mode === 'new'
                    ? tr('Apply', 'Применить')
                    : tr('Save access', 'Сохранить доступ')}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
