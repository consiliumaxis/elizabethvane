import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';
import { useAdminLocale } from '../useAdminLocale';
import { PERMISSIONS, hasPermission } from '../permissions';

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
const formatPocketValue = (value) => (
  value === null || value === undefined || String(value).trim() === '' ? '—' : String(value)
);
const getPocketEventLabel = (eventSlug, tr) => {
  const normalized = String(eventSlug || '').trim().toLowerCase();
  if (normalized === 'registration') return tr('Registration', 'Регистрация');
  if (normalized === 'ftd') return tr('First deposit', 'Первый депозит');
  if (normalized === 'dep') return tr('Repeat deposit', 'Повторный депозит');
  return eventSlug || tr('Pocket event', 'Событие Pocket');
};

const ARCHIVE_TABLE_LABELS = {
  users: ['User profile', 'Профиль пользователя'],
  user_onboarding: ['Questionnaire and funnel', 'Опросник и воронка'],
  user_mode_access: ['Trading mode access', 'Доступ к торговым режимам'],
  user_analyses: ['Trading analyses', 'Торговые анализы'],
  user_presets: ['User strategies', 'Стратегии пользователя'],
  ai_chats: ['AI chats', 'Диалоги с AI'],
  ai_messages: ['AI chat messages', 'Сообщения в диалогах AI'],
  aio_postback_events: ['AIO events', 'События AIO'],
  pocket_postback_events: ['Pocket events', 'События Pocket'],
  preserved_staff_access: ['Staff access (preserved)', 'Доступ сотрудника (сохранён)'],
  preserved_manager_audit: ['Manager action log (preserved)', 'Журнал действий менеджеров (сохранён)'],
  custom_presets: ['Custom strategies', 'Пользовательские стратегии'],
  custom_preset_indicators: ['Custom strategy indicators', 'Индикаторы пользовательских стратегий'],
  messages: ['Correspondence', 'Переписка'],
  conversation_memory: ['AI conversation memory', 'Память диалога AI'],
  user_state: ['AI Chatter state', 'Состояние AI Chatter'],
  funnel_media_sent: ['Sent funnel media', 'Отправленные материалы воронки'],
  bot_block_log: ['Bot blocking log', 'История блокировок бота'],
  postback_events: ['Postback events', 'События постбэков'],
  postback_state: ['Postback state', 'Состояние постбэков'],
};

