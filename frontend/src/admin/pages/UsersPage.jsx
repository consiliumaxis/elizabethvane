import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';

const getDisplayName = (user) => user?.first_name || user?.username || `User ${user?.user_id || ''}`;

export default function UsersPage() {
  const [search, setSearch] = useState('');
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadUsers = useCallback(async (currentSearch = '') => {
    setLoading(true);
    setError('');
    try {
      const query = new URLSearchParams({
        limit: '100',
        offset: '0',
        search: currentSearch.trim(),
      });
      const res = await apiAdminFetchJson(`/api/admin/users?${query.toString()}`);
      const rows = res.users || [];
      setUsers(rows);
      setTotal(Number(res.total || 0));
    } catch (e) {
      setError(e.message || 'Не удалось загрузить пользователей');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers('');
  }, [loadUsers]);

  const selectedUser = useMemo(
    () => users.find((user) => String(user.user_id) === String(selectedUserId)) || null,
    [users, selectedUserId]
  );

  const isBlocked = selectedUser ? Number(selectedUser.is_blocked) === 1 : false;

  const onSubmit = (e) => {
    e.preventDefault();
    loadUsers(search);
  };

  const openUserCard = (userId) => {
    setSelectedUserId(userId);
  };

  const closeUserCard = () => {
    setSelectedUserId(null);
  };

  const toggleBlocked = async (user) => {
    if (!user || actionLoading) return;
    setActionLoading(true);
    setError('');
    try {
      const res = await apiAdminFetchJson('/api/admin/users/block', {
        method: 'POST',
        body: JSON.stringify({
          user_id: user.user_id,
          is_blocked: Number(user.is_blocked) !== 1,
        }),
      });
      const updatedUser = res.user || { ...user, is_blocked: Number(user.is_blocked) === 1 ? 0 : 1 };
      setUsers((prev) => prev.map((item) => (
        String(item.user_id) === String(updatedUser.user_id) ? { ...item, ...updatedUser } : item
      )));
    } catch (e) {
      setError(e.message || 'Не удалось изменить блокировку');
    } finally {
      setActionLoading(false);
    }
  };

  if (selectedUser) {
    return (
      <div className="admin-card">
        <div className="admin-row-between">
          <h3 className="admin-section-title">Карточка пользователя</h3>
          <button className="admin-btn-outline" onClick={closeUserCard}>
            ← К списку
          </button>
        </div>

        <div className="admin-user-detail">
          <div className="admin-user-detail-head">
            <span className="admin-user-state">{isBlocked ? '⛔ Заблокирован' : '✅ Активен'}</span>
            <strong>{getDisplayName(selectedUser)}</strong>
          </div>

          <div className="admin-user-grid">
            <div><span>ID:</span> {selectedUser.user_id}</div>
            <div><span>Username:</span> {selectedUser.username || '-'}</div>
            <div><span>Имя:</span> {selectedUser.first_name || '-'}</div>
            <div><span>Режим:</span> {selectedUser.mode || '-'}</div>
            <div><span>Стратегия:</span> {selectedUser.strategy_name || selectedUser.strategy_id || '-'}</div>
            <div><span>Язык:</span> {selectedUser.lang || '-'}</div>
            <div><span>Админ:</span> {Number(selectedUser.is_admin) === 1 ? 'Да' : 'Нет'}</div>
            <div><span>Блокировка:</span> {isBlocked ? `Да${selectedUser.blocked_at ? `, ${selectedUser.blocked_at}` : ''}` : 'Нет'}</div>
            <div><span>Создан:</span> {selectedUser.created_at || '-'}</div>
          </div>

          <div className="admin-user-actions">
            <button
              className={isBlocked ? 'admin-btn' : 'admin-btn-outline danger'}
              onClick={() => toggleBlocked(selectedUser)}
              disabled={actionLoading}
            >
              {isBlocked ? 'Разблокировать' : 'Заблокировать'}
            </button>
            <div className="admin-muted">Заблокированный пользователь увидит экран ограничения при входе в приложение.</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-card">
      <div className="admin-row-between">
        <h3 className="admin-section-title">Пользователи</h3>
        <div className="admin-muted">Всего: {total}</div>
      </div>

      <form className="admin-inline-form" onSubmit={onSubmit}>
        <input
          className="admin-input"
          placeholder="ID / username / имя"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button className="admin-btn" type="submit">Найти</button>
      </form>

      {error ? <div className="admin-error">{error}</div> : null}
      {loading ? <div className="admin-muted">Загрузка...</div> : null}

      <div className="admin-entity-list">
        {users.map((user) => {
          const blocked = Number(user.is_blocked) === 1;
          return (
            <button
              key={user.user_id}
              className={`admin-entity-card ${blocked ? 'blocked' : ''}`}
              type="button"
              onClick={() => openUserCard(user.user_id)}
            >
              <div className="admin-entity-head">
                <div className="admin-entity-title">
                  <span className="admin-state-icon">{blocked ? '⛔' : '✅'}</span>
                  <span>{getDisplayName(user)}</span>
                </div>
                <span
                  className="admin-entity-gear"
                  onClick={(e) => {
                    e.stopPropagation();
                    openUserCard(user.user_id);
                  }}
                >
                  ⚙️
                </span>
              </div>
              <div className="admin-entity-meta">
                ID: {user.user_id} | {blocked ? 'blocked' : (user.mode || '-')} | {user.strategy_name || user.strategy_id || '-'}
              </div>
            </button>
          );
        })}
      </div>

      {!loading && users.length === 0 ? <div className="admin-muted">Пользователи не найдены</div> : null}
    </div>
  );
}

