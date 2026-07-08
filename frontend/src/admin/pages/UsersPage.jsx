import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';

const getDisplayName = (user) => user?.first_name || user?.username || `User ${user?.user_id || ''}`;
const getAvatarUrl = (user) => String(user?.avatar_url || '').trim();
const getInitials = (user) => String(user?.first_name || user?.username || user?.user_id || 'U')
  .trim()
  .slice(0, 2)
  .toUpperCase();
const formatBalance = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `$${parsed.toFixed(2)}` : '$0.00';
};
const hasAccess = (value) => Number(value) === 1;

export default function UsersPage() {
  const [search, setSearch] = useState('');
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [accessModalOpen, setAccessModalOpen] = useState(false);
  const [balanceModalOpen, setBalanceModalOpen] = useState(false);
  const [accessForm, setAccessForm] = useState({ forex: true, binary: true });
  const [balanceForm, setBalanceForm] = useState({ balance: '0.00', sync: false });

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
    setAccessModalOpen(false);
    setBalanceModalOpen(false);
  };

  const replaceUser = (updatedUser) => {
    if (!updatedUser?.user_id) return;
    setUsers((prev) => prev.map((item) => (
      String(item.user_id) === String(updatedUser.user_id) ? { ...item, ...updatedUser } : item
    )));
  };

  const openAccessModal = () => {
    if (!selectedUser) return;
    setAccessForm({
      forex: hasAccess(selectedUser.forex_access),
      binary: hasAccess(selectedUser.binary_access),
    });
    setAccessModalOpen(true);
  };

  const openBalanceModal = () => {
    if (!selectedUser) return;
    const parsed = Number(selectedUser.balance);
    setBalanceForm({
      balance: Number.isFinite(parsed) ? parsed.toFixed(2) : '0.00',
      sync: Boolean(selectedUser.trader_id) && Number(selectedUser.balance_sync_enabled) === 1,
    });
    setBalanceModalOpen(true);
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
      replaceUser(updatedUser);
    } catch (e) {
      setError(e.message || 'Не удалось изменить блокировку');
    } finally {
      setActionLoading(false);
    }
  };

  const saveAccess = async () => {
    if (!selectedUser || actionLoading) return;
    setActionLoading(true);
    setError('');
    try {
      const res = await apiAdminFetchJson('/api/admin/users/access', {
        method: 'POST',
        body: JSON.stringify({
          user_id: selectedUser.user_id,
          forex_access: accessForm.forex,
          binary_access: accessForm.binary,
        }),
      });
      replaceUser(res.user);
      setAccessModalOpen(false);
    } catch (e) {
      setError(e.message || 'Не удалось изменить доступ');
    } finally {
      setActionLoading(false);
    }
  };

  const saveBalance = async () => {
    if (!selectedUser || actionLoading) return;
    setActionLoading(true);
    setError('');
    try {
      const res = await apiAdminFetchJson('/api/admin/users/balance', {
        method: 'POST',
        body: JSON.stringify({
          user_id: selectedUser.user_id,
          balance: balanceForm.balance,
          balance_sync_enabled: balanceForm.sync,
        }),
      });
      replaceUser(res.user);
      setBalanceModalOpen(false);
    } catch (e) {
      setError(e.message || 'Не удалось изменить баланс');
    } finally {
      setActionLoading(false);
    }
  };

  const deleteUser = async () => {
    if (!selectedUser || actionLoading) return;
    const userName = getDisplayName(selectedUser);
    if (!window.confirm(`Удалить пользователя ${userName} и все его данные в приложении?`)) return;
    setActionLoading(true);
    setError('');
    try {
      await apiAdminFetchJson(`/api/admin/users/${encodeURIComponent(selectedUser.user_id)}`, {
        method: 'DELETE',
      });
      setUsers((prev) => prev.filter((item) => String(item.user_id) !== String(selectedUser.user_id)));
      setTotal((prev) => Math.max(0, Number(prev || 0) - 1));
      closeUserCard();
    } catch (e) {
      setError(e.message || 'Не удалось удалить пользователя');
    } finally {
      setActionLoading(false);
    }
  };

  if (selectedUser) {
    const selectedAvatarUrl = getAvatarUrl(selectedUser);
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
            <div className="admin-user-title-row">
              <div className="admin-user-avatar large">
                <span>{getInitials(selectedUser)}</span>
                {selectedAvatarUrl ? (
                  <img src={selectedAvatarUrl} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                ) : null}
              </div>
              <div>
                <span className="admin-user-state">{isBlocked ? '⛔ Заблокирован' : '✅ Активен'}</span>
                <strong>{getDisplayName(selectedUser)}</strong>
              </div>
            </div>
          </div>

          <div className="admin-user-grid">
            <div><span>ID:</span> {selectedUser.user_id}</div>
            <div><span>Trader ID:</span> {selectedUser.trader_id || 'Не указан'}</div>
            <div><span>Баланс:</span> {formatBalance(selectedUser.balance)}</div>
            <div><span>Доступ Forex:</span> {hasAccess(selectedUser.forex_access) ? 'Есть' : 'Нету'}</div>
            <div><span>Доступ Binary:</span> {hasAccess(selectedUser.binary_access) ? 'Есть' : 'Нету'}</div>
            <div><span>Username:</span> {selectedUser.username || '-'}</div>
            <div><span>Имя:</span> {selectedUser.first_name || '-'}</div>
            <div><span>Режим:</span> {selectedUser.mode || '-'}</div>
            <div><span>Стратегия:</span> {selectedUser.strategy_name || selectedUser.strategy_id || '-'}</div>
            <div><span>Язык:</span> {selectedUser.lang || '-'}</div>
            <div><span>Админ:</span> {Number(selectedUser.is_admin) === 1 ? 'Да' : 'Нет'}</div>
            <div><span>Синхронизация баланса:</span> {Number(selectedUser.balance_sync_enabled) === 1 ? 'Включена' : 'Выключена'}</div>
            <div><span>Блокировка:</span> {isBlocked ? `Да${selectedUser.blocked_at ? `, ${selectedUser.blocked_at}` : ''}` : 'Нет'}</div>
            <div><span>Создан:</span> {selectedUser.created_at || '-'}</div>
          </div>

          <div className="admin-user-actions">
            <div className="admin-row-actions">
              <button className="admin-btn-outline" onClick={openAccessModal} disabled={actionLoading}>
                Редактировать доступ
              </button>
              <button className="admin-btn-outline" onClick={openBalanceModal} disabled={actionLoading}>
                Изменить баланс
              </button>
            </div>
            <button
              className={isBlocked ? 'admin-btn' : 'admin-btn-outline danger'}
              onClick={() => toggleBlocked(selectedUser)}
              disabled={actionLoading}
            >
              {isBlocked ? 'Разблокировать' : 'Заблокировать'}
            </button>
            <button className="admin-btn-outline danger" onClick={deleteUser} disabled={actionLoading}>
              Удалить пользователя
            </button>
            <div className="admin-muted">Заблокированный пользователь увидит экран ограничения при входе в приложение.</div>
          </div>
        </div>

        {accessModalOpen ? (
          <div className="admin-modal-backdrop" onClick={() => setAccessModalOpen(false)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-row-between">
                <h3 className="admin-section-title">Редактировать доступ</h3>
                <button className="admin-btn-outline" onClick={() => setAccessModalOpen(false)}>Закрыть</button>
              </div>
              <div className="admin-toggle-list">
                <label className="admin-pretty-toggle">
                  <span>FOREX</span>
                  <button
                    type="button"
                    className={`admin-toggle-btn ${accessForm.forex ? 'on' : 'off'}`}
                    onClick={() => setAccessForm((prev) => ({ ...prev, forex: !prev.forex }))}
                  >
                    {accessForm.forex ? '✅' : '❌'}
                  </button>
                </label>
                <label className="admin-pretty-toggle">
                  <span>BINARY</span>
                  <button
                    type="button"
                    className={`admin-toggle-btn ${accessForm.binary ? 'on' : 'off'}`}
                    onClick={() => setAccessForm((prev) => ({ ...prev, binary: !prev.binary }))}
                  >
                    {accessForm.binary ? '✅' : '❌'}
                  </button>
                </label>
              </div>
              <div className="admin-row-actions">
                <button className="admin-btn" onClick={saveAccess} disabled={actionLoading}>
                  Сохранить
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {balanceModalOpen ? (
          <div className="admin-modal-backdrop" onClick={() => setBalanceModalOpen(false)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-row-between">
                <h3 className="admin-section-title">Изменить баланс</h3>
                <button className="admin-btn-outline" onClick={() => setBalanceModalOpen(false)}>Закрыть</button>
              </div>
              <div className="admin-field">
                <label className="admin-label">Текущий баланс</label>
                <div className="admin-readonly-value">{formatBalance(selectedUser.balance)}</div>
              </div>
              <div className="admin-field">
                <label className="admin-label">Новый баланс</label>
                <input
                  className="admin-input"
                  inputMode="decimal"
                  value={balanceForm.balance}
                  onChange={(e) => setBalanceForm((prev) => ({ ...prev, balance: e.target.value.replace(',', '.') }))}
                />
              </div>
              <label className="admin-pretty-toggle wide">
                <span>Синхронизация баланса</span>
                <button
                  type="button"
                  className={`admin-toggle-btn ${balanceForm.sync ? 'on' : 'off'}`}
                  disabled={!selectedUser.trader_id}
                  onClick={() => {
                    if (!selectedUser.trader_id) return;
                    setBalanceForm((prev) => ({ ...prev, sync: !prev.sync }));
                  }}
                >
                  {balanceForm.sync ? '✅' : '❌'}
                </button>
              </label>
              <div className="admin-muted">
                {selectedUser.trader_id
                  ? 'При активной синхронизации баланс будет подтягиваться с Pocket.'
                  : 'Баланс можно задать вручную. Синхронизация доступна только после указания Trader ID.'}
              </div>
              <div className="admin-row-actions">
                <button className="admin-btn" onClick={saveBalance} disabled={actionLoading}>
                  Сохранить
                </button>
              </div>
            </div>
          </div>
        ) : null}
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
          const avatarUrl = getAvatarUrl(user);
          return (
            <button
              key={user.user_id}
              className={`admin-entity-card ${blocked ? 'blocked' : ''}`}
              type="button"
              onClick={() => openUserCard(user.user_id)}
            >
              <div className="admin-entity-head">
                <div className="admin-entity-title">
                  <div className="admin-user-avatar">
                    <span>{getInitials(user)}</span>
                    {avatarUrl ? (
                      <img src={avatarUrl} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                    ) : null}
                  </div>
                  <span>{getDisplayName(user)}</span>
                  <span className="admin-state-icon">{blocked ? '⛔' : '✅'}</span>
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
                ID: {user.user_id} | Trader: {user.trader_id || '-'} | {formatBalance(user.balance)} | Forex {hasAccess(user.forex_access) ? 'есть' : 'нет'} | Binary {hasAccess(user.binary_access) ? 'есть' : 'нет'} | {blocked ? 'blocked' : (user.mode || '-')}
              </div>
            </button>
          );
        })}
      </div>

      {!loading && users.length === 0 ? <div className="admin-muted">Пользователи не найдены</div> : null}
    </div>
  );
}

