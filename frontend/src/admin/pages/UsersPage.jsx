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
  const [accessMap, setAccessMap] = useState({});

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
      setAccessMap((prev) => {
        const next = { ...prev };
        rows.forEach((user) => {
          const key = String(user.user_id);
          if (typeof next[key] === 'undefined') {
            next[key] = true;
          }
        });
        return next;
      });
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

  const isAccessEnabled = selectedUser ? Boolean(accessMap[String(selectedUser.user_id)]) : false;

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

  const toggleAccess = (userId) => {
    const key = String(userId);
    setAccessMap((prev) => ({ ...prev, [key]: !prev[key] }));
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
            <span className="admin-user-state">{isAccessEnabled ? '✅ Доступ есть' : '❌ Доступа нет'}</span>
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
            <div><span>Создан:</span> {selectedUser.created_at || '-'}</div>
          </div>

          <div className="admin-user-actions">
            <button className="admin-btn" onClick={() => toggleAccess(selectedUser.user_id)}>
              {isAccessEnabled ? 'Забрать доступ' : 'Выдать доступ'}
            </button>
            <div className="admin-muted">Временный frontend fallback. Подключим backend позже.</div>
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
          const hasAccess = Boolean(accessMap[String(user.user_id)]);
          return (
            <button
              key={user.user_id}
              className="admin-entity-card"
              type="button"
              onClick={() => openUserCard(user.user_id)}
            >
              <div className="admin-entity-head">
                <div className="admin-entity-title">
                  <span className="admin-state-icon">{hasAccess ? '✅' : '❌'}</span>
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
                ID: {user.user_id} | {user.mode || '-'} | {user.strategy_name || user.strategy_id || '-'}
              </div>
            </button>
          );
        })}
      </div>

      {!loading && users.length === 0 ? <div className="admin-muted">Пользователи не найдены</div> : null}
    </div>
  );
}

