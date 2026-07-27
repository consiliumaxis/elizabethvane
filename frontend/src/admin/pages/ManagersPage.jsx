import { useCallback, useEffect, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';
import { useAdminLocale } from '../useAdminLocale';


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
  const source = String(item.first_name || item.username || item.user_id || '?').trim();
  return source.slice(0, 2).toUpperCase();
};

export default function ManagersPage({ adminUser }) {
  const { locale, tr } = useAdminLocale();
  const roleOptions = [
    {
      value: 'manager',
      label: tr('Manager', 'Менеджер'),
      hint: tr('Can only use the /stats command.', 'Может использовать только команду /stats.'),
    },
    {
      value: 'admin',
      label: tr('Administrator', 'Администратор'),
      hint: tr('Can open the Admin Center and use /stats.', 'Имеет доступ к админцентру и команде /stats.'),
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
  const [telegramId, setTelegramId] = useState('');
  const [newRole, setNewRole] = useState('manager');
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

  const loadStaff = useCallback(async () => {
    const result = await apiAdminFetchJson('/api/admin/staff');
    setStaff(result.staff || []);
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
        body: JSON.stringify({ user_id: userId, role: newRole }),
      });
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

  const updateStaff = async (item, patch) => {
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
    } catch (requestError) {
      setError(requestError.message || tr('Could not update access', 'Не удалось обновить доступ'));
    } finally {
      setSavingId('');
    }
  };

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
            {tr('A manager can only use ', 'Менеджер получает только команду ')}<code>/stats</code>.
            {' '}{tr('An administrator can also open the entire Admin Center.', 'Администратор также может открывать весь админцентр.')}
          </p>
        </div>
        <div className="admin-managers-command">
          <strong>{tr('Quick client lookup', 'Быстрый поиск клиента')}</strong>
          <code>/stats @nickname</code>
          <code>/stats 123456789</code>
        </div>
      </section>

      {error ? <div className="admin-error admin-floating-notice">{error}</div> : null}
      {success ? <div className="admin-success admin-floating-notice">{success}</div> : null}

      <section className="admin-card admin-managers-add">
        <div className="admin-section-head">
          <div>
            <h3 className="admin-section-title">{tr('Add staff member', 'Добавить сотрудника')}</h3>
            <p className="admin-muted">
              {tr(
                'You can add an ID in advance. Name and username appear after the staff member starts the bot.',
                'Можно добавить ID заранее. Имя и username появятся после первого запуска бота сотрудником.'
              )}
            </p>
          </div>
        </div>
        <div className="admin-managers-add-grid">
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
              onChange={(event) => setNewRole(event.target.value)}
            >
              {roleOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <button className="admin-btn" type="button" disabled={savingId === 'new'} onClick={addStaff}>
            {savingId === 'new' ? tr('Adding…', 'Добавление…') : tr('Add', 'Добавить')}
          </button>
        </div>
        <div className="admin-managers-role-hint">
          {roleOptions.find((option) => option.value === newRole)?.hint}
        </div>
      </section>

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
                      {item.first_name || (item.username ? `@${item.username}` : tr('Profile not loaded yet', 'Профиль ещё не получен'))}
                      {isSelf ? <span>{tr('You', 'Вы')}</span> : null}
                    </div>
                    {item.username && item.first_name ? (
                      <div className="admin-muted">@{item.username}</div>
                    ) : null}
                    <div className="admin-manager-id">ID {item.user_id}</div>
                  </div>
                </div>

                <div className="admin-manager-controls">
                  <label>
                    <span>{tr('Role', 'Роль')}</span>
                    <select
                      className="admin-input"
                      value={item.role || 'manager'}
                      disabled={isSelf || isSaving}
                      onChange={(event) => updateStaff(item, { role: event.target.value })}
                    >
                      {roleOptions.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className={`admin-manager-status ${active ? 'is-active' : ''}`}
                    disabled={isSelf || isSaving}
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
                      disabled={isSelf || isSaving}
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
            <h3 className="admin-section-title">{tr('/stats request history', 'История запросов /stats')}</h3>
            <div className="admin-muted">
              {tr(
                'Who requested statistics, which client was searched for, and the result. Total',
                'Кто запрашивал статистику, какого клиента искал и чем завершился запрос. Всего'
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
                    <span className="admin-audit-label">{tr('Searched for', 'Искали')}</span>
                    <strong>{targetName}</strong>
                    <small>{item.target_user_id ? `ID ${item.target_user_id}` : tr('No match found', 'Совпадение не найдено')}</small>
                  </div>
                </div>
                <code className="admin-audit-query">{item.target_query || '/stats'}</code>
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
    </div>
  );
}
