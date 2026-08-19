import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
const formatArchiveDate = (value, locale = 'ru-RU') => {
  if (!value) return '—';
  const normalized = String(value).includes('T') ? String(value) : String(value).replace(' ', 'T');
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat(locale, {
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
const formatPercent = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `${parsed.toFixed(1)}%` : '—';
};
const formatCount = (value) => new Intl.NumberFormat('ru-RU').format(Number(value || 0));
const getOnboardingProgress = (onboarding) => {
  if (!onboarding) return 0;
  if (onboarding.channel_gate_completed_at) return 100;
  if (onboarding.channel_subscribed_at) return 80;
  if (onboarding.quiz_completed_at) return 60;
  if (onboarding.current_step) return 25;
  return 0;
};
const getAnalysisStatusLabel = (status, tr) => {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'success') return tr('Win', 'Успешно');
  if (normalized === 'fail') return tr('Loss', 'Убыток');
  if (normalized === 'active') return tr('Active', 'Активен');
  if (normalized === 'skipped') return tr('Skipped', 'Пропущен');
  return status || '—';
};
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
  aio_inbound_postbacks: ['Inbound AIO conversions', 'Входящие конверсии AIO'],
  pocket_postback_events: ['Pocket events', 'События Pocket'],
  chatterfy_access_events: ['Chatterfy access events', 'События доступа Chatterfy'],
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
  aio_country_code: ['AIO country code', 'Код страны AIO'],
  pocket_country_code: ['Pocket country code', 'Код страны Pocket'],
  aio_status_fields_visit_uuid: ['AIO status visit ID', 'ID визита для статусов AIO'],
  aio_dep_ok_synced_value: ['AIO deposit flag', 'Переданный флаг депозита AIO'],
  aio_vip_synced_value: ['AIO VIP flag', 'Переданный флаг VIP AIO'],
  aio_copy_synced_value: ['AIO Copy flag', 'Переданный флаг Copy AIO'],
  conversion_type_uuid: ['Conversion type UUID', 'UUID типа конверсии'],
  country_code: ['Country code', 'Код страны'],
  chatterfy_lead_id: ['Chatterfy lead ID', 'ID лида Chatterfy'],
  chatterfy_bot_lead_id: ['Chatterfy Bot chat ID', 'ID чата Chatterfy Bot'],
  chatterfy_bot_channel_subscribed_at: ['Chatterfy channel subscription', 'Подписка на канал из Chatterfy'],
  chatterfy_vip_granted_at: ['Chatterfy VIP granted', 'VIP выдан через Chatterfy'],
  chatterfy_copy_granted_at: ['Chatterfy Copy granted', 'Copy выдан через Chatterfy'],
  chatterfy_tracker_click_id: ['Chatterfy tracker click ID', 'Tracker Click ID Chatterfy'],
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
  received_at: ['Received date', 'Дата получения'],
  applied_at: ['Applied date', 'Дата применения'],
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
      'elizabeth_bot_active', 'aio_dep_ok_synced_value', 'aio_vip_synced_value',
      'aio_copy_synced_value',
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
    aioCountry: mainUser.aio_country_code || '',
    pocketCountry: mainUser.pocket_country_code || mainUser.country || '',
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
  const { locale, tr } = useAdminLocale();
  const formatAdminDate = (value) => formatArchiveDate(value, locale);
  const canProfileEdit = hasPermission(adminUser, PERMISSIONS.usersProfileEdit);
  const canArchiveClear = hasPermission(adminUser, PERMISSIONS.usersArchiveClear);
  const canEditAccess = hasPermission(adminUser, PERMISSIONS.usersAccess);
  const canEditBalance = hasPermission(adminUser, PERMISSIONS.usersBalance);
  const canBlock = hasPermission(adminUser, PERMISSIONS.usersBlock);
  const canDelete = hasPermission(adminUser, PERMISSIONS.usersDelete);
  const [search, setSearch] = useState('');
  const [pocketStatus, setPocketStatus] = useState('all');
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
  const [profileDetails, setProfileDetails] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState('');
  const [profileTab, setProfileTab] = useState('overview');
  const [confirmationPhrase, setConfirmationPhrase] = useState('');
  const [confirmationValue, setConfirmationValue] = useState('');
  const [accessForm, setAccessForm] = useState({ forex: true, binary: true });
  const [balanceForm, setBalanceForm] = useState({ balance: '0.00', sync: false });
  const initialLoadStarted = useRef(false);

  const loadUsers = useCallback(async (currentSearch = '', currentPocketStatus = 'all') => {
    setLoading(true);
    setError('');
    try {
      const query = new URLSearchParams({
        limit: '100',
        offset: '0',
        search: currentSearch.trim(),
        pocket_status: currentPocketStatus,
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

  const loadProfileDetails = useCallback(async (userId) => {
    if (!userId) return;
    setProfileLoading(true);
    setProfileError('');
    try {
      const res = await apiAdminFetchJson(
        `/api/admin/users/${encodeURIComponent(userId)}/profile`
      );
      setProfileDetails({
        user: res.user || null,
        onboarding: res.onboarding || null,
        activity: res.activity || {},
        aiChatter: res.ai_chatter || { available: false, exists: false },
        pocket: res.pocket || {},
        depositAccess: res.deposit_access || {},
        postbacks: res.postbacks || [],
        aioInboundPostbacks: res.aio_inbound_postbacks || [],
        aioOutboundEvents: res.aio_outbound_events || [],
      });
      if (res.user?.user_id) {
        setUsers((prev) => prev.map((item) => (
          String(item.user_id) === String(res.user.user_id) ? { ...item, ...res.user } : item
        )));
      }
    } catch (e) {
      setProfileDetails(null);
      setProfileError(e.message || tr('Could not load the user profile', 'Не удалось загрузить профиль пользователя'));
    } finally {
      setProfileLoading(false);
    }
  }, [tr]);

  useEffect(() => {
    if (initialLoadStarted.current) return undefined;
    initialLoadStarted.current = true;
    const timer = window.setTimeout(() => loadUsers('', 'all'), 0);
    return () => window.clearTimeout(timer);
  }, [loadUsers]);

  useEffect(() => {
    if (!selectedUserId || !canArchiveClear) return undefined;
    const timer = window.setTimeout(() => loadArchives(selectedUserId), 0);
    return () => window.clearTimeout(timer);
  }, [canArchiveClear, loadArchives, selectedUserId]);

  useEffect(() => {
    if (!selectedUserId) return undefined;
    const timer = window.setTimeout(() => loadProfileDetails(selectedUserId), 0);
    return () => window.clearTimeout(timer);
  }, [loadProfileDetails, selectedUserId]);

  const selectedUser = useMemo(
    () => users.find((user) => String(user.user_id) === String(selectedUserId)) || null,
    [users, selectedUserId]
  );

  const isBlocked = selectedUser ? Number(selectedUser.is_blocked) === 1 : false;

  const onSubmit = (e) => {
    e.preventDefault();
    loadUsers(search, pocketStatus);
  };

  const applyPocketStatus = (nextStatus) => {
    if (nextStatus === pocketStatus || loading) return;
    setPocketStatus(nextStatus);
    loadUsers(search, nextStatus);
  };

  const openUserCard = (userId) => {
    setSelectedUserId(userId);
    setStatus('');
    setError('');
    setArchiveDetail(null);
    setArchives([]);
    setConfirmationPhrase('');
    setProfileDetails(null);
    setProfileError('');
    setProfileTab('overview');
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
    setProfileDetails(null);
    setProfileError('');
    setProfileTab('overview');
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
      await loadProfileDetails(selectedUser.user_id);
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
    const pocket = profileDetails?.pocket || {};
    const pocketPostbacks = profileDetails?.postbacks || [];
    const depositAccess = profileDetails?.depositAccess || {};
    const aioInboundPostbacks = profileDetails?.aioInboundPostbacks || [];
    const aioOutboundEvents = profileDetails?.aioOutboundEvents || [];
    const latestAioInbound = aioInboundPostbacks[0] || null;
    const latestAioOutbound = aioOutboundEvents[0] || null;
    const aioLinked = Boolean(pocket.aio_visit_uuid);
    const aioGeoReceived = Boolean(pocket.aio_country_code || latestAioInbound?.country_code);
    const latestPocketPostback = pocketPostbacks[0] || null;
    const registrationConfirmed = Number(
      pocket.pocket_registered ?? selectedUser.pocket_registered ?? 0
    ) === 1;
    const depositConfirmed = Number(
      pocket.pocket_deposited ?? selectedUser.pocket_deposited ?? 0
    ) === 1;
    const telegramChatId = pocket.user_id || selectedUser.user_id || '';
    const chatterfyChatId = pocket.chatterfy_lead_id || '';
    const chatterfyBotChatId = pocket.chatterfy_bot_lead_id || '';
    const chatterfyChannelSubscribedAt = pocket.chatterfy_bot_channel_subscribed_at || '';
    const chatterfyChannelSubscribed = Boolean(chatterfyChannelSubscribedAt);
    const chatterfyVipGrantedAt = pocket.chatterfy_vip_granted_at || selectedUser.chatterfy_vip_granted_at || '';
    const chatterfyCopyGrantedAt = pocket.chatterfy_copy_granted_at || selectedUser.chatterfy_copy_granted_at || '';
    const chatterfyVipGranted = Boolean(chatterfyVipGrantedAt);
    const chatterfyCopyGranted = Boolean(chatterfyCopyGrantedAt);
    const trackerClickId = pocket.chatterfy_tracker_click_id || '';
    const chatterfyLinked = Boolean(chatterfyChatId || chatterfyBotChatId);
    const onboarding = profileDetails?.onboarding || null;
    const activity = profileDetails?.activity || {};
    const aiChatter = profileDetails?.aiChatter || { available: true, exists: false };
    const onboardingProgress = getOnboardingProgress(onboarding);
    const completedDeals = Number(activity.completed_deals || 0);
    const profileTabs = [
      { id: 'overview', label: tr('Overview', 'Обзор') },
      { id: 'integrations', label: tr('Integrations', 'Интеграции') },
      { id: 'management', label: tr('Management', 'Управление') },
      { id: 'data', label: tr('Data & history', 'Данные и история') },
    ];
    return (
      <div className="admin-card admin-user-profile-card">
        <button className="admin-user-profile-back" onClick={closeUserCard}>
          <span aria-hidden="true">←</span>
          {tr('All users', 'Все пользователи')}
        </button>

        <header className="admin-user-profile-hero">
          <div className="admin-user-profile-identity">
            <div className="admin-user-avatar profile">
              <span>{getInitials(selectedUser)}</span>
              {selectedAvatarUrl ? (
                <img src={selectedAvatarUrl} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
              ) : null}
            </div>
            <div className="admin-user-profile-heading">
              <div className="admin-user-profile-titleline">
                <span className="admin-user-profile-eyebrow">{tr('Customer profile', 'Профиль клиента')} · #{selectedUser.user_id}</span>
                <div className="admin-user-profile-milestones" aria-label={tr('Pocket statuses', 'Статусы Pocket')}>
                  {registrationConfirmed ? (
                    <span className="admin-user-milestone is-registration" title={tr('Pocket registration confirmed', 'Регистрация в Pocket подтверждена')}>
                      <span aria-hidden="true">✅</span>
                      {tr('Registered', 'Регистрация')}
                    </span>
                  ) : null}
                  {depositConfirmed ? (
                    <span className="admin-user-milestone is-deposit" title={tr('Pocket deposit confirmed', 'Депозит в Pocket подтверждён')}>
                      <span aria-hidden="true">💵</span>
                      {tr('Deposit', 'Депозит')}
                    </span>
                  ) : null}
                  {chatterfyVipGranted ? (
                    <span className="admin-user-milestone is-vip" title={tr('VIP granted by Chatterfy', 'VIP выдан через Chatterfy')}>
                      <span aria-hidden="true">◆</span>
                      VIP
                    </span>
                  ) : null}
                  {chatterfyCopyGranted ? (
                    <span className="admin-user-milestone is-copy" title={tr('Copy granted by Chatterfy', 'Copy выдан через Chatterfy')}>
                      <span aria-hidden="true">⇄</span>
                      Copy
                    </span>
                  ) : null}
                </div>
              </div>
              <h2>{getDisplayName(selectedUser)}</h2>
              <div className="admin-user-profile-handle">
                {selectedUser.username
                  ? `@${String(selectedUser.username).replace(/^@/, '')}`
                  : tr('Telegram username is not specified', 'Username Telegram не указан')}
              </div>
              <div className="admin-user-profile-badges">
                <span className={isBlocked ? 'is-danger' : 'is-success'}>
                  {isBlocked ? tr('Blocked', 'Заблокирован') : tr('Active', 'Активен')}
                </span>
                {Number(selectedUser.is_admin) === 1 ? <span className="is-role">{tr('Staff', 'Сотрудник')}</span> : null}
                {chatterfyLinked ? <span className="is-service">Chatterfy</span> : null}
                {manualTraderId ? <span className="is-warning">{tr('Manual Trader ID', 'Ручной Trader ID')}</span> : null}
              </div>
            </div>
          </div>
          <div className="admin-user-profile-quick-actions">
            {canEditAccess ? (
              <button className="admin-btn-outline" onClick={openAccessModal} disabled={actionLoading}>
                {tr('Access', 'Доступ')}
              </button>
            ) : null}
            {canEditBalance ? (
              <button className="admin-btn" onClick={openBalanceModal} disabled={actionLoading}>
                {tr('Balance', 'Баланс')}
              </button>
            ) : null}
          </div>
        </header>

        <div className="admin-user-profile-metrics" aria-label={tr('Key indicators', 'Ключевые показатели')}>
          <div>
            <span>{tr('Balance', 'Баланс')}</span>
            <strong>{formatBalance(selectedUser.balance)}</strong>
            <small>{Number(selectedUser.balance_sync_enabled) === 1 ? tr('Pocket sync enabled', 'Синхронизация включена') : tr('Manual value', 'Ручное значение')}</small>
          </div>
          <div>
            <span>{tr('Deposits', 'Депозиты')}</span>
            <strong>{formatBalance(pocket.pocket_deposit_amount)}</strong>
            <small>{Number(pocket.pocket_deposited) === 1 ? tr('Confirmed', 'Подтверждены') : tr('Not received', 'Не получены')}</small>
          </div>
          <div>
            <span>{tr('Completed deals', 'Завершено сделок')}</span>
            <strong>{formatCount(completedDeals)}</strong>
            <small>{formatCount(activity.deals_7d)} {tr('in 7 days', 'за 7 дней')}</small>
          </div>
          <div>
            <span>{tr('Winrate', 'Винрейт')}</span>
            <strong>{formatPercent(activity.winrate)}</strong>
            <small>{tr('7 days', '7 дней')}: {formatPercent(activity.winrate_7d)}</small>
          </div>
        </div>

        <nav className="admin-user-profile-tabs" aria-label={tr('User profile sections', 'Разделы профиля пользователя')}>
          {profileTabs.map((tab) => (
            <button
              type="button"
              key={tab.id}
              className={profileTab === tab.id ? 'active' : ''}
              onClick={() => setProfileTab(tab.id)}
              aria-current={profileTab === tab.id ? 'page' : undefined}
            >
              {tab.label}
              {tab.id === 'integrations' ? <b>{[aioLinked, chatterfyLinked, Number(pocket.pocket_registered) === 1, aiChatter.exists].filter(Boolean).length}</b> : null}
              {tab.id === 'data' && archives.length ? <b>{archives.length}</b> : null}
            </button>
          ))}
        </nav>

        {profileLoading ? (
          <div className="admin-user-profile-loading">
            <span />
            {tr('Collecting data from connected services…', 'Собираем данные из подключённых сервисов…')}
          </div>
        ) : null}
        {profileError ? <div className="admin-error">{profileError}</div> : null}

        <div className="admin-user-detail">
          {profileTab === 'overview' ? (
            <div className="admin-user-overview">
              <section className="admin-user-profile-section">
                <div className="admin-user-profile-section-head">
                  <div>
                    <span>{tr('Identity', 'Идентификация')}</span>
                    <h3>{tr('Contact and profile', 'Контакты и профиль')}</h3>
                  </div>
                  <small>{tr('Data from Telegram and the app', 'Данные Telegram и приложения')}</small>
                </div>
                <div className="admin-user-profile-fields">
                  <div><span>Telegram ID</span><strong>{selectedUser.user_id}</strong></div>
                  <div><span>Username</span><strong>{selectedUser.username ? `@${String(selectedUser.username).replace(/^@/, '')}` : '—'}</strong></div>
                  <div><span>{tr('Displayed name', 'Отображаемое имя')}</span><strong>{selectedUser.first_name || '—'}</strong></div>
                  <div><span>{tr('Telegram name', 'Имя в Telegram')}</span><strong>{selectedUser.telegram_first_name || '—'}</strong></div>
                  <div><span>{tr('Interface language', 'Язык интерфейса')}</span><strong>{String(selectedUser.lang || '—').toUpperCase()}</strong></div>
                  <div><span>{tr('Created', 'Создан')}</span><strong>{formatAdminDate(selectedUser.created_at)}</strong></div>
                </div>
              </section>

              <section className="admin-user-profile-section">
                <div className="admin-user-profile-section-head">
                  <div>
                    <span>{tr('Trading profile', 'Торговый профиль')}</span>
                    <h3>{tr('Access and preferences', 'Доступ и предпочтения')}</h3>
                  </div>
                </div>
                <div className="admin-user-profile-fields">
                  <div>
                    <span>Trader ID</span>
                    <strong>{selectedUser.trader_id || tr('Not set', 'Не указан')}</strong>
                    {manualTraderId ? <small>{tr('Entered by the user; Pocket verification is disabled', 'Введён пользователем; проверка Pocket отключена')}</small> : null}
                  </div>
                  <div><span>{tr('Mode', 'Режим')}</span><strong>{selectedUser.mode || '—'}</strong></div>
                  <div><span>{tr('Strategy', 'Стратегия')}</span><strong>{selectedUser.strategy_name || selectedUser.strategy_id || '—'}</strong></div>
                  <div><span>Forex</span><strong className={hasAccess(selectedUser.forex_access) ? 'is-positive' : ''}>{hasAccess(selectedUser.forex_access) ? tr('Access granted', 'Доступ есть') : tr('No access', 'Нет доступа')}</strong></div>
                  <div><span>Binary</span><strong className={hasAccess(selectedUser.binary_access) ? 'is-positive' : ''}>{hasAccess(selectedUser.binary_access) ? tr('Access granted', 'Доступ есть') : tr('No access', 'Нет доступа')}</strong></div>
                  <div><span>{tr('Balance sync', 'Синхронизация баланса')}</span><strong>{manualTraderId ? tr('Unavailable', 'Недоступна') : (Number(selectedUser.balance_sync_enabled) === 1 ? tr('Enabled', 'Включена') : tr('Disabled', 'Выключена'))}</strong></div>
                </div>
              </section>

              <section className="admin-user-profile-section admin-user-deposit-access-section">
                <div className="admin-user-profile-section-head">
                  <div>
                    <span>{tr('Country and deposit access', 'Страна и доступ по депозиту')}</span>
                    <h3>{tr('Personal deposit levels', 'Персональные уровни депозитов')}</h3>
                  </div>
                  <small>
                    {depositAccess.source === 'country'
                      ? tr('Country rule', 'Правило страны')
                      : tr('Default fallback', 'Резервные значения')}
                  </small>
                </div>
                <div className="admin-user-profile-fields compact admin-user-geo-fields">
                  <div>
                    <span>{tr('AIO country', 'Страна AIO')}</span>
                    <strong>{formatPocketValue(depositAccess.aio_country_code || pocket.aio_country_code)}</strong>
                    <small>{tr('Selects the deposit rule', 'Определяет правило депозитов')}</small>
                  </div>
                  <div>
                    <span>{tr('Pocket country', 'Страна Pocket')}</span>
                    <strong>{formatPocketValue(depositAccess.pocket_country_code || pocket.pocket_country_code || pocket.country)}</strong>
                    <small>{tr('Stored separately for diagnostics', 'Хранится отдельно для диагностики')}</small>
                  </div>
                  <div>
                    <span>{tr('Effective rule', 'Применённое правило')}</span>
                    <strong>
                      {depositAccess.source === 'country'
                        ? `${depositAccess.country_name || depositAccess.country_code || '—'}${depositAccess.country_name && depositAccess.country_code ? ` · ${depositAccess.country_code}` : ''}`
                        : tr('Default values', 'Значения по умолчанию')}
                    </strong>
                    <small>{tr('Based on AIO GEO', 'На основании GEO AIO')}</small>
                  </div>
                  <div>
                    <span>{tr('Accumulated deposits', 'Накоплено депозитов')}</span>
                    <strong>{formatBalance(depositAccess.deposit_amount ?? pocket.pocket_deposit_amount)}</strong>
                    <small>{tr('FTD + repeat deposits', 'FTD + повторные депозиты')}</small>
                  </div>
                </div>
                <div className="admin-user-deposit-levels">
                  {[
                    {
                      key: 'deposit',
                      title: tr('Minimum deposit', 'Минимальный депозит'),
                      value: depositAccess.min_deposit_amount,
                      enabled: Number(depositAccess.deposit_access || 0) === 1,
                      shortage: depositAccess.shortage,
                    },
                    {
                      key: 'vip',
                      title: 'VIP',
                      value: depositAccess.vip_deposit_amount,
                      enabled: Number(depositAccess.vip_access || 0) === 1,
                      shortage: depositAccess.vip_shortage,
                    },
                    {
                      key: 'copy',
                      title: 'Copy',
                      value: depositAccess.copy_deposit_amount,
                      enabled: Number(depositAccess.copy_access || 0) === 1,
                      shortage: depositAccess.copy_shortage,
                    },
                  ].map((level) => (
                    <div key={level.key} className={level.enabled ? 'is-unlocked' : ''}>
                      <span>{level.title}</span>
                      <strong>{formatBalance(level.value)}</strong>
                      <small>
                        {level.enabled
                          ? tr('Access granted', 'Доступ открыт')
                          : `${tr('Remaining', 'Не хватает')}: ${formatBalance(level.shortage)}`}
                      </small>
                    </div>
                  ))}
                </div>
              </section>

              <section className="admin-user-profile-section admin-user-journey-section">
                <div className="admin-user-profile-section-head">
                  <div>
                    <span>{tr('Customer journey', 'Путь клиента')}</span>
                    <h3>{tr('Questionnaire and funnel', 'Опросник и воронка')}</h3>
                  </div>
                  <b>{onboardingProgress}%</b>
                </div>
                <div className="admin-user-journey-progress" aria-label={`${onboardingProgress}%`}>
                  <span style={{ width: `${onboardingProgress}%` }} />
                </div>
                {onboarding ? (
                  <>
                    <div className="admin-user-journey-steps">
                      <span className={onboarding.current_step ? 'done' : ''}>{tr('Started', 'Начат')}</span>
                      <span className={onboarding.quiz_completed_at ? 'done' : ''}>{tr('Questionnaire', 'Опросник')}</span>
                      <span className={onboarding.channel_subscribed_at ? 'done' : ''}>{tr('Channel', 'Канал')}</span>
                      <span className={onboarding.channel_gate_completed_at ? 'done' : ''}>{tr('Trading', 'Трейдинг')}</span>
                    </div>
                    <div className="admin-user-profile-fields compact">
                      <div><span>{tr('Experience', 'Опыт')}</span><strong>{onboarding.quiz_experience || '—'}</strong></div>
                      <div><span>{tr('Broker experience', 'Опыт с брокером')}</span><strong>{onboarding.quiz_broker_experience || '—'}</strong></div>
                      <div><span>{tr('Capital', 'Капитал')}</span><strong>{onboarding.quiz_capital || '—'}</strong></div>
                      <div><span>{tr('Current step', 'Текущий этап')}</span><strong>{onboarding.current_step || '—'}</strong></div>
                    </div>
                  </>
                ) : (
                  <div className="admin-user-empty-state">
                    <strong>{tr('The funnel has not started', 'Воронка ещё не начата')}</strong>
                    <span>{tr('The profile may have been created by an integration before the user opened the bot.', 'Профиль мог быть создан интеграцией до первого открытия бота.')}</span>
                  </div>
                )}
              </section>

              <section className="admin-user-profile-section">
                <div className="admin-user-profile-section-head">
                  <div>
                    <span>{tr('Usage', 'Активность')}</span>
                    <h3>{tr('Application activity', 'Активность в приложении')}</h3>
                  </div>
                </div>
                <div className="admin-user-activity-grid">
                  <div><strong>{formatCount(activity.analyses_total)}</strong><span>{tr('analyses', 'анализов')}</span></div>
                  <div><strong>{formatCount(activity.analyses_active)}</strong><span>{tr('active', 'активных')}</span></div>
                  <div><strong>{formatCount(activity.chats_count)}</strong><span>{tr('AI chats', 'AI-диалогов')}</span></div>
                  <div><strong>{formatCount(activity.messages_count)}</strong><span>{tr('AI messages', 'AI-сообщений')}</span></div>
                  <div><strong>{formatCount(activity.strategies_count)}</strong><span>{tr('custom strategies', 'своих стратегий')}</span></div>
                </div>
                <div className="admin-user-activity-foot">
                  <span>{tr('Last analysis', 'Последний анализ')}</span>
                  <strong>{formatAdminDate(activity.last_analysis_at)}</strong>
                </div>
              </section>
            </div>
          ) : null}

          {profileTab === 'integrations' ? (
          <>

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
              {!profileLoading && !profileError ? (
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

            {profileLoading ? (
              <div className="admin-user-pocket-message">{tr('Loading Pocket data…', 'Загружаем данные Pocket…')}</div>
            ) : null}
            {!profileLoading && !profileError ? (
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
                    <strong>{formatAdminDate(pocket.pocket_registered_at)}</strong>
                  </div>
                  <div>
                    <span>{tr('Pocket country', 'Страна Pocket')}</span>
                    <strong>{formatPocketValue(pocket.pocket_country_code || pocket.country)}</strong>
                  </div>
                  <div>
                    <span>{tr('Last Pocket event', 'Последнее событие Pocket')}</span>
                    <strong>{latestPocketPostback ? getPocketEventLabel(latestPocketPostback.event_slug, tr) : '—'}</strong>
                  </div>
                  <div>
                    <span>{tr('Event received', 'Событие получено')}</span>
                    <strong>{latestPocketPostback ? formatAdminDate(latestPocketPostback.created_at) : '—'}</strong>
                  </div>
                </div>

                <details className="admin-user-pocket-details">
                  <summary>{tr('Technical identifiers', 'Технические идентификаторы')}</summary>
                  <div className="admin-user-pocket-technical">
                    <div><span>Click ID</span><code>{formatPocketValue(pocket.pocket_click_id || pocket.user_id)}</code></div>
                    <div><span>Site ID</span><code>{formatPocketValue(pocket.pocket_site_id)}</code></div>
                    <div><span>CID</span><code>{formatPocketValue(pocket.pocket_cid)}</code></div>
                    <div><span>Sub ID 1</span><code>{formatPocketValue(pocket.pocket_sub_id1)}</code></div>
                    <div><span>Sub ID 2 · AIO visit</span><code>{formatPocketValue(pocket.pocket_sub_id2)}</code></div>
                    <div><span>Sub ID 3 · Chatterfy</span><code>{formatPocketValue(pocket.pocket_sub_id3)}</code></div>
                    <div><span>{tr('Last Pocket check', 'Последняя проверка Pocket')}</span><code>{formatAdminDate(pocket.pocket_checked_at)}</code></div>
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
                            <span>{formatAdminDate(event.created_at)}</span>
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

          <section className={`admin-user-chatterfy-panel admin-user-aio-panel ${aioGeoReceived ? 'has-data' : ''}`}>
            <div className="admin-user-chatterfy-head">
              <div>
                <span className="admin-user-profile-permission-kicker">Conversion identity</span>
                <strong>AIO</strong>
                <p>
                  {tr(
                    'The AIO visit, country and received conversion type are stored independently from Pocket and Chatterfy.',
                    'Визит AIO, гео и полученный тип конверсии хранятся отдельно от данных Pocket и Chatterfy.'
                  )}
                </p>
              </div>
              <span className={`admin-user-chatterfy-state ${aioGeoReceived ? 'is-success' : 'is-pending'}`}>
                {aioGeoReceived
                  ? tr('Geo applied', 'Гео применено')
                  : (aioLinked ? tr('Waiting for conversion', 'Ожидается конверсия') : tr('Visit not linked', 'Визит не привязан'))}
              </span>
            </div>

            {profileLoading ? (
              <div className="admin-user-pocket-message">{tr('Loading AIO data…', 'Загружаем данные AIO…')}</div>
            ) : null}
            {!profileLoading && !profileError ? (
              <>
                <div className="admin-user-chatterfy-grid">
                  <div>
                    <span>AIO Visit UUID <code>click_id</code></span>
                    <strong>{formatPocketValue(pocket.aio_visit_uuid)}</strong>
                    <small>visit</small>
                  </div>
                  <div>
                    <span>{tr('AIO geo', 'Гео AIO')} <code>geo</code></span>
                    <strong>{formatPocketValue(pocket.aio_country_code || latestAioInbound?.country_code)}</strong>
                    <small>ISO alpha-2</small>
                  </div>
                  <div>
                    <span>{tr('Conversion type', 'Тип конверсии')}</span>
                    <strong>{formatPocketValue(latestAioInbound?.conversion_type_uuid)}</strong>
                    <small>conversion_type_uuid</small>
                  </div>
                  <div>
                    <span>{tr('Inbound status', 'Статус входящего события')}</span>
                    <strong>{formatPocketValue(latestAioInbound?.status)}</strong>
                    <small>{latestAioInbound ? formatAdminDate(latestAioInbound.received_at) : '—'}</small>
                  </div>
                  <div>
                    <span>{tr('Applied to profile', 'Применено к профилю')}</span>
                    <strong>{latestAioInbound?.applied_at ? tr('Yes', 'Да') : tr('No', 'Нет')}</strong>
                    <small>{formatAdminDate(latestAioInbound?.applied_at)}</small>
                  </div>
                  <div>
                    <span>{tr('Last outbound event', 'Последнее исходящее событие')}</span>
                    <strong>{formatPocketValue(latestAioOutbound?.event_slug)}</strong>
                    <small>{latestAioOutbound ? formatAdminDate(latestAioOutbound.created_at) : '—'}</small>
                  </div>
                </div>

                <details className="admin-user-pocket-details">
                  <summary>
                    {tr('Inbound AIO conversion history', 'История входящих конверсий AIO')} · {aioInboundPostbacks.length}
                  </summary>
                  {aioInboundPostbacks.length ? (
                    <div className="admin-user-pocket-events">
                      {aioInboundPostbacks.map((event) => (
                        <article key={event.id} className="admin-user-pocket-event">
                          <div>
                            <strong>{event.country_code || '—'} · {event.status || '—'}</strong>
                            <span>{formatAdminDate(event.received_at)}</span>
                          </div>
                          <div className="admin-user-pocket-event-meta">
                            <span>Conversion UUID: <b>{formatPocketValue(event.conversion_type_uuid)}</b></span>
                            <span>{tr('Applied', 'Применено')}: <b>{formatAdminDate(event.applied_at)}</b></span>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="admin-user-pocket-message">
                      {tr('No inbound AIO conversions have been received yet.', 'Входящие конверсии AIO ещё не получены.')}
                    </div>
                  )}
                </details>

                <details className="admin-user-pocket-details">
                  <summary>
                    {tr('Outbound AIO event history', 'История исходящих событий AIO')} · {aioOutboundEvents.length}
                  </summary>
                  {aioOutboundEvents.length ? (
                    <div className="admin-user-pocket-events">
                      {aioOutboundEvents.map((event) => (
                        <article key={event.id} className="admin-user-pocket-event">
                          <div>
                            <strong>{formatPocketValue(event.event_slug)}</strong>
                            <span>{formatAdminDate(event.created_at)}</span>
                          </div>
                          <div className="admin-user-pocket-event-meta">
                            <span>{tr('Status', 'Статус')}: <b>{formatPocketValue(event.status)}</b></span>
                            <span>HTTP: <b>{formatPocketValue(event.response_status)}</b></span>
                          </div>
                          {event.error ? <p>{event.error}</p> : null}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="admin-user-pocket-message">
                      {tr('No outbound AIO events have been sent yet.', 'Исходящие события AIO ещё не отправлялись.')}
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
                    'Chatterfy account and bot identifiers are linked to the Telegram user. Channel subscription is recorded only for administrators.',
                    'Идентификаторы аккаунта и бота Chatterfy связаны с Telegram-пользователем. Подписка на канал фиксируется только для администраторов.'
                  )}
                </p>
              </div>
              <span className={`admin-user-chatterfy-state ${chatterfyLinked ? 'is-success' : 'is-pending'}`}>
                {chatterfyLinked
                  ? tr('Webhook linked', 'Webhook привязан')
                  : tr('Waiting for webhook', 'Ожидается webhook')}
              </span>
            </div>

            {profileLoading ? (
              <div className="admin-user-pocket-message">{tr('Loading Chatterfy data…', 'Загружаем данные Chatterfy…')}</div>
            ) : null}
            {!profileLoading && !profileError ? (
              <>
                <div className="admin-user-chatterfy-grid">
                  <div>
                    <span>Telegram Chat ID <code>{'{chatId}'}</code></span>
                    <strong>{formatPocketValue(telegramChatId)}</strong>
                    <small>click_id</small>
                  </div>
                  <div>
                    <span>Chatterfy Chat ID · Account</span>
                    <strong>{formatPocketValue(chatterfyChatId)}</strong>
                    <small>sub_id3</small>
                  </div>
                  <div>
                    <span>Chatterfy Bot Chat ID <code>{'{id}'}</code></span>
                    <strong>{formatPocketValue(chatterfyBotChatId)}</strong>
                    <small>{tr('Bot flow', 'Воронка бота')}</small>
                  </div>
                  <div>
                    <span>Tracker Click ID <code>{'{tracker.clickid}'}</code></span>
                    <strong>{formatPocketValue(trackerClickId)}</strong>
                    <small>{tr('Stored separately', 'Хранится отдельно')}</small>
                  </div>
                  <div className={chatterfyChannelSubscribed ? 'is-subscribed' : 'is-not-subscribed'}>
                    <span>{tr('Channel subscription', 'Подписка на канал')}</span>
                    <strong>
                      {chatterfyChannelSubscribed ? tr('Yes', 'Есть') : tr('No', 'Нет')}
                    </strong>
                    <small>
                      {chatterfyChannelSubscribed
                        ? formatAdminDate(chatterfyChannelSubscribedAt)
                        : tr('No postback received', 'Postback ещё не получен')}
                    </small>
                  </div>
                  <div className={chatterfyVipGranted ? 'is-subscribed' : 'is-not-subscribed'}>
                    <span>{tr('VIP status', 'Статус VIP')}</span>
                    <strong>{chatterfyVipGranted ? tr('Granted', 'Выдан') : tr('Not granted', 'Не выдан')}</strong>
                    <small>
                      {chatterfyVipGranted
                        ? formatAdminDate(chatterfyVipGrantedAt)
                        : tr('No postback received', 'Postback ещё не получен')}
                    </small>
                  </div>
                  <div className={chatterfyCopyGranted ? 'is-subscribed' : 'is-not-subscribed'}>
                    <span>{tr('Copy status', 'Статус Copy')}</span>
                    <strong>{chatterfyCopyGranted ? tr('Granted', 'Выдан') : tr('Not granted', 'Не выдан')}</strong>
                    <small>
                      {chatterfyCopyGranted
                        ? formatAdminDate(chatterfyCopyGrantedAt)
                        : tr('No postback received', 'Postback ещё не получен')}
                    </small>
                  </div>
                </div>

                <div className="admin-user-chatterfy-map">
                  <span>{tr('Registration link mapping', 'Подстановка в ссылку регистрации')}</span>
                  <code>click_id ← {'{chatId}'}</code>
                  <code>sub_id2 ← AIO visit UUID</code>
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

          <section className={`admin-user-service-panel is-aichatter ${aiChatter.exists ? 'is-linked' : ''}`}>
            <div className="admin-user-service-head">
              <div>
                <span className="admin-user-profile-permission-kicker">Account messaging</span>
                <strong>AI Chatter</strong>
                <p>
                  {tr(
                    'A separate messaging service connected to the Telegram account. Its status does not control the main bot.',
                    'Отдельный сервис переписки, подключённый к Telegram-аккаунту. Его статус не управляет основным ботом.'
                  )}
                </p>
              </div>
              <span className={`admin-user-chatterfy-state ${aiChatter.available && aiChatter.exists ? 'is-success' : 'is-pending'}`}>
                {!aiChatter.available
                  ? tr('Service unavailable', 'Сервис недоступен')
                  : (aiChatter.exists ? tr('Profile linked', 'Профиль связан') : tr('No profile', 'Профиля нет'))}
              </span>
            </div>

            {!aiChatter.available ? (
              <div className="admin-user-service-empty">
                <strong>{tr('AI Chatter did not respond', 'AI Chatter не ответил')}</strong>
                <span>{aiChatter.error || tr('The main user profile remains available.', 'Основной профиль пользователя продолжает работать.')}</span>
              </div>
            ) : null}

            {aiChatter.available && !aiChatter.exists ? (
              <div className="admin-user-service-empty">
                <strong>{tr('There has been no conversation in AI Chatter yet', 'Диалога в AI Chatter ещё не было')}</strong>
                <span>{tr('The Chatter profile will be linked automatically after the first contact or Pocket synchronization.', 'Профиль Chatter свяжется автоматически после первого контакта или синхронизации Pocket.')}</span>
              </div>
            ) : null}

            {aiChatter.available && aiChatter.exists ? (
              <>
                <div className="admin-user-chatterfy-grid admin-user-aichatter-grid">
                  <div><span>{tr('Funnel stage', 'Этап воронки')}</span><strong>{formatPocketValue(aiChatter.stage)}</strong><small>{formatAdminDate(aiChatter.stage_updated_at)}</small></div>
                  <div><span>{tr('Messages', 'Сообщения')}</span><strong>{formatCount(aiChatter.messages_count)}</strong><small>{formatCount(aiChatter.inbound_messages)} in · {formatCount(aiChatter.outbound_messages)} out</small></div>
                  <div><span>{tr('Media sent', 'Отправлено медиа')}</span><strong>{formatCount(aiChatter.funnel_media_sent)}</strong><small>{tr('funnel items', 'элементов воронки')}</small></div>
                  <div><span>{tr('AI Chatter replies', 'Ответы AI Chatter')}</span><strong>{Number(aiChatter.bot_active) === 1 ? tr('Enabled', 'Включены') : tr('Disabled', 'Выключены')}</strong><small>{formatPocketValue(aiChatter.bot_block_reason)}</small></div>
                  <div><span>{tr('Main bot AI', 'AI основного бота')}</span><strong>{Number(aiChatter.elizabeth_bot_active) === 1 ? tr('Enabled', 'Включён') : tr('Disabled', 'Выключен')}</strong><small>{tr('Separate profile', 'Отдельный профиль')}</small></div>
                  <div><span>{tr('Last message', 'Последнее сообщение')}</span><strong>{formatAdminDate(aiChatter.last_message_at)}</strong><small>{aiChatter.latest_message?.direction || '—'}</small></div>
                </div>
                {aiChatter.latest_message?.text ? (
                  <div className="admin-user-last-message">
                    <span>{tr('Latest message preview', 'Последнее сообщение')}</span>
                    <p>{aiChatter.latest_message.text}</p>
                    <small>{formatAdminDate(aiChatter.latest_message.created_at)}</small>
                  </div>
                ) : null}
              </>
            ) : null}
          </section>
          </>
          ) : null}

          {profileTab === 'management' ? (
          <section className="admin-user-profile-section admin-user-management-summary">
            <div className="admin-user-profile-section-head">
              <div>
                <span>{tr('Control center', 'Центр управления')}</span>
                <h3>{tr('Current restrictions and access', 'Текущие ограничения и доступы')}</h3>
              </div>
              <small>{tr('Changes apply immediately', 'Изменения применяются сразу')}</small>
            </div>
            <div className="admin-user-profile-fields">
              <div><span>{tr('Application status', 'Статус приложения')}</span><strong className={!isBlocked ? 'is-positive' : ''}>{isBlocked ? tr('Blocked', 'Заблокировано') : tr('Access allowed', 'Доступ разрешён')}</strong></div>
              <div><span>{tr('Profile editing', 'Редактирование профиля')}</span><strong>{profileEditingAllowed ? tr('Allowed', 'Разрешено') : tr('Forbidden', 'Запрещено')}</strong></div>
              <div><span>Forex</span><strong className={hasAccess(selectedUser.forex_access) ? 'is-positive' : ''}>{hasAccess(selectedUser.forex_access) ? tr('Enabled', 'Включён') : tr('Disabled', 'Выключен')}</strong></div>
              <div><span>Binary</span><strong className={hasAccess(selectedUser.binary_access) ? 'is-positive' : ''}>{hasAccess(selectedUser.binary_access) ? tr('Enabled', 'Включён') : tr('Disabled', 'Выключен')}</strong></div>
              <div><span>{tr('Balance source', 'Источник баланса')}</span><strong>{Number(selectedUser.balance_sync_enabled) === 1 ? 'Pocket API' : tr('Administrator', 'Администратор')}</strong></div>
              <div><span>{tr('Staff profile', 'Профиль сотрудника')}</span><strong>{Number(selectedUser.is_admin) === 1 ? tr('Yes — protected by staff rules', 'Да — защищён правилами сотрудников') : tr('No', 'Нет')}</strong></div>
            </div>
          </section>
          ) : null}

          {profileTab === 'management' && canProfileEdit ? (
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

          {profileTab === 'data' ? (
          <>
          <section className="admin-user-profile-section admin-user-history-section">
            <div className="admin-user-profile-section-head">
              <div>
                <span>{tr('Trading history', 'Торговая история')}</span>
                <h3>{tr('Recent analyses', 'Последние анализы')}</h3>
              </div>
              <small>{formatCount(activity.recent_analyses?.length)} {tr('shown', 'показано')}</small>
            </div>
            {activity.recent_analyses?.length ? (
              <div className="admin-user-history-list">
                {activity.recent_analyses.map((analysis) => (
                  <article key={analysis.id}>
                    <span className={`is-${String(analysis.status || '').toLowerCase()}`} />
                    <div>
                      <strong>{analysis.pair || '—'} · {analysis.timeframe || '—'}</strong>
                      <small>{analysis.strategy_name || analysis.analysis_type || '—'}</small>
                    </div>
                    <div>
                      <b>{getAnalysisStatusLabel(analysis.status, tr)}</b>
                      <small>{formatAdminDate(analysis.closed_at || analysis.created_at)}</small>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="admin-user-empty-state">
                <strong>{tr('No analyses yet', 'Анализов пока нет')}</strong>
                <span>{tr('Trading activity will appear here after the first analysis.', 'Торговая активность появится после первого анализа.')}</span>
              </div>
            )}
          </section>

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
          </>
          ) : null}

          {profileTab === 'management' && (canEditAccess || canEditBalance || canBlock || canDelete) ? (
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
                      <strong>{formatAdminDate(archiveDetail.archived_at)}</strong>
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
                        <span>{tr('AIO country', 'Страна AIO')}</span>
                        <strong>{archiveProfile.aioCountry || '—'}</strong>
                      </div>
                      <div>
                        <span>{tr('Pocket country', 'Страна Pocket')}</span>
                        <strong>{archiveProfile.pocketCountry || '—'}</strong>
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
                        <strong>{formatAdminDate(archive.archived_at)}</strong>
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

      <div className="admin-user-pocket-filters" role="group" aria-label={tr('Filter users by Pocket status', 'Фильтр пользователей по статусу Pocket')}>
        {[
          { value: 'all', icon: '●', en: 'All', ru: 'Все' },
          { value: 'not_registered', icon: '○', en: 'No registration', ru: 'Без регистрации' },
          { value: 'registered', icon: '✅', en: 'Registered', ru: 'Регистрация' },
          { value: 'deposited', icon: '💵', en: 'Deposited', ru: 'С депозитом' },
        ].map((filter) => (
          <button
            key={filter.value}
            className={pocketStatus === filter.value ? 'active' : ''}
            type="button"
            aria-pressed={pocketStatus === filter.value}
            onClick={() => applyPocketStatus(filter.value)}
            disabled={loading}
          >
            <span aria-hidden="true">{filter.icon}</span>
            {tr(filter.en, filter.ru)}
          </button>
        ))}
      </div>

      {error ? <div className="admin-error">{error}</div> : null}
      {loading ? <div className="admin-muted">{tr('Loading…', 'Загрузка...')}</div> : null}

      <div className="admin-entity-list">
        {users.map((user) => {
          const blocked = Number(user.is_blocked) === 1;
          const registrationConfirmed = Number(user.pocket_registered || 0) === 1;
          const depositConfirmed = Number(user.pocket_deposited || 0) === 1;
          const vipGranted = Boolean(user.chatterfy_vip_granted_at);
          const copyGranted = Boolean(user.chatterfy_copy_granted_at);
          const avatarUrl = getAvatarUrl(user);
          return (
            <button
              key={user.user_id}
              className={`admin-entity-card admin-user-list-card ${blocked ? 'blocked' : ''}`}
              type="button"
              onClick={() => openUserCard(user.user_id)}
            >
              <div className="admin-user-list-head">
                <div className="admin-user-list-identity">
                  <div className="admin-user-avatar">
                    <span>{getInitials(user)}</span>
                    {avatarUrl ? (
                      <img src={avatarUrl} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                    ) : null}
                  </div>
                  <div>
                    <strong>{getDisplayName(user)}</strong>
                    <small>{user.username ? `@${String(user.username).replace(/^@/, '')}` : `ID ${user.user_id}`}</small>
                  </div>
                </div>
                <div className="admin-user-list-statuses">
                  <span className={`admin-user-list-status ${blocked ? 'is-blocked' : 'is-active'}`}>
                    {blocked ? tr('Blocked', 'Заблокирован') : tr('Active', 'Активен')}
                  </span>
                  {registrationConfirmed ? (
                    <span
                      className="admin-user-milestone is-registration compact"
                      title={tr('Pocket registration confirmed', 'Регистрация в Pocket подтверждена')}
                      aria-label={tr('Pocket registration confirmed', 'Регистрация в Pocket подтверждена')}
                    >
                      <span aria-hidden="true">✅</span>
                    </span>
                  ) : null}
                  {depositConfirmed ? (
                    <span
                      className="admin-user-milestone is-deposit compact"
                      title={tr('Pocket deposit confirmed', 'Депозит в Pocket подтверждён')}
                      aria-label={tr('Pocket deposit confirmed', 'Депозит в Pocket подтверждён')}
                    >
                      <span aria-hidden="true">💵</span>
                    </span>
                  ) : null}
                  {vipGranted ? (
                    <span className="admin-user-milestone is-vip compact" title="VIP" aria-label="VIP">
                      <span aria-hidden="true">◆</span>
                    </span>
                  ) : null}
                  {copyGranted ? (
                    <span className="admin-user-milestone is-copy compact" title="Copy" aria-label="Copy">
                      <span aria-hidden="true">⇄</span>
                    </span>
                  ) : null}
                </div>
              </div>
              <div className="admin-user-list-facts">
                <div><span>Telegram ID</span><strong>{user.user_id}</strong></div>
                <div><span>Trader ID</span><strong>{user.trader_id || '—'}{isManualTraderId(user) ? ' · M' : ''}</strong></div>
                <div><span>{tr('Balance', 'Баланс')}</span><strong>{formatBalance(user.balance)}</strong></div>
              </div>
              <div className="admin-user-list-foot">
                <div>
                  <span className={hasAccess(user.forex_access) ? 'on' : ''}>Forex</span>
                  <span className={hasAccess(user.binary_access) ? 'on' : ''}>Binary</span>
                  <span>{user.mode || '—'}</span>
                </div>
                <b aria-hidden="true">→</b>
              </div>
            </button>
          );
        })}
      </div>

      {!loading && users.length === 0 ? <div className="admin-muted">{tr('No users found', 'Пользователи не найдены')}</div> : null}
    </div>
  );
}

