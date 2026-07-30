import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';
import { useAdminLocale } from '../useAdminLocale';

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
const isManualTraderId = (user) => Number(user?.trader_id_is_manual || 0) === 1;
const formatArchiveDate = (value) => {
  if (!value) return '—';
  const normalized = String(value).includes('T') ? String(value) : String(value).replace(' ', 'T');
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed);
};

export default function UsersPage() {
  const { tr } = useAdminLocale();
  const [search, setSearch] = useState('');
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [accessModalOpen, setAccessModalOpen] = useState(false);
  const [balanceModalOpen, setBalanceModalOpen] = useState(false);
  const [clearCacheModalOpen, setClearCacheModalOpen] = useState(false);
  const [archiveModalOpen, setArchiveModalOpen] = useState(false);
  const [archives, setArchives] = useState([]);
  const [archivesLoading, setArchivesLoading] = useState(false);
  const [archiveDetail, setArchiveDetail] = useState(null);
  const [archiveDetailLoading, setArchiveDetailLoading] = useState(false);
  const [confirmationPhrase, setConfirmationPhrase] = useState('');
  const [confirmationValue, setConfirmationValue] = useState('');
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
      setError(e.message || tr('Could not load users', 'Не удалось загрузить пользователей'));
    } finally {
      setLoading(false);
    }
  }, [tr]);

  const loadArchives = useCallback(async (userId) => {
    if (!userId) return;
    setArchivesLoading(true);
    try {
      const res = await apiAdminFetchJson(
        `/api/admin/users/${encodeURIComponent(userId)}/archives`
      );
      setArchives(res.archives || []);
      setConfirmationPhrase(res.confirmation_phrase || `CLEAR ${userId}`);
    } catch (e) {
      setError(e.message || tr('Could not load data archives', 'Не удалось загрузить архивы данных'));
    } finally {
      setArchivesLoading(false);
    }
  }, [tr]);

  useEffect(() => {
    const timer = window.setTimeout(() => loadUsers(''), 0);
    return () => window.clearTimeout(timer);
  }, [loadUsers]);

  useEffect(() => {
    if (!selectedUserId) return undefined;
    const timer = window.setTimeout(() => loadArchives(selectedUserId), 0);
    return () => window.clearTimeout(timer);
  }, [loadArchives, selectedUserId]);

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
    setStatus('');
    setError('');
    setArchiveDetail(null);
    setArchives([]);
    setConfirmationPhrase('');
  };

  const closeUserCard = () => {
    setSelectedUserId(null);
    setAccessModalOpen(false);
    setBalanceModalOpen(false);
    setClearCacheModalOpen(false);
    setArchiveModalOpen(false);
    setArchiveDetail(null);
    setConfirmationValue('');
    setArchives([]);
    setConfirmationPhrase('');
    setStatus('');
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
      sync: !isManualTraderId(selectedUser)
        && Boolean(selectedUser.pocket_trader_id)
        && Number(selectedUser.balance_sync_enabled) === 1,
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
      setError(e.message || tr('Could not update the block status', 'Не удалось изменить блокировку'));
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
      setError(e.message || tr('Could not update access', 'Не удалось изменить доступ'));
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
      setError(e.message || tr('Could not update the balance', 'Не удалось изменить баланс'));
    } finally {
      setActionLoading(false);
    }
  };

  const toggleProfileEditing = async (user) => {
    if (!user || actionLoading) return;
    const nextAllowed = Number(user.profile_edit_allowed || 0) !== 1;
    setActionLoading(true);
    setError('');
    setStatus('');
    try {
      const res = await apiAdminFetchJson('/api/admin/users/profile-edit', {
        method: 'POST',
        body: JSON.stringify({
          user_id: user.user_id,
          profile_edit_allowed: nextAllowed,
        }),
      });
      replaceUser(res.user);
      setStatus(nextAllowed
        ? tr('Profile editing enabled for this user', 'Редактирование профиля разрешено')
        : tr('Profile editing disabled for this user', 'Редактирование профиля запрещено'));
    } catch (e) {
      setError(e.message || tr('Could not update profile permission', 'Не удалось изменить разрешение профиля'));
    } finally {
      setActionLoading(false);
    }
  };

  const openClearCacheModal = () => {
    if (!selectedUser) return;
    setConfirmationValue('');
    setClearCacheModalOpen(true);
    setError('');
  };

  const clearUserCache = async () => {
    if (!selectedUser || actionLoading) return;
    const requiredPhrase = confirmationPhrase || `CLEAR ${selectedUser.user_id}`;
    if (confirmationValue.trim() !== requiredPhrase) return;
    setActionLoading(true);
    setError('');
    setStatus('');
    try {
      const res = await apiAdminFetchJson(
        `/api/admin/users/${encodeURIComponent(selectedUser.user_id)}/clear-cache`,
        {
          method: 'POST',
          body: JSON.stringify({ confirmation: confirmationValue.trim() }),
        }
      );
      replaceUser(res.user);
      setClearCacheModalOpen(false);
      setConfirmationValue('');
      setStatus(tr(
        `User data archived and cache cleared. Archive #${res.archive_id}.`,
        `Данные пользователя помещены в архив, кэш очищен. Архив №${res.archive_id}.`
      ));
      await loadArchives(selectedUser.user_id);
    } catch (e) {
      setError(e.message || tr('Could not clear user cache', 'Не удалось очистить кэш пользователя'));
    } finally {
      setActionLoading(false);
    }
  };

  const openArchiveModal = async () => {
    if (!selectedUser) return;
    setArchiveDetail(null);
    setArchiveModalOpen(true);
    await loadArchives(selectedUser.user_id);
  };

  const loadArchiveDetail = async (archiveId) => {
    if (!selectedUser || !archiveId) return;
    setArchiveDetailLoading(true);
    setError('');
    try {
      const res = await apiAdminFetchJson(
        `/api/admin/users/${encodeURIComponent(selectedUser.user_id)}/archives/${encodeURIComponent(archiveId)}`
      );
      setArchiveDetail(res.archive || null);
    } catch (e) {
      setError(e.message || tr('Could not open archive', 'Не удалось открыть архив'));
    } finally {
      setArchiveDetailLoading(false);
    }
  };

  const downloadArchive = () => {
    if (!archiveDetail?.snapshot) return;
    const blob = new Blob(
      [JSON.stringify(archiveDetail.snapshot, null, 2)],
      { type: 'application/json;charset=utf-8' }
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `elizabeth-user-${archiveDetail.user_id}-archive-${archiveDetail.id}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const deleteUser = async () => {
    if (!selectedUser || actionLoading) return;
    const userName = getDisplayName(selectedUser);
    if (!window.confirm(tr(
      `Delete ${userName} and all of their application data?`,
      `Удалить пользователя ${userName} и все его данные в приложении?`
    ))) return;
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
      setError(e.message || tr('Could not delete the user', 'Не удалось удалить пользователя'));
    } finally {
      setActionLoading(false);
    }
  };

  if (selectedUser) {
    const selectedAvatarUrl = getAvatarUrl(selectedUser);
    const profileEditingAllowed = Number(selectedUser.profile_edit_allowed || 0) === 1;
    const manualTraderId = isManualTraderId(selectedUser);
    const canSyncPocket = Boolean(selectedUser.pocket_trader_id) && !manualTraderId;
    const requiredConfirmation = confirmationPhrase || `CLEAR ${selectedUser.user_id}`;
    const confirmationMatches = confirmationValue.trim() === requiredConfirmation;
    const archiveSnapshot = archiveDetail?.snapshot || {};
    return (
      <div className="admin-card">
        <div className="admin-row-between">
          <h3 className="admin-section-title">{tr('User profile', 'Карточка пользователя')}</h3>
          <button className="admin-btn-outline" onClick={closeUserCard}>
            {tr('← Back to list', '← К списку')}
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
                <span className="admin-user-state">
                  {isBlocked ? tr('⛔ Blocked', '⛔ Заблокирован') : tr('✅ Active', '✅ Активен')}
                </span>
                <strong>{getDisplayName(selectedUser)}</strong>
              </div>
            </div>
          </div>

          <div className="admin-user-grid">
            <div><span>ID:</span> {selectedUser.user_id}</div>
            <div>
              <span>Trader ID:</span>
              {selectedUser.trader_id || tr('Not set', 'Не указан')}
              {manualTraderId ? <b className="admin-user-manual-badge">{tr('Manual', 'Ручной')}</b> : null}
            </div>
            <div><span>{tr('Balance', 'Баланс')}:</span> {formatBalance(selectedUser.balance)}</div>
            <div><span>{tr('Forex access', 'Доступ Forex')}:</span> {hasAccess(selectedUser.forex_access) ? tr('Enabled', 'Есть') : tr('Disabled', 'Нету')}</div>
            <div><span>{tr('Binary access', 'Доступ Binary')}:</span> {hasAccess(selectedUser.binary_access) ? tr('Enabled', 'Есть') : tr('Disabled', 'Нету')}</div>
            <div><span>Username:</span> {selectedUser.username || '-'}</div>
            <div><span>{tr('Displayed name', 'Отображаемое имя')}:</span> {selectedUser.first_name || '-'}</div>
            <div><span>{tr('Telegram name', 'Имя в Telegram')}:</span> {selectedUser.telegram_first_name || '-'}</div>
            <div><span>{tr('Mode', 'Режим')}:</span> {selectedUser.mode || '-'}</div>
            <div><span>{tr('Strategy', 'Стратегия')}:</span> {selectedUser.strategy_name || selectedUser.strategy_id || '-'}</div>
            <div><span>{tr('Language', 'Язык')}:</span> {selectedUser.lang || '-'}</div>
            <div><span>{tr('Admin', 'Админ')}:</span> {Number(selectedUser.is_admin) === 1 ? tr('Yes', 'Да') : tr('No', 'Нет')}</div>
            <div>
              <span>{tr('Balance sync', 'Синхронизация баланса')}:</span>
              {manualTraderId
                ? tr('Unavailable for manual Trader ID', 'Недоступна для ручного Trader ID')
                : (Number(selectedUser.balance_sync_enabled) === 1 ? tr('Enabled', 'Включена') : tr('Disabled', 'Выключена'))}
            </div>
            <div><span>{tr('Blocked', 'Блокировка')}:</span> {isBlocked ? `${tr('Yes', 'Да')}${selectedUser.blocked_at ? `, ${selectedUser.blocked_at}` : ''}` : tr('No', 'Нет')}</div>
            <div><span>{tr('Created', 'Создан')}:</span> {selectedUser.created_at || '-'}</div>
          </div>

          <div className={`admin-user-profile-permission ${profileEditingAllowed ? 'is-enabled' : ''}`}>
            <div className="admin-user-profile-permission-copy">
              <span className="admin-user-profile-permission-kicker">{tr('Personal permission', 'Персональное разрешение')}</span>
              <strong>{tr('Name and Trader ID editing', 'Редактирование имени и Trader ID')}</strong>
              <p>
                {profileEditingAllowed
                  ? tr(
                    'The name and ID become clickable in the profile; the user can change both values.',
                    'Имя и ID становятся кликабельными в профиле — пользователь может менять оба значения.'
                  )
                  : tr(
                    'The values are read-only and clicks do not open editing.',
                    'Значения доступны только для просмотра, нажатие не открывает редактирование.'
                  )}
              </p>
            </div>
            <button
              type="button"
              className={`admin-user-profile-switch ${profileEditingAllowed ? 'on' : 'off'}`}
              onClick={() => toggleProfileEditing(selectedUser)}
              disabled={actionLoading}
              aria-pressed={profileEditingAllowed}
            >
              <span aria-hidden="true" />
              <b>{profileEditingAllowed ? tr('Allowed', 'Разрешено') : tr('Forbidden', 'Запрещено')}</b>
            </button>
            <div className="admin-user-profile-permission-note">
              {tr(
                'A Trader ID entered by the user is stored separately, marked as manual and never sent to Pocket API. Pocket balance synchronization is disabled for it.',
                'Trader ID, введённый пользователем, хранится отдельно, помечается как ручной и не отправляется в Pocket API. Синхронизация баланса для него отключается.'
              )}
            </div>
          </div>

          <div className="admin-user-cache-panel">
            <div className="admin-user-cache-copy">
              <span className="admin-user-profile-permission-kicker">
                {tr('User data', 'Данные пользователя')}
              </span>
              <strong>{tr('Archive and clear cache', 'Архив и очистка кэша')}</strong>
              <p>
                {tr(
                  'Creates a complete snapshot of both systems, then resets chats, funnel stages, Trader ID, Pocket/AIO data, balance, analyses and strategies.',
                  'Создаёт полный снимок обеих систем, затем сбрасывает чаты, этапы воронок, Trader ID, Pocket/AIO, баланс, анализы и стратегии.'
                )}
              </p>
            </div>
            <div className="admin-user-cache-actions">
              <button
                type="button"
                className="admin-btn-outline"
                onClick={openArchiveModal}
                disabled={actionLoading || archivesLoading}
              >
                {tr('Data archive', 'Архив данных')} · {archives.length}
              </button>
              <button
                type="button"
                className="admin-btn-outline danger"
                onClick={openClearCacheModal}
                disabled={actionLoading}
              >
                {tr('Clear cache', 'Очистить кэш')}
              </button>
            </div>
            <div className="admin-user-cache-note">
              {tr(
                'Telegram identity, staff access and previous archives are preserved so the user card remains available.',
                'Telegram-идентичность, доступ сотрудника и предыдущие архивы сохраняются, поэтому карточка пользователя не исчезает.'
              )}
            </div>
          </div>

          <div className="admin-user-actions">
            <div className="admin-row-actions">
              <button className="admin-btn-outline" onClick={openAccessModal} disabled={actionLoading}>
                {tr('Edit access', 'Редактировать доступ')}
              </button>
              <button className="admin-btn-outline" onClick={openBalanceModal} disabled={actionLoading}>
                {tr('Edit balance', 'Изменить баланс')}
              </button>
            </div>
            <button
              className={isBlocked ? 'admin-btn' : 'admin-btn-outline danger'}
              onClick={() => toggleBlocked(selectedUser)}
              disabled={actionLoading}
            >
              {isBlocked ? tr('Unblock', 'Разблокировать') : tr('Block', 'Заблокировать')}
            </button>
            <button className="admin-btn-outline danger" onClick={deleteUser} disabled={actionLoading}>
              {tr('Delete user', 'Удалить пользователя')}
            </button>
            <div className="admin-muted">
              {tr(
                'A blocked user will see a restriction screen when opening the application.',
                'Заблокированный пользователь увидит экран ограничения при входе в приложение.'
              )}
            </div>
          </div>
        </div>

        {status ? <div className="admin-success">{status}</div> : null}
        {error ? <div className="admin-error">{error}</div> : null}

        {accessModalOpen ? (
          <div className="admin-modal-backdrop" onClick={() => setAccessModalOpen(false)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-row-between">
                <h3 className="admin-section-title">{tr('Edit access', 'Редактировать доступ')}</h3>
                <button className="admin-btn-outline" onClick={() => setAccessModalOpen(false)}>{tr('Close', 'Закрыть')}</button>
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
                  {tr('Save', 'Сохранить')}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {balanceModalOpen ? (
          <div className="admin-modal-backdrop" onClick={() => setBalanceModalOpen(false)}>
            <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-row-between">
                <h3 className="admin-section-title">{tr('Edit balance', 'Изменить баланс')}</h3>
                <button className="admin-btn-outline" onClick={() => setBalanceModalOpen(false)}>{tr('Close', 'Закрыть')}</button>
              </div>
              <div className="admin-field">
                <label className="admin-label">{tr('Current balance', 'Текущий баланс')}</label>
                <div className="admin-readonly-value">{formatBalance(selectedUser.balance)}</div>
              </div>
              <div className="admin-field">
                <label className="admin-label">{tr('New balance', 'Новый баланс')}</label>
                <input
                  className="admin-input"
                  inputMode="decimal"
                  value={balanceForm.balance}
                  onChange={(e) => setBalanceForm((prev) => ({ ...prev, balance: e.target.value.replace(',', '.') }))}
                />
              </div>
              <label className="admin-pretty-toggle wide">
                <span>{tr('Balance synchronization', 'Синхронизация баланса')}</span>
                <button
                  type="button"
                  className={`admin-toggle-btn ${balanceForm.sync ? 'on' : 'off'}`}
                  disabled={!canSyncPocket}
                  onClick={() => {
                    if (!canSyncPocket) return;
                    setBalanceForm((prev) => ({ ...prev, sync: !prev.sync }));
                  }}
                >
                  {balanceForm.sync ? '✅' : '❌'}
                </button>
              </label>
              <div className="admin-muted">
                {manualTraderId
                  ? tr(
                    'A manual Trader ID is not checked through Pocket API. Balance can only be set manually.',
                    'Ручной Trader ID не проверяется через Pocket API. Баланс можно задавать только вручную.'
                  )
                  : selectedUser.pocket_trader_id
                  ? tr('When synchronization is active, the balance is loaded from Pocket.', 'При активной синхронизации баланс будет подтягиваться с Pocket.')
                  : tr('The balance can be set manually. Synchronization becomes available after a Trader ID is assigned.', 'Баланс можно задать вручную. Синхронизация доступна только после указания Trader ID.')}
              </div>
              <div className="admin-row-actions">
                <button className="admin-btn" onClick={saveBalance} disabled={actionLoading}>
                  {tr('Save', 'Сохранить')}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {clearCacheModalOpen ? (
          <div
            className="admin-modal-backdrop"
            onClick={() => {
              if (!actionLoading) setClearCacheModalOpen(false);
            }}
          >
            <div className="admin-modal admin-cache-confirm-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-row-between">
                <div>
                  <span className="admin-user-profile-permission-kicker">
                    {tr('Protected action', 'Защищённое действие')}
                  </span>
                  <h3 className="admin-section-title">{tr('Clear user cache', 'Очистить кэш пользователя')}</h3>
                </div>
                <button
                  className="admin-btn-outline"
                  onClick={() => setClearCacheModalOpen(false)}
                  disabled={actionLoading}
                >
                  {tr('Close', 'Закрыть')}
                </button>
              </div>

              <div className="admin-cache-warning">
                <strong>{tr('An archive is created first', 'Сначала будет создан архив')}</strong>
                <p>
                  {tr(
                    'After the snapshot is saved, live chats, AI memory, both funnel states, Trader ID, Pocket/AIO data, balance, analyses and custom strategies will be cleared.',
                    'После сохранения снимка будут очищены активные чаты, память AI, состояния обеих воронок, Trader ID, Pocket/AIO, баланс, анализы и кастомные стратегии.'
                  )}
                </p>
              </div>

              <div className="admin-cache-preserved">
                <span>{tr('Preserved', 'Сохраняется')}</span>
                <div>
                  <b>Telegram ID</b>
                  <b>{tr('Telegram identity', 'Telegram-профиль')}</b>
                  <b>{tr('Staff role', 'Роль сотрудника')}</b>
                  <b>{tr('Previous archives', 'Предыдущие архивы')}</b>
                </div>
              </div>

              <label className="admin-field">
                <span className="admin-label">
                  {tr('Type the phrase exactly', 'Введите фразу без изменений')}
                </span>
                <code className="admin-confirmation-phrase">{requiredConfirmation}</code>
                <input
                  className="admin-input"
                  autoComplete="off"
                  value={confirmationValue}
                  onChange={(e) => setConfirmationValue(e.target.value)}
                  placeholder={requiredConfirmation}
                />
              </label>

              <div className="admin-row-actions admin-cache-confirm-actions">
                <button
                  type="button"
                  className="admin-btn-outline"
                  onClick={() => setClearCacheModalOpen(false)}
                  disabled={actionLoading}
                >
                  {tr('Cancel', 'Отмена')}
                </button>
                <button
                  type="button"
                  className="admin-btn danger-solid"
                  onClick={clearUserCache}
                  disabled={!confirmationMatches || actionLoading}
                >
                  {actionLoading
                    ? tr('Archiving and clearing…', 'Архивируем и очищаем…')
                    : tr('Create archive and clear', 'Создать архив и очистить')}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {archiveModalOpen ? (
          <div className="admin-modal-backdrop" onClick={() => setArchiveModalOpen(false)}>
            <div className="admin-modal admin-archive-modal" onClick={(e) => e.stopPropagation()}>
              <div className="admin-row-between">
                <div>
                  <span className="admin-user-profile-permission-kicker">
                    {tr('User data', 'Данные пользователя')}
                  </span>
                  <h3 className="admin-section-title">
                    {archiveDetail
                      ? `${tr('Archive', 'Архив')} #${archiveDetail.id}`
                      : tr('Data archive', 'Архив данных')}
                  </h3>
                </div>
                <button
                  className="admin-btn-outline"
                  onClick={() => setArchiveModalOpen(false)}
                >
                  {tr('Close', 'Закрыть')}
                </button>
              </div>

              {archiveDetail ? (
                <div className="admin-archive-detail">
                  <div className="admin-row-actions">
                    <button
                      type="button"
                      className="admin-btn-outline"
                      onClick={() => setArchiveDetail(null)}
                    >
                      {tr('← Archive list', '← К списку архивов')}
                    </button>
                    <button
                      type="button"
                      className="admin-btn"
                      onClick={downloadArchive}
                    >
                      {tr('Download JSON', 'Скачать JSON')}
                    </button>
                  </div>

                  <div className="admin-archive-summary-grid">
                    <div>
                      <span>{tr('Created', 'Создан')}</span>
                      <strong>{formatArchiveDate(archiveDetail.archived_at)}</strong>
                    </div>
                    <div>
                      <span>{tr('Records', 'Записей')}</span>
                      <strong>{archiveDetail.summary?.total_records || 0}</strong>
                    </div>
                    <div>
                      <span>{tr('Status', 'Статус')}</span>
                      <strong>{archiveDetail.archive_status}</strong>
                    </div>
                  </div>

                  {['main_app', 'ai_chatter'].map((sectionName) => (
                    <section className="admin-archive-section" key={sectionName}>
                      <div className="admin-row-between">
                        <h4>{sectionName === 'main_app' ? 'Elizabeth App' : 'AI Chatter'}</h4>
                        <span>
                          {archiveDetail.summary?.sections?.[sectionName]?.records || 0}
                          {' '}
                          {tr('records', 'записей')}
                        </span>
                      </div>
                      <div className="admin-archive-table-list">
                        {Object.entries(archiveSnapshot[sectionName] || {}).map(([tableName, rows]) => {
                          const normalizedRows = Array.isArray(rows) ? rows : [];
                          return (
                            <details key={tableName}>
                              <summary>
                                <span>{tableName}</span>
                                <b>{normalizedRows.length}</b>
                              </summary>
                              <pre>
                                {JSON.stringify(normalizedRows.slice(0, 25), null, 2)}
                              </pre>
                              {normalizedRows.length > 25 ? (
                                <p>
                                  {tr(
                                    `Showing 25 of ${normalizedRows.length}. Download JSON for the complete archive.`,
                                    `Показано 25 из ${normalizedRows.length}. Полные данные доступны в JSON-файле.`
                                  )}
                                </p>
                              ) : null}
                            </details>
                          );
                        })}
                      </div>
                    </section>
                  ))}
                </div>
              ) : (
                <div className="admin-archive-list">
                  {archivesLoading || archiveDetailLoading ? (
                    <div className="admin-muted">{tr('Loading…', 'Загрузка…')}</div>
                  ) : null}
                  {!archivesLoading && archives.length === 0 ? (
                    <div className="admin-archive-empty">
                      <strong>{tr('No archives yet', 'Архивов пока нет')}</strong>
                      <span>
                        {tr(
                          'The first entry will appear after clearing this user cache.',
                          'Первая запись появится после очистки кэша этого пользователя.'
                        )}
                      </span>
                    </div>
                  ) : null}
                  {archives.map((archive) => (
                    <button
                      type="button"
                      className="admin-archive-row"
                      key={archive.id}
                      onClick={() => loadArchiveDetail(archive.id)}
                      disabled={archiveDetailLoading}
                    >
                      <span className="admin-archive-row-date">
                        <strong>{formatArchiveDate(archive.archived_at)}</strong>
                        <small>
                          {tr('Administrator', 'Администратор')}: {archive.archived_by_name || archive.archived_by}
                        </small>
                      </span>
                      <span className="admin-archive-row-meta">
                        <b>{archive.summary?.total_records || 0}</b>
                        <small>{tr('records', 'записей')}</small>
                      </span>
                      <span className={`admin-archive-status is-${archive.archive_status}`}>
                        {archive.archive_status}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="admin-card">
      <div className="admin-row-between">
        <h3 className="admin-section-title">{tr('Users', 'Пользователи')}</h3>
        <div className="admin-muted">{tr('Total', 'Всего')}: {total}</div>
      </div>

      <form className="admin-inline-form" onSubmit={onSubmit}>
        <input
          className="admin-input"
          placeholder={tr('ID / username / name', 'ID / username / имя')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button className="admin-btn" type="submit">{tr('Search', 'Найти')}</button>
      </form>

      {error ? <div className="admin-error">{error}</div> : null}
      {loading ? <div className="admin-muted">{tr('Loading…', 'Загрузка...')}</div> : null}

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
                ID: {user.user_id} | Trader: {user.trader_id || '-'}{isManualTraderId(user) ? ` (${tr('manual', 'ручной')})` : ''} | {formatBalance(user.balance)} | Forex {hasAccess(user.forex_access) ? tr('enabled', 'есть') : tr('disabled', 'нет')} | Binary {hasAccess(user.binary_access) ? tr('enabled', 'есть') : tr('disabled', 'нет')} | {blocked ? 'blocked' : (user.mode || '-')}
              </div>
            </button>
          );
        })}
      </div>

      {!loading && users.length === 0 ? <div className="admin-muted">{tr('No users found', 'Пользователи не найдены')}</div> : null}
    </div>
  );
}