const ARCHIVE_FIELD_LABELS = {
  id: ['Record ID', 'ID записи'],
  user_id: ['Telegram user ID', 'Telegram ID пользователя'],
  tg_user_id: ['Telegram user ID', 'Telegram ID пользователя'],
  chat_id: ['Chat ID', 'ID диалога'],
  preset_id: ['Strategy ID', 'ID стратегии'],
  indicator_id: ['Indicator ID', 'ID индикатора'],
  strategy_id: ['Strategy ID', 'ID стратегии'],
  target_user_id: ['Target user ID', 'Telegram ID клиента'],
  requested_by: ['Requested by', 'Telegram ID менеджера'],
  archived_by: ['Archived by', 'Telegram ID администратора'],
  username: ['Username', 'Имя пользователя'],
  first_name: ['Telegram name', 'Имя в Telegram'],
  profile_name: ['Displayed name', 'Отображаемое имя'],
  title: ['Title', 'Название'],
  name: ['Name', 'Название'],
  avatar_url: ['Avatar URL', 'Ссылка на аватар'],
  trader_id: ['Trader ID', 'Trader ID'],
  profile_trader_id: ['Manual Trader ID', 'Trader ID, указанный вручную'],
  profile_edit_allowed: ['Profile editing allowed', 'Разрешено редактирование профиля'],
  profile_updated_at: ['Profile updated', 'Профиль изменён'],
  pocket_click_id: ['Pocket Click ID', 'Pocket Click ID'],
  pocket_site_id: ['Pocket Site ID', 'Pocket Site ID'],
  pocket_cid: ['Pocket CID', 'Pocket CID'],
  pocket_sub_id1: ['Pocket Sub ID 1', 'Pocket Sub ID 1'],
  pocket_sub_id2: ['Pocket Sub ID 2', 'Pocket Sub ID 2'],
  pocket_sub_id3: ['Pocket Sub ID 3 (Chatterfy)', 'Pocket Sub ID 3 (Chatterfy)'],
  pocket_registered: ['Pocket registration', 'Регистрация в Pocket'],
  pocket_deposited: ['Pocket deposit', 'Депозит в Pocket'],
  pocket_registered_at: ['Pocket registration date', 'Дата регистрации в Pocket'],
  pocket_deposit_amount: ['Pocket deposit amount', 'Сумма депозита Pocket'],
  pocket_checked_at: ['Pocket check date', 'Дата проверки Pocket'],
  pocket_trader_id: ['Pocket Trader ID', 'Trader ID от Pocket'],
  aio_visit_uuid: ['AIO visit ID', 'ID визита AIO'],
  chatterfy_lead_id: ['Chatterfy lead ID', 'ID лида Chatterfy'],
  event_slug: ['Event type', 'Тип события'],
  event_code: ['Event code', 'Код события'],
  unique_key: ['Unique event key', 'Уникальный ключ события'],
  source_unique_key: ['Source event key', 'Ключ события источника'],
  provider_event_id: ['Provider event ID', 'ID события провайдера'],
  payload_fingerprint: ['Payload fingerprint', 'Отпечаток данных'],
  request_url: ['Request URL', 'Адрес запроса'],
  chatterfy_request_url: ['Chatterfy request URL', 'Адрес запроса Chatterfy'],
  status: ['Status', 'Статус'],
  reason: ['Reason', 'Причина'],
  response_status: ['Response status', 'Код ответа'],
  response_body: ['Response body', 'Ответ сервиса'],
  error: ['Error', 'Ошибка'],
  chatterfy_status: ['Chatterfy status', 'Статус Chatterfy'],
  chatterfy_response_status: ['Chatterfy response code', 'Код ответа Chatterfy'],
  chatterfy_response_body: ['Chatterfy response', 'Ответ Chatterfy'],
  chatterfy_error: ['Chatterfy error', 'Ошибка Chatterfy'],
  chatterfy_sent_at: ['Sent to Chatterfy', 'Отправлено в Chatterfy'],
  aichatter_status: ['AI Chatter status', 'Статус AI Chatter'],
  aichatter_error: ['AI Chatter error', 'Ошибка AI Chatter'],
  aichatter_synced_at: ['AI Chatter sync date', 'Дата синхронизации AI Chatter'],
  raw_payload: ['Original data', 'Исходные данные'],
  access: ['System access', 'Доступ к системе'],
  deposit: ['Deposit', 'Депозит'],
  balance: ['Balance', 'Баланс'],
  balance_sync_enabled: ['Balance sync', 'Синхронизация баланса'],
  balance_synced_at: ['Balance sync date', 'Дата синхронизации баланса'],
  balance_sync_error: ['Balance sync error', 'Ошибка синхронизации баланса'],
  country: ['Country', 'Страна'],
  currency: ['Currency', 'Валюта'],
  revenue: ['Revenue', 'Доход'],
  deposit_amount: ['Deposit amount', 'Сумма депозита'],
  sumdep: ['Deposit amount', 'Сумма депозита'],
  wdr_sum: ['Withdrawal amount', 'Сумма вывода'],
  commission: ['Commission', 'Комиссия'],
  mode: ['Trading mode', 'Торговый режим'],
  is_enabled: ['Enabled', 'Включено'],
  override_mode: ['Access override', 'Персональная настройка доступа'],
  is_blocked: ['User blocked', 'Пользователь заблокирован'],
  blocked_by: ['Blocked by', 'Кем заблокирован'],
  blocked_at: ['Blocking date', 'Дата блокировки'],
  lang: ['Language', 'Язык'],
  pair: ['Asset', 'Актив'],
  timeframe: ['Timeframe', 'Таймфрейм'],
  analysis_type: ['Analysis type', 'Тип анализа'],
  market_kind: ['Market type', 'Тип рынка'],
  raw_data: ['Analysis data', 'Данные анализа'],
  news_data: ['News data', 'Новостные данные'],
  entry_price: ['Entry price', 'Цена входа'],
  exit_price: ['Exit price', 'Цена выхода'],
  closed_at: ['Trade closed', 'Сделка закрыта'],
  role: ['Role', 'Роль'],
  content: ['Message', 'Сообщение'],
  direction: ['Message direction', 'Направление сообщения'],
  is_business: ['Business message', 'Сообщение бизнес-аккаунта'],
  text: ['Message text', 'Текст сообщения'],
  message_count: ['Message count', 'Количество сообщений'],
  context_summary: ['Context summary', 'Краткое содержание контекста'],
  memory: ['AI memory', 'Память AI'],
  stage: ['Funnel stage', 'Этап воронки'],
  notes: ['Notes', 'Заметки'],
  current_step: ['Current questionnaire step', 'Текущий этап опросника'],
  quiz_name: ['Questionnaire: name', 'Опросник: имя'],
  quiz_age: ['Questionnaire: age', 'Опросник: возраст'],
  quiz_experience: ['Questionnaire: experience', 'Опросник: опыт'],
  quiz_broker_experience: ['Questionnaire: broker', 'Опросник: опыт с брокером'],
  quiz_capital: ['Questionnaire: capital', 'Опросник: капитал'],
  quiz_completed_at: ['Questionnaire completed', 'Опросник завершён'],
  channel_subscribed_at: ['Channel subscription', 'Подписка на канал'],
  channel_gate_completed_at: ['Channel gate completed', 'Проверка канала пройдена'],
  media_key: ['Media key', 'Ключ материала'],
  delivery_scope: ['Delivery profile', 'Профиль отправки'],
  sent_at: ['Sent date', 'Дата отправки'],
  registration_status: ['Registration status', 'Статус регистрации'],
  deposit_status: ['Deposit status', 'Статус депозита'],
  registered_at: ['Registration date', 'Дата регистрации'],
  bot_active: ['AI Chatter active', 'AI Chatter включён'],
  elizabeth_bot_active: ['Elizabeth Bot active', 'Elizabeth Bot включён'],
  bot_blocked_at: ['Bot blocking date', 'Дата блокировки бота'],
  bot_block_reason: ['Bot blocking reason', 'Причина блокировки бота'],
  first_deposit_sum: ['First deposit', 'Первый депозит'],
  first_deposit_at: ['First deposit date', 'Дата первого депозита'],
  repeat_deposit_last_sum: ['Last repeat deposit', 'Последний повторный депозит'],
  repeat_deposit_total: ['Repeat deposits total', 'Сумма повторных депозитов'],
  repeat_deposit_count: ['Repeat deposit count', 'Количество повторных депозитов'],
  repeat_deposit_at: ['Repeat deposit date', 'Дата повторного депозита'],
  deposit_total: ['Total deposits', 'Общая сумма депозитов'],
  withdrawal_last_sum: ['Last withdrawal', 'Последний вывод'],
  withdrawal_total: ['Total withdrawals', 'Общая сумма выводов'],
  withdrawal_count: ['Withdrawal count', 'Количество выводов'],
  withdrawal_status: ['Withdrawal status', 'Статус вывода'],
  withdrawal_at: ['Withdrawal date', 'Дата вывода'],
  commission_last_amount: ['Last commission', 'Последняя комиссия'],
  commission_total: ['Total commission', 'Общая комиссия'],
  commission_count: ['Commission count', 'Количество комиссий'],
  commission_at: ['Commission date', 'Дата комиссии'],
  registration_received_at: ['Registration postback date', 'Дата постбэка регистрации'],
  last_event_code: ['Last event', 'Последнее событие'],
  last_event_at: ['Last event date', 'Дата последнего события'],
  site_id: ['Site ID', 'Site ID'],
  cid: ['Campaign ID', 'ID кампании'],
  click_id: ['Click ID', 'Click ID'],
  ac: ['Affiliate code', 'Код партнёра'],
  promo: ['Promo code', 'Промокод'],
  device_type: ['Device type', 'Тип устройства'],
  source_ip: ['Source IP', 'IP источника'],
  created_at: ['Created', 'Дата создания'],
  updated_at: ['Updated', 'Дата изменения'],
};

