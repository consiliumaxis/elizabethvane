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

const roleLabel = (role) => (
  ROLE_OPTIONS.find((item) => item.value === role)?.label || 'Менеджер'
);

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
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadStaff = useCallback(async () => {
    const result = await apiAdminFetchJson('/api/admin/staff');
    setStaff(result.staff || []);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadStaff()
        .catch((requestError) => setError(requestError.message || 'Не удалось загрузить сотрудников'))
        .finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadStaff]);

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
    </div>
  );
}
