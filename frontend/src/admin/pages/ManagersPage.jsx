import { useCallback, useEffect, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';


const ROLE_OPTIONS = [
  {
    value: 'manager',
    label: 'Менеджер',
    hint: 'Может использовать только команду /stats.',
  },
  {
    value: 'admin',
    label: 'Администратор',
    hint: 'Имеет доступ к админцентру и команде /stats.',
  },
];

const AUDIT_PAGE_SIZE = 15;

const AUDIT_STATUS_OPTIONS = [
  { value: '', label: 'Все результаты' },
  { value: 'success', label: 'Успешно' },
  { value: 'not_found', label: 'Клиент не найден' },
  { value: 'invalid_query', label: 'Неверный запрос' },
  { value: 'denied', label: 'Нет доступа' },
  { value: 'private_chat_required', label: 'Не личный чат' },
];

const AUDIT_STATUS_META = {
  success: { label: 'Успешно', tone: 'success' },
  not_found: { label: 'Клиент не найден', tone: 'warning' },
  invalid_query: { label: 'Неверный запрос', tone: 'warning' },
  denied: { label: 'Нет доступа', tone: 'danger' },
  private_chat_required: { label: 'Не личный чат', tone: 'warning' },
};

const roleLabel = (role) => (
  ROLE_OPTIONS.find((item) => item.value === role)?.label || 'Менеджер'
);

const formatAuditDate = (value) => {
  if (!value) return 'Время не указано';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('ru-RU', {
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
      setError(requestError.message || 'Не удалось загрузить историю запросов');
    } finally {
      setAuditLoading(false);
    }
  }, [appliedAuditSearch, auditOffset, auditStatus]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadStaff()
        .catch((requestError) => setError(requestError.message || 'Не удалось загрузить сотрудников'))
        .finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadStaff]);

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
      setError('Введите корректный Telegram ID сотрудника');
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
      flashSuccess(`${roleLabel(newRole)} добавлен: ${userId}`);
      await loadStaff();
    } catch (requestError) {
      setError(requestError.message || 'Не удалось добавить сотрудника');
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
      flashSuccess('Доступ сотрудника обновлён');
      await loadStaff();
    } catch (requestError) {
      setError(requestError.message || 'Не удалось обновить доступ');
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
      flashSuccess(`Сотрудник ${item.user_id} удалён`);
      await loadStaff();
    } catch (requestError) {
      setError(requestError.message || 'Не удалось удалить сотрудника');
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
          <div className="admin-badge">Доступ сотрудников</div>
          <h3 className="admin-section-title">Менеджеры и администраторы</h3>
          <p className="admin-muted">
            Менеджер получает только команду <code>/stats</code>. Администратор также может открывать весь админцентр.
          </p>
        </div>
        <div className="admin-managers-command">
          <strong>Быстрый поиск клиента</strong>
          <code>/stats @nickname</code>
          <code>/stats 123456789</code>
        </div>
      </section>

      {error ? <div className="admin-error admin-floating-notice">{error}</div> : null}
      {success ? <div className="admin-success admin-floating-notice">{success}</div> : null}

      <section className="admin-card admin-managers-add">
        <div className="admin-section-head">
          <div>
            <h3 className="admin-section-title">Добавить сотрудника</h3>
            <p className="admin-muted">
              Можно добавить ID заранее. Имя и username появятся после первого запуска бота сотрудником.
            </p>
          </div>
        </div>
        <div className="admin-managers-add-grid">
          <label>
            <span>Telegram ID</span>
            <input
              className="admin-input"
              inputMode="numeric"
              placeholder="Например 123456789"
              value={telegramId}
              onChange={(event) => setTelegramId(event.target.value.replace(/\D/g, '').slice(0, 20))}
            />
          </label>
          <label>
            <span>Роль</span>
            <select
              className="admin-input"
              value={newRole}
              onChange={(event) => setNewRole(event.target.value)}
            >
              {ROLE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <button className="admin-btn" type="button" disabled={savingId === 'new'} onClick={addStaff}>
            {savingId === 'new' ? 'Добавление…' : 'Добавить'}
          </button>
        </div>
        <div className="admin-managers-role-hint">
          {ROLE_OPTIONS.find((option) => option.value === newRole)?.hint}
        </div>
      </section>

      <section className="admin-card">
        <div className="admin-row-between admin-managers-list-head">
          <div>
            <h3 className="admin-section-title">Список сотрудников</h3>
            <div className="admin-muted">Всего: {staff.length}</div>
          </div>
          <button className="admin-btn-outline" type="button" disabled={loading} onClick={loadStaff}>
            Обновить
          </button>
        </div>

        {loading ? <div className="admin-muted">Загрузка сотрудников…</div> : null}
        {!loading && !staff.length ? (
          <div className="admin-managers-empty">Сотрудники пока не добавлены.</div>
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
                      {item.first_name || (item.username ? `@${item.username}` : 'Профиль ещё не получен')}
                      {isSelf ? <span>Вы</span> : null}
                    </div>
                    {item.username && item.first_name ? (
                      <div className="admin-muted">@{item.username}</div>
                    ) : null}
                    <div className="admin-manager-id">ID {item.user_id}</div>
                  </div>
                </div>

                <div className="admin-manager-controls">
                  <label>
                    <span>Роль</span>
                    <select
                      className="admin-input"
                      value={item.role || 'manager'}
                      disabled={isSelf || isSaving}
                      onChange={(event) => updateStaff(item, { role: event.target.value })}
                    >
                      {ROLE_OPTIONS.map((option) => (
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
                    {active ? 'Доступ включён' : 'Доступ выключен'}
                  </button>
                </div>

                <div className="admin-manager-footer">
                  <span className={`admin-manager-role-badge ${item.role || 'manager'}`}>
                    {roleLabel(item.role)}
                  </span>
                  {deleteConfirmId === String(item.user_id) ? (
                    <div className="admin-manager-confirm">
                      <span>Удалить доступ?</span>
                      <button type="button" disabled={isSaving} onClick={() => deleteStaff(item)}>Да</button>
                      <button type="button" disabled={isSaving} onClick={() => setDeleteConfirmId('')}>Нет</button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="admin-mini-action danger"
                      disabled={isSelf || isSaving}
                      onClick={() => setDeleteConfirmId(String(item.user_id))}
                    >
                      Удалить
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
            <h3 className="admin-section-title">История запросов /stats</h3>
            <div className="admin-muted">
              Кто запрашивал статистику, какого клиента искал и чем завершился запрос. Всего: {auditTotal}
            </div>
          </div>
          <button
            className="admin-btn-outline"
            type="button"
            disabled={auditLoading}
            onClick={loadAudit}
          >
            Обновить
          </button>
        </div>

        <form className="admin-audit-filters" onSubmit={applyAuditSearch}>
          <label>
            <span>Поиск</span>
            <input
              className="admin-input"
              value={auditSearch}
              placeholder="ID, username или команда"
              onChange={(event) => setAuditSearch(event.target.value.slice(0, 100))}
            />
          </label>
          <label>
            <span>Результат</span>
            <select
              className="admin-input"
              value={auditStatus}
              onChange={(event) => {
                setAuditOffset(0);
                setAuditStatus(event.target.value);
              }}
            >
              {AUDIT_STATUS_OPTIONS.map((option) => (
                <option key={option.value || 'all'} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <button className="admin-btn" type="submit" disabled={auditLoading}>Найти</button>
        </form>

        {auditLoading ? <div className="admin-muted admin-audit-loading">Загрузка истории…</div> : null}
        {!auditLoading && !auditRows.length ? (
          <div className="admin-managers-empty">По выбранным условиям запросов пока нет.</div>
        ) : null}

        <div className="admin-audit-list">
          {auditRows.map((item) => {
            const statusMeta = AUDIT_STATUS_META[item.result_status] || {
              label: item.result_status || 'Неизвестно',
              tone: 'neutral',
            };
            const requesterName = item.requester_first_name
              || (item.requester_username ? `@${item.requester_username}` : 'Профиль не получен');
            const targetName = item.target_user_id
              ? (
                item.target_first_name
                || (item.target_username ? `@${item.target_username}` : `ID ${item.target_user_id}`)
              )
              : 'Клиент не определён';
            return (
              <article className="admin-audit-card" key={item.id}>
                <div className="admin-audit-card-head">
                  <span className={`admin-audit-status ${statusMeta.tone}`}>{statusMeta.label}</span>
                  <time>{formatAuditDate(item.created_at)}</time>
                </div>
                <div className="admin-audit-grid">
                  <div>
                    <span className="admin-audit-label">Запросил</span>
                    <strong>{requesterName}</strong>
                    <small>
                      ID {item.requested_by}
                      {' · '}
                      {item.requester_role ? roleLabel(item.requester_role) : 'роль не назначена'}
                    </small>
                  </div>
                  <div>
                    <span className="admin-audit-label">Искали</span>
                    <strong>{targetName}</strong>
                    <small>{item.target_user_id ? `ID ${item.target_user_id}` : 'Совпадение не найдено'}</small>
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
              ← Назад
            </button>
            <span>Страница {auditPage} из {auditPages}</span>
            <button
              className="admin-btn-outline"
              type="button"
              disabled={auditLoading || auditOffset + AUDIT_PAGE_SIZE >= auditTotal}
              onClick={() => setAuditOffset(auditOffset + AUDIT_PAGE_SIZE)}
            >
              Далее →
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