const getArchiveTableLabel = (tableName, tr) => {
  const labels = ARCHIVE_TABLE_LABELS[tableName];
  return labels ? tr(labels[0], labels[1]) : tr(`Technical section: ${tableName}`, `Технический раздел: ${tableName}`);
};

const getArchiveFieldLabel = (fieldName, tr) => {
  const labels = ARCHIVE_FIELD_LABELS[fieldName];
  return labels ? tr(labels[0], labels[1]) : tr(`Field “${fieldName}”`, `Поле «${fieldName}»`);
};

const formatArchiveValue = (fieldName, value, tr) => {
  if (value === null || value === undefined || value === '') return tr('Not specified', 'Не указано');
  if (typeof value === 'boolean') return value ? tr('Yes', 'Да') : tr('No', 'Нет');
  if (
    [
      'access', 'is_enabled', 'is_blocked', 'is_business', 'profile_edit_allowed',
      'balance_sync_enabled', 'pocket_registered', 'pocket_deposited', 'bot_active',
      'elizabeth_bot_active',
    ].includes(fieldName)
    && (Number(value) === 0 || Number(value) === 1)
  ) {
    return Number(value) === 1 ? tr('Yes', 'Да') : tr('No', 'Нет');
  }
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
};

const formatArchiveRows = (rows, tr) => rows.map((row, index) => {
  const fields = Object.entries(row || {}).map(([fieldName, value]) => (
    `${getArchiveFieldLabel(fieldName, tr)}: ${formatArchiveValue(fieldName, value, tr)}`
  ));
  return `${tr('Record', 'Запись')} ${index + 1}\n${fields.join('\n')}`;
}).join('\n\n────────────────────\n\n');

const getArchiveProfile = (snapshot = {}) => {
  const identity = snapshot.identity || {};
  const mainUser = snapshot.main_app?.users?.[0] || {};
  const chatterUser = snapshot.ai_chatter?.users?.[0] || {};
  const profileTraderId = mainUser.profile_trader_id || '';
  const pocketTraderId = mainUser.trader_id || chatterUser.trader_id || '';
  return {
    name: mainUser.profile_name
      || identity.display_name
      || mainUser.first_name
      || chatterUser.first_name
      || '',
    username: identity.username || mainUser.username || chatterUser.username || '',
    userId: identity.user_id || mainUser.user_id || chatterUser.tg_user_id || '',
    traderId: identity.trader_id || profileTraderId || pocketTraderId || '',
    pocketTraderId: profileTraderId && pocketTraderId && profileTraderId !== pocketTraderId
      ? pocketTraderId
      : '',
    balance: mainUser.balance,
    deposit: mainUser.pocket_deposit_amount ?? mainUser.deposit,
    country: mainUser.country || chatterUser.country || '',
    registrationStatus: chatterUser.registration_status
      || (Number(mainUser.pocket_registered) === 1 ? 'registered' : ''),
    depositStatus: chatterUser.deposit_status
      || (Number(mainUser.pocket_deposited) === 1 ? 'deposited' : ''),
  };
};

const getArchiveStatusLabel = (status, tr) => {
  const normalized = String(status || '').trim().toLowerCase();
  const labels = {
    complete: ['Complete', 'Завершён'],
    partial: ['Partially complete', 'Завершён частично'],
    pending: ['Creating', 'Создаётся'],
    registered: ['Registered', 'Зарегистрирован'],
    not_registered: ['Not registered', 'Не зарегистрирован'],
    deposited: ['Deposit received', 'Депозит получен'],
    not_deposited: ['No deposit', 'Депозита нет'],
    processed: ['Processed', 'Обработано'],
    sent: ['Sent', 'Отправлено'],
    active: ['Active', 'Активен'],
    archived: ['Archived', 'В архиве'],
  };
  return labels[normalized]
    ? tr(labels[normalized][0], labels[normalized][1])
    : (status || tr('Not specified', 'Не указано'));
};

const formatArchiveMoney = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  return formatBalance(value);
};

export default function UsersPage({ adminUser }) {
  const { tr } = useAdminLocale();
  const canProfileEdit = hasPermission(adminUser, PERMISSIONS.usersProfileEdit);
  const canArchiveClear = hasPermission(adminUser, PERMISSIONS.usersArchiveClear);
  const canEditAccess = hasPermission(adminUser, PERMISSIONS.usersAccess);
  const canEditBalance = hasPermission(adminUser, PERMISSIONS.usersBalance);
  const canBlock = hasPermission(adminUser, PERMISSIONS.usersBlock);
  const canDelete = hasPermission(adminUser, PERMISSIONS.usersDelete);
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
  const [pocketDetails, setPocketDetails] = useState(null);
  const [pocketLoading, setPocketLoading] = useState(false);
  const [pocketError, setPocketError] = useState('');
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

  const loadPocketDetails = useCallback(async (userId) => {
    if (!userId) return;
    setPocketLoading(true);
    setPocketError('');
    try {
      const res = await apiAdminFetchJson(
        `/api/admin/users/${encodeURIComponent(userId)}/pocket`
      );
      setPocketDetails({
        pocket: res.pocket || {},
        postbacks: res.postbacks || [],
      });
    } catch (e) {
      setPocketDetails(null);
      setPocketError(e.message || tr('Could not load Pocket data', 'Не удалось загрузить данные Pocket'));
    } finally {
      setPocketLoading(false);
    }
  }, [tr]);

  useEffect(() => {
    const timer = window.setTimeout(() => loadUsers(''), 0);
    return () => window.clearTimeout(timer);
  }, [loadUsers]);

  useEffect(() => {
    if (!selectedUserId || !canArchiveClear) return undefined;
    const timer = window.setTimeout(() => loadArchives(selectedUserId), 0);
    return () => window.clearTimeout(timer);
  }, [canArchiveClear, loadArchives, selectedUserId]);

  useEffect(() => {
    if (!selectedUserId) return undefined;
    const timer = window.setTimeout(() => loadPocketDetails(selectedUserId), 0);
    return () => window.clearTimeout(timer);
  }, [loadPocketDetails, selectedUserId]);

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
    setPocketDetails(null);
    setPocketError('');
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
    setPocketDetails(null);
    setPocketError('');
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
      await loadPocketDetails(selectedUser.user_id);
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
    const archiveProfile = getArchiveProfile(archiveSnapshot);
    const pocket = pocketDetails?.pocket || {};
    const pocketPostbacks = pocketDetails?.postbacks || [];
    const latestPocketPostback = pocketPostbacks[0] || null;
    const telegramChatId = pocket.user_id || selectedUser.user_id || '';
    const chatterfyChatId = pocket.chatterfy_lead_id || pocket.pocket_sub_id3 || '';
    const trackerClickId = pocket.pocket_sub_id2 || pocket.aio_visit_uuid || '';
    const chatterfyLinked = Boolean(chatterfyChatId);
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

          <section className="admin-user-pocket-panel">
            <div className="admin-user-pocket-head">
              <div>
                <span className="admin-user-profile-permission-kicker">Affiliate tracking</span>
                <strong>Pocket Option</strong>
                <p>
                  {tr(
                    'Registration, deposits and tracking identifiers received from Pocket postbacks.',
                    'Регистрация, депозиты и идентификаторы, полученные из postback Pocket.'
                  )}
                </p>
              </div>
              {!pocketLoading && !pocketError ? (
                <div className="admin-user-pocket-statuses">
                  <span className={Number(pocket.pocket_registered) === 1 ? 'is-success' : 'is-muted'}>
                    {Number(pocket.pocket_registered) === 1
                      ? tr('Registered', 'Регистрация есть')
                      : tr('Not registered', 'Нет регистрации')}
                  </span>
                  <span className={Number(pocket.pocket_deposited) === 1 ? 'is-success' : 'is-muted'}>
                    {Number(pocket.pocket_deposited) === 1
                      ? tr('Deposit received', 'Депозит получен')
                      : tr('No deposit', 'Депозита нет')}
                  </span>
                </div>
              ) : null}
            </div>

            {pocketLoading ? (
              <div className="admin-user-pocket-message">{tr('Loading Pocket data…', 'Загружаем данные Pocket…')}</div>
            ) : null}
            {pocketError ? <div className="admin-error">{pocketError}</div> : null}

            {!pocketLoading && !pocketError ? (
              <>
                <div className="admin-user-pocket-summary">
                  <div>
                    <span>{tr('Pocket Trader ID', 'Trader ID от Pocket')}</span>
                    <strong>{formatPocketValue(pocket.trader_id || selectedUser.pocket_trader_id)}</strong>
                  </div>
                  <div>
                    <span>{tr('Total deposits', 'Сумма депозитов')}</span>
                    <strong>{formatBalance(pocket.pocket_deposit_amount)}</strong>
                  </div>
                  <div>
                    <span>{tr('Registration date', 'Дата регистрации')}</span>
                    <strong>{formatArchiveDate(pocket.pocket_registered_at)}</strong>
                  </div>
                  <div>
                    <span>{tr('Country', 'Страна')}</span>
                    <strong>{formatPocketValue(pocket.country)}</strong>
                  </div>
                  <div>
                    <span>{tr('Last Pocket event', 'Последнее событие Pocket')}</span>
                    <strong>{latestPocketPostback ? getPocketEventLabel(latestPocketPostback.event_slug, tr) : '—'}</strong>
                  </div>
                  <div>
                    <span>{tr('Event received', 'Событие получено')}</span>
                    <strong>{latestPocketPostback ? formatArchiveDate(latestPocketPostback.created_at) : '—'}</strong>
                  </div>
                </div>

                <details className="admin-user-pocket-details">
                  <summary>{tr('Technical identifiers', 'Технические идентификаторы')}</summary>
                  <div className="admin-user-pocket-technical">
                    <div><span>Click ID</span><code>{formatPocketValue(pocket.pocket_click_id || pocket.user_id)}</code></div>
                    <div><span>Site ID</span><code>{formatPocketValue(pocket.pocket_site_id)}</code></div>
                    <div><span>CID</span><code>{formatPocketValue(pocket.pocket_cid)}</code></div>
                    <div><span>Sub ID 1</span><code>{formatPocketValue(pocket.pocket_sub_id1)}</code></div>
                    <div><span>Sub ID 2 · Chatterfy tracker</span><code>{formatPocketValue(pocket.pocket_sub_id2 || pocket.aio_visit_uuid)}</code></div>
                    <div><span>Sub ID 3 · Chatterfy</span><code>{formatPocketValue(pocket.pocket_sub_id3 || pocket.chatterfy_lead_id)}</code></div>
                    <div><span>AIO visit UUID</span><code>{formatPocketValue(pocket.aio_visit_uuid)}</code></div>
                    <div><span>Chatterfy lead ID</span><code>{formatPocketValue(pocket.chatterfy_lead_id)}</code></div>
                    <div><span>{tr('Last Pocket check', 'Последняя проверка Pocket')}</span><code>{formatArchiveDate(pocket.pocket_checked_at)}</code></div>
                  </div>
                </details>

                <details className="admin-user-pocket-details">
                  <summary>
                    {tr('Pocket postback history', 'История postback Pocket')} · {pocketPostbacks.length}
                  </summary>
                  {pocketPostbacks.length ? (
                    <div className="admin-user-pocket-events">
                      {pocketPostbacks.map((event) => (
                        <article key={event.id} className="admin-user-pocket-event">
                          <div>
                            <strong>{getPocketEventLabel(event.event_slug, tr)}</strong>
                            <span>{formatArchiveDate(event.created_at)}</span>
                          </div>
                          <div className="admin-user-pocket-event-meta">
                            <span>{tr('Pocket status', 'Статус Pocket')}: <b>{formatPocketValue(event.status)}</b></span>
                            <span>{tr('Amount', 'Сумма')}: <b>{formatBalance(event.deposit_amount)}</b></span>
                            <span>AI Chatter: <b>{formatPocketValue(event.aichatter_status)}</b></span>
                            <span>Chatterfy: <b>{formatPocketValue(event.chatterfy_status)}</b></span>
                          </div>
                          {event.reason || event.aichatter_error || event.chatterfy_error ? (
                            <p>{event.reason || event.aichatter_error || event.chatterfy_error}</p>
                          ) : null}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="admin-user-pocket-message">
                      {tr('No Pocket postbacks have been received yet.', 'Postback-события Pocket ещё не получены.')}
                    </div>
                  )}
                </details>
              </>
            ) : null}
          </section>

          <section className={`admin-user-chatterfy-panel ${chatterfyLinked ? 'is-linked' : ''}`}>
            <div className="admin-user-chatterfy-head">
              <div>
                <span className="admin-user-profile-permission-kicker">Webhook identity</span>
                <strong>Chatterfy</strong>
                <p>
                  {tr(
                    'Identifiers received from the Chatterfy flow and used to build the personal registration URL.',
                    'Идентификаторы из воронки Chatterfy, которые используются при сборке персональной ссылки регистрации.'
                  )}
                </p>
              </div>
              <span className={`admin-user-chatterfy-state ${chatterfyLinked ? 'is-success' : 'is-pending'}`}>
                {chatterfyLinked
                  ? tr('Webhook linked', 'Webhook привязан')
                  : tr('Waiting for webhook', 'Ожидается webhook')}
              </span>
            </div>

            {pocketLoading ? (
              <div className="admin-user-pocket-message">{tr('Loading Chatterfy data…', 'Загружаем данные Chatterfy…')}</div>
            ) : null}
            {pocketError ? <div className="admin-error">{pocketError}</div> : null}

            {!pocketLoading && !pocketError ? (
              <>
                <div className="admin-user-chatterfy-grid">
                  <div>
                    <span>Telegram Chat ID <code>{'{chatId}'}</code></span>
                    <strong>{formatPocketValue(telegramChatId)}</strong>
                    <small>click_id</small>
                  </div>
                  <div>
                    <span>Chatterfy Chat ID <code>{'{id}'}</code></span>
                    <strong>{formatPocketValue(chatterfyChatId)}</strong>
                    <small>sub_id3</small>
                  </div>
                  <div>
                    <span>Tracker Click ID <code>{'{tracker.clickid}'}</code></span>
                    <strong>{formatPocketValue(trackerClickId)}</strong>
                    <small>sub_id2</small>
                  </div>
                </div>

                <div className="admin-user-chatterfy-map">
                  <span>{tr('Registration link mapping', 'Подстановка в ссылку регистрации')}</span>
                  <code>click_id ← {'{chatId}'}</code>
                  <code>sub_id2 ← {'{tracker.clickid}'}</code>
                  <code>sub_id3 ← {'{id}'}</code>
                </div>

                {!chatterfyLinked ? (
                  <p className="admin-user-chatterfy-hint">
                    {tr(
                      'The Telegram ID is known, but Chatterfy has not sent its internal chat ID yet. The value will appear automatically after the webhook runs.',
                      'Telegram ID уже известен, но Chatterfy ещё не передал внутренний ID чата. Значение появится автоматически после срабатывания webhook.'
                    )}
                  </p>
                ) : null}
              </>
            ) : null}
          </section>

          {canProfileEdit ? (
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
          ) : null}

          {canArchiveClear ? (
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
          ) : null}

          {(canEditAccess || canEditBalance || canBlock || canDelete) ? (
          <div className="admin-user-actions">
            <div className="admin-row-actions">
              {canEditAccess ? <button className="admin-btn-outline" onClick={openAccessModal} disabled={actionLoading}>
                {tr('Edit access', 'Редактировать доступ')}
              </button> : null}
              {canEditBalance ? <button className="admin-btn-outline" onClick={openBalanceModal} disabled={actionLoading}>
                {tr('Edit balance', 'Изменить баланс')}
              </button> : null}
            </div>
            {canBlock ? (
            <button
              className={isBlocked ? 'admin-btn' : 'admin-btn-outline danger'}
              onClick={() => toggleBlocked(selectedUser)}
              disabled={actionLoading}
            >
              {isBlocked ? tr('Unblock', 'Разблокировать') : tr('Block', 'Заблокировать')}
            </button>
            ) : null}
            {canDelete ? <button className="admin-btn-outline danger" onClick={deleteUser} disabled={actionLoading}>
              {tr('Delete user', 'Удалить пользователя')}
            </button> : null}
            {canBlock ? <div className="admin-muted">
              {tr(
                'A blocked user will see a restriction screen when opening the application.',
                'Заблокированный пользователь увидит экран ограничения при входе в приложение.'
              )}
            </div> : null}
          </div>
          ) : null}
        </div>

        {status ? <div className="admin-success">{status}</div> : null}
        {error ? <div className="admin-error">{error}</div> : null}

        {accessModalOpen && canEditAccess ? (
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

        {balanceModalOpen && canEditBalance ? (
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

        {clearCacheModalOpen && canArchiveClear ? (
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

        {archiveModalOpen && canArchiveClear ? (
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
                      <strong>{getArchiveStatusLabel(archiveDetail.archive_status, tr)}</strong>
                    </div>
                  </div>

                  <section className="admin-archive-profile-card">
                    <div className="admin-archive-profile-head">
                      <div>
                        <span>{tr('Snapshot at the time of clearing', 'Данные на момент очистки')}</span>
                        <h4>{archiveProfile.name || tr('Name not specified', 'Имя не указано')}</h4>
                      </div>
                      <b>#{archiveDetail.id}</b>
                    </div>
                    <div className="admin-archive-profile-grid">
                      <div>
                        <span>{tr('Username', 'Имя пользователя')}</span>
                        <strong>
                          {archiveProfile.username
                            ? `@${String(archiveProfile.username).replace(/^@/, '')}`
                            : '—'}
                        </strong>
                      </div>
                      <div>
                        <span>Telegram ID</span>
                        <strong>{archiveProfile.userId || archiveDetail.user_id || '—'}</strong>
                      </div>
                      <div>
                        <span>Trader ID</span>
                        <strong>{archiveProfile.traderId || '—'}</strong>
                      </div>
                      {archiveProfile.pocketTraderId ? (
                        <div>
                          <span>{tr('Pocket Trader ID', 'Trader ID от Pocket')}</span>
                          <strong>{archiveProfile.pocketTraderId}</strong>
                        </div>
                      ) : null}
                      <div className="is-accent">
                        <span>{tr('Balance', 'Баланс')}</span>
                        <strong>{formatArchiveMoney(archiveProfile.balance)}</strong>
                      </div>
                      <div>
                        <span>{tr('Deposit amount', 'Сумма депозита')}</span>
                        <strong>{formatArchiveMoney(archiveProfile.deposit)}</strong>
                      </div>
                      <div>
                        <span>{tr('Country', 'Страна')}</span>
                        <strong>{archiveProfile.country || '—'}</strong>
                      </div>
                      <div>
                        <span>{tr('Registration', 'Регистрация')}</span>
                        <strong>{getArchiveStatusLabel(archiveProfile.registrationStatus, tr)}</strong>
                      </div>
                      <div>
                        <span>{tr('Deposit status', 'Статус депозита')}</span>
                        <strong>{getArchiveStatusLabel(archiveProfile.depositStatus, tr)}</strong>
                      </div>
                    </div>
                  </section>

                  {['main_app', 'ai_chatter'].map((sectionName) => (
                    <section className="admin-archive-section" key={sectionName}>
                      <div className="admin-row-between">
                        <h4>
                          {sectionName === 'main_app'
                            ? tr('Elizabeth application', 'Приложение Elizabeth')
                            : tr('AI Chatter', 'AI Chatter')}
                        </h4>
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
                                <span>
                                  {getArchiveTableLabel(tableName, tr)}
                                  <small>{tableName}</small>
                                </span>
                                <b>{normalizedRows.length}</b>
                              </summary>
                              <pre>
                                {formatArchiveRows(normalizedRows.slice(0, 25), tr)}
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
                        <small>
                          {archive.summary?.display_name || tr('Name not specified', 'Имя не указано')}
                          {archive.summary?.username
                            ? ` · @${String(archive.summary.username).replace(/^@/, '')}`
                            : ''}
                        </small>
                        {archive.summary?.trader_id ? (
                          <small>Trader ID: {archive.summary.trader_id}</small>
                        ) : null}
                      </span>
                      <span className="admin-archive-row-meta">
                        <b>{archive.summary?.total_records || 0}</b>
                        <small>{tr('records', 'записей')}</small>
                      </span>
                      <span className={`admin-archive-status is-${archive.archive_status}`}>
                        {getArchiveStatusLabel(archive.archive_status, tr)}
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

