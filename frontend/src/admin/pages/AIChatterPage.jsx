import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';
import { useAdminLocale } from '../useAdminLocale';

const EMPTY_SETTINGS = {
  system_enabled: true,
  work_start: '22:00',
  work_end: '10:00',
  bot_name: 'Elizabeth Vane',
  min_deposit: 10,
  work_24_7: false,
  ai_enabled: true,
  ai_model: 'gpt-4.1',
  openai_api_key: '',
  openai_key_configured: false,
  system_prompt: '',
  planner_system_prompt: '',
  postback_log_chat_id: '',
  log_registrations: true,
  log_deposits: true,
  log_withdrawals: true,
  log_commissions: true,
  log_system_errors: false,
  commission_mode: 'auto',
  funnel_media_enabled: true,
  registration_base_url: '',
};

const formatDate = (value, locale = 'en-US') => {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString(locale);
};

const formatMoney = (value, locale = 'en-US') => Number(value || 0).toLocaleString(locale, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const formatBytes = (value) => {
  const bytes = Number(value || 0);
  if (!bytes) return '0 MB';
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

function Toggle({ checked, onChange, label, hint }) {
  return (
    <label className="aichatter-toggle-row">
      <input type="checkbox" checked={Boolean(checked)} onChange={(event) => onChange(event.target.checked)} />
      <span>
        <strong>{label}</strong>
        {hint && <small>{hint}</small>}
      </span>
    </label>
  );
}

export default function AIChatterPage() {
  const { locale, tr } = useAdminLocale();
  const sections = [
    { id: 'overview', label: tr('Overview', 'Обзор') },
    { id: 'settings', label: tr('Settings', 'Настройки') },
    { id: 'funnel', label: tr('Funnel', 'Воронка') },
    { id: 'users', label: tr('Dialogs', 'Диалоги') },
    { id: 'triggers', label: tr('Triggers', 'Триггеры') },
    { id: 'postbacks', label: tr('Postbacks', 'Постбеки') },
  ];
  const aiModelOptions = [
    { value: 'gpt-5.6-sol', label: tr('GPT-5.6 Sol — maximum quality', 'GPT-5.6 Sol — максимальное качество') },
    { value: 'gpt-5.6-terra', label: tr('GPT-5.6 Terra — quality and cost balance', 'GPT-5.6 Terra — баланс качества и цены') },
    { value: 'gpt-5.6-luna', label: tr('GPT-5.6 Luna — fast and economical', 'GPT-5.6 Luna — быстро и экономично') },
    { value: 'gpt-5.4', label: tr('GPT-5.4 — previous flagship generation', 'GPT-5.4 — предыдущее флагманское поколение') },
    { value: 'gpt-5.4-mini', label: tr('GPT-5.4 mini — faster and cheaper', 'GPT-5.4 mini — быстрее и дешевле') },
    { value: 'gpt-5.4-nano', label: tr('GPT-5.4 nano — minimum cost', 'GPT-5.4 nano — минимальная стоимость') },
    { value: 'gpt-4.1', label: tr('GPT-4.1 — best quality', 'GPT-4.1 — лучшее качество') },
    { value: 'gpt-4.1-mini', label: tr('GPT-4.1 mini — faster and cheaper', 'GPT-4.1 mini — быстрее и дешевле') },
    { value: 'gpt-4.1-nano', label: tr('GPT-4.1 nano — minimum cost', 'GPT-4.1 nano — минимальная стоимость') },
    { value: 'gpt-4o-mini', label: tr('GPT-4o mini — economical', 'GPT-4o mini — экономичная') },
  ];
  const funnelBlocks = {
    A: tr('Warm-up', 'Прогрев'),
    W: tr('Mechanics', 'Механика'),
    E: tr('Deposit', 'Депозит'),
    R: tr('After deposit', 'После депозита'),
    C: tr('Copy trading', 'Копитрейдинг'),
  };
  const funnelBlockHints = {
    A: tr('Introduction, trust and warm-up for a new client.', 'Первое знакомство, доверие и прогрев нового клиента.'),
    W: tr('Product, signals and workflow explanation.', 'Объяснение продукта, сигналов и механики работы.'),
    E: tr('Registration, deposit and handling pre-deposit objections.', 'Регистрация, депозит и ответы на сомнения до пополнения.'),
    R: tr('Post-deposit support and first trading actions.', 'Сопровождение после депозита и первые торговые действия.'),
    C: tr('Copy trading, additional scenarios and client return.', 'Копитрейдинг, дополнительные сценарии и возврат клиента.'),
  };
  const [profile, setProfile] = useState('chatter');
  const [section, setSection] = useState('overview');
  const [overview, setOverview] = useState({ counts: {}, settings: EMPTY_SETTINGS });
  const [settings, setSettings] = useState(EMPTY_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [users, setUsers] = useState([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [userSearch, setUserSearch] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);
  const [messages, setMessages] = useState([]);
  const [clearingHistory, setClearingHistory] = useState(false);

  const [triggers, setTriggers] = useState([]);
  const [triggerInput, setTriggerInput] = useState('');
  const [postbacks, setPostbacks] = useState([]);
  const [pocketPostbackConfig, setPocketPostbackConfig] = useState({ configured: false, urls: {}, parameters: {} });
  const [postbackFilter, setPostbackFilter] = useState('');
  const [statistics, setStatistics] = useState({ daily: [], manual_commissions: [] });
  const [statsDays, setStatsDays] = useState(7);
  const [manualDate, setManualDate] = useState(new Date().toISOString().slice(0, 10));
  const [manualAmount, setManualAmount] = useState('');
  const [funnelItems, setFunnelItems] = useState([]);
  const [funnelSaving, setFunnelSaving] = useState(false);
  const [uploadingKey, setUploadingKey] = useState('');

  const flash = (message) => {
    setSuccess(message);
    window.setTimeout(() => setSuccess(''), 2500);
  };

  const loadOverview = useCallback(async () => {
    const result = await apiAdminFetchJson(`/api/admin/aichatter/overview?profile=${profile}`);
    const nextSettings = { ...EMPTY_SETTINGS, ...(result.settings || {}) };
    setOverview({ counts: result.counts || {}, settings: nextSettings });
    setSettings(nextSettings);
  }, [profile]);

  const loadUsers = useCallback(async (search = userSearch) => {
    const params = new URLSearchParams({ search, profile, page: '1', limit: '100' });
    const result = await apiAdminFetchJson(`/api/admin/aichatter/users?${params}`);
    setUsers(result.users || []);
    setUsersTotal(result.total || 0);
  }, [userSearch, profile]);

  const loadTriggers = useCallback(async () => {
    const result = await apiAdminFetchJson(`/api/admin/aichatter/triggers?profile=${profile}`);
    setTriggers(result.phrases || []);
  }, [profile]);

  const loadPostbacks = useCallback(async () => {
    const params = new URLSearchParams({ page: '1', limit: '100' });
    if (postbackFilter) params.set('event_code', postbackFilter);
    const result = await apiAdminFetchJson(`/api/admin/aichatter/postbacks?${params}`);
    setPostbacks(result.events || []);
    const config = await apiAdminFetchJson('/api/admin/aichatter/pocket-postback-config');
    setPocketPostbackConfig(config || { configured: false, urls: {}, parameters: {} });
  }, [postbackFilter]);

  const loadStatistics = useCallback(async (days) => {
    const result = await apiAdminFetchJson(`/api/admin/aichatter/statistics?days=${days}`);
    setStatistics({ daily: result.daily || [], manual_commissions: result.manual_commissions || [] });
  }, []);

  const loadFunnel = useCallback(async () => {
    const result = await apiAdminFetchJson(`/api/admin/aichatter/funnel?profile=${profile}`);
    setFunnelItems(result.items || []);
  }, [profile]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      Promise.all([loadOverview(), loadTriggers(), loadStatistics(7)])
        .catch((requestError) => setError(requestError.message || tr('Could not load AI CHATTER', 'Не удалось загрузить АИЧАТТЕР')))
        .finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadOverview, loadTriggers, loadStatistics, tr]);

  useEffect(() => {
    if (section !== 'funnel') return undefined;
    const timer = window.setTimeout(() => {
      loadFunnel().catch((requestError) => setError(requestError.message || tr('Could not load the funnel', 'Не удалось загрузить воронку')));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [profile, section, loadFunnel, tr]);

  const selectSection = async (nextSection) => {
    setSection(nextSection);
    try {
      if (nextSection === 'users') await loadUsers();
      if (nextSection === 'postbacks') await loadPostbacks();
      if (nextSection === 'funnel') await loadFunnel();
    } catch (requestError) {
      setError(requestError.message || tr('Could not load data', 'Не удалось загрузить данные'));
    }
  };

  const changeStatsDays = async (days) => {
    setStatsDays(days);
    try {
      await loadStatistics(days);
    } catch (requestError) {
      setError(requestError.message || tr('Could not load statistics', 'Не удалось загрузить статистику'));
    }
  };

  const counts = overview.counts || {};
  const dailyTotals = useMemo(() => statistics.daily.reduce((acc, row) => ({
    registrations: acc.registrations + Number(row.registrations_count || 0),
    firstDeposits: acc.firstDeposits + Number(row.first_deposit_total || 0),
    deposits: acc.deposits + Number(row.deposit_total || 0),
    commissions: acc.commissions + Number(row.commission_total || 0),
  }), { registrations: 0, firstDeposits: 0, deposits: 0, commissions: 0 }), [statistics.daily]);

  const updateField = (field, value) => setSettings((current) => ({ ...current, [field]: value }));

  const saveSettings = async () => {
    setSaving(true);
    setError('');
    try {
      const settingsPayload = { ...settings };
      delete settingsPayload.min_deposit;
      delete settingsPayload.registration_base_url;
      delete settingsPayload.openai_api_key;
      if (profile === 'elizabeth_bot') {
        settingsPayload.work_24_7 = true;
        delete settingsPayload.work_start;
        delete settingsPayload.work_end;
      }
      const result = await apiAdminFetchJson(`/api/admin/aichatter/settings?profile=${profile}`, {
        method: 'PUT',
        body: JSON.stringify(settingsPayload),
      });
      const next = { ...EMPTY_SETTINGS, ...(result.settings || {}) };
      setSettings(next);
      setOverview((current) => ({ ...current, settings: next }));
      flash(tr('Settings saved. The bot will apply them within 10 seconds.', 'Настройки сохранены. Бот применит их в течение 10 секунд.'));
    } catch (requestError) {
      setError(requestError.message || tr('Could not save settings', 'Не удалось сохранить настройки'));
    } finally {
      setSaving(false);
    }
  };

  const openConversation = async (user) => {
    setSelectedUser(user);
    setMessages([]);
    try {
      const result = await apiAdminFetchJson(`/api/admin/aichatter/users/${user.tg_user_id}/messages?limit=200`);
      setMessages(result.messages || []);
    } catch (requestError) {
      setError(requestError.message || tr('Could not load the conversation', 'Не удалось загрузить переписку'));
    }
  };

  const toggleUser = async (user) => {
    try {
      await apiAdminFetchJson(`/api/admin/aichatter/users/${user.tg_user_id}?profile=${profile}`, {
        method: 'PATCH',
        body: JSON.stringify({ bot_active: !user.bot_active }),
      });
      await loadUsers();
      if (selectedUser?.tg_user_id === user.tg_user_id) {
        setSelectedUser((current) => ({ ...current, bot_active: !current.bot_active }));
      }
      flash(user.bot_active
        ? tr('Bot disabled for this user', 'Бот отключён для пользователя')
        : tr('Bot enabled for this user', 'Бот включён для пользователя'));
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const clearConversationHistory = async (user) => {
    const confirmed = window.confirm(
      tr(
        `Clear conversation history with ${user.first_name || user.tg_user_id}?\n\nMessages and AI memory will be permanently deleted.`,
        `Очистить историю диалога с ${user.first_name || user.tg_user_id}?\n\nСообщения и AI-память будут удалены без возможности восстановления.`
      ),
    );
    if (!confirmed) return;

    setClearingHistory(true);
    setError('');
    try {
      await apiAdminFetchJson(`/api/admin/aichatter/users/${user.tg_user_id}/messages`, {
        method: 'DELETE',
      });
      setMessages([]);
      setUsers((current) => current.map((item) => (
        item.tg_user_id === user.tg_user_id ? { ...item, messages_count: 0 } : item
      )));
      flash(tr('Conversation history and AI memory have been cleared', 'История диалога и AI-память очищены'));
    } catch (requestError) {
      setError(requestError.message || tr('Could not clear the conversation history', 'Не удалось очистить историю диалога'));
    } finally {
      setClearingHistory(false);
    }
  };

  const saveTriggers = async (next) => {
    try {
      const result = await apiAdminFetchJson(`/api/admin/aichatter/triggers?profile=${profile}`, {
        method: 'PUT',
        body: JSON.stringify({ phrases: next }),
      });
      setTriggers(result.phrases || []);
      flash(tr('Triggers updated', 'Триггеры обновлены'));
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const addTriggers = () => {
    const additions = triggerInput.split(',').map((item) => item.trim()).filter(Boolean);
    const existing = new Set(triggers.map((item) => item.toLocaleLowerCase()));
    const next = [...triggers];
    additions.forEach((item) => {
      if (!existing.has(item.toLocaleLowerCase())) next.push(item);
    });
    setTriggerInput('');
    saveTriggers(next);
  };

  const saveManualCommission = async () => {
    const amount = Number(manualAmount);
    if (!manualDate || !Number.isFinite(amount) || amount < 0) {
      setError(tr('Enter a date and a valid amount', 'Укажи дату и корректную сумму'));
      return;
    }
    try {
      await apiAdminFetchJson('/api/admin/aichatter/statistics/manual-commission', {
        method: 'PUT',
        body: JSON.stringify({ stat_date: manualDate, amount }),
      });
      setManualAmount('');
      await loadStatistics(statsDays);
      flash(tr('Manual commission saved', 'Ручная комиссия сохранена'));
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const updateFunnelItem = (mediaKey, patch) => {
    setFunnelItems((current) => current.map((item) => (
      item.media_key === mediaKey ? { ...item, ...patch } : item
    )));
  };

  const moveFunnelItem = (index, direction) => {
    const target = index + direction;
    if (target < 0 || target >= funnelItems.length) return;
    setFunnelItems((current) => {
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next.map((item, itemIndex) => ({ ...item, sort_order: (itemIndex + 1) * 10 }));
    });
  };

  const saveFunnel = async () => {
    setFunnelSaving(true);
    setError('');
    try {
      const result = await apiAdminFetchJson(`/api/admin/aichatter/funnel?profile=${profile}`, {
        method: 'PUT',
        body: JSON.stringify({
          items: funnelItems.map((item, index) => ({
            media_key: item.media_key,
            block_code: item.block_code,
            title: item.title,
            description: item.description || '',
            sort_order: (index + 1) * 10,
            enabled: Boolean(item.enabled),
          })),
        }),
      });
      setFunnelItems(result.items || []);
      flash(tr('Funnel order and settings saved', 'Порядок и настройки воронки сохранены'));
    } catch (requestError) {
      setError(requestError.message || tr('Could not save the funnel', 'Не удалось сохранить воронку'));
    } finally {
      setFunnelSaving(false);
    }
  };

  const uploadFunnelMedia = async (mediaKey, file) => {
    if (!file) return;
    if (file.type && file.type !== 'video/mp4') {
      setError(tr('A video note requires an MP4 file', 'Для кружка нужен MP4-файл'));
      return;
    }
    setUploadingKey(mediaKey);
    setError('');
    try {
      await apiAdminFetchJson(`/api/admin/aichatter/funnel/${encodeURIComponent(mediaKey)}/media?profile=${profile}`, {
        method: 'PUT',
        headers: { 'Content-Type': file.type || 'video/mp4' },
        body: file,
      });
      await loadFunnel();
      flash(tr(`Video note ${mediaKey.toUpperCase()} uploaded`, `Кружок ${mediaKey.toUpperCase()} загружен`));
    } catch (requestError) {
      setError(requestError.message || tr('Could not upload the video note', 'Не удалось загрузить кружок'));
    } finally {
      setUploadingKey('');
    }
  };

  if (loading) return <div className="admin-card admin-muted">{tr('Loading AI CHATTER…', 'Загрузка АИЧАТТЕР…')}</div>;

  const isMainBotProfile = profile === 'elizabeth_bot';
  const switchProfile = async (nextProfile) => {
    if (nextProfile === profile) return;
    setProfile(nextProfile);
    setError('');
    setSuccess('');
  };

  return (
    <div className="aichatter-layout">
      <section className="admin-card aichatter-profile-switch">
        <div>
          <strong>{tr('Communication channel', 'Канал общения')}</strong>
          <small>{tr('Each channel has its own settings, prompts, schedule and video notes.', 'У каждого канала свои настройки, промпты, расписание и набор кружков.')}</small>
        </div>
        <div className="aichatter-profile-buttons">
          <button type="button" className={`admin-btn-outline ${!isMainBotProfile ? 'active' : ''}`} onClick={() => switchProfile('chatter')}>EL CHATTER · {tr('account', 'аккаунт')}</button>
          <button type="button" className={`admin-btn-outline ${isMainBotProfile ? 'active' : ''}`} onClick={() => switchProfile('elizabeth_bot')}>ELIZABETH BOT · {tr('video notes', 'кружки')}</button>
        </div>
      </section>
      <section className="admin-card aichatter-hero">
        <div>
          <div className="admin-badge">{isMainBotProfile ? '@ElizabethVane_bot' : `Telegram Business · ${tr('Elizabeth account', 'аккаунт Elizabeth')}`}</div>
          <h2 className="admin-subtitle">{isMainBotProfile ? tr('Main Elizabeth Vane bot', 'Основной бот Elizabeth Vane') : tr('EL CHATTER — account conversations', 'EL CHATTER — переписка от аккаунта')}</h2>
          <p className="admin-muted">{isMainBotProfile ? tr('Separate response and video-note settings for the main Telegram bot.', 'Отдельные настройки ответов основного Telegram-бота и его видеокружков.') : tr('A separate service connected to the Telegram account that responds on its behalf.', 'Отдельный сервис, подключённый к Telegram-аккаунту и ведущий переписку от его имени.')}</p>
        </div>
        <div className={`aichatter-status ${settings.system_enabled && settings.ai_enabled ? 'online' : 'paused'}`}>
          {settings.system_enabled && settings.ai_enabled ? tr('Running', 'Работает') : tr('Paused', 'Приостановлен')}
        </div>
      </section>

      <nav className="admin-card aichatter-nav">
        {sections.map((item) => (
          <button key={item.id} className={`admin-btn-outline ${section === item.id ? 'active' : ''}`} onClick={() => selectSection(item.id)}>
            {item.label}
          </button>
        ))}
      </nav>

      {error && <div className="admin-error">{error}</div>}
      {success && <div className="admin-success">{success}</div>}

      {section === 'overview' && (
        <div className="aichatter-stack">
          <section className="admin-kpi-grid aichatter-kpi-grid">
            {[
              [tr('Users', 'Пользователи'), counts.users_total || 0],
              [tr('Bot active', 'Активен бот'), counts.users_active || 0],
              [tr('Messages', 'Сообщения'), counts.messages_total || 0],
              [tr('Registrations', 'Регистрации'), counts.registrations || 0],
              [tr('Deposits', 'Депозиты'), counts.deposits || 0],
              [tr('Triggers', 'Триггеры'), counts.triggers_total || 0],
            ].map(([label, value]) => (
              <div className="admin-kpi-chip" key={label}><div className="admin-kpi-label">{label}</div><div className="admin-kpi-value">{value}</div></div>
            ))}
          </section>
          <section className="admin-card">
            <div className="aichatter-section-head">
              <div><h3 className="admin-section-title">{tr('Statistics', 'Статистика')}</h3><div className="admin-muted">{tr('Last', 'Последние')} {statsDays} {tr('days', 'дней')}</div></div>
              <select className="admin-input compact" value={statsDays} onChange={(event) => changeStatsDays(Number(event.target.value))}>
                <option value={1}>{tr('Today', 'Сегодня')}</option><option value={7}>{tr('7 days', '7 дней')}</option><option value={14}>{tr('14 days', '14 дней')}</option><option value={30}>{tr('30 days', '30 дней')}</option>
              </select>
            </div>
            <div className="aichatter-summary-grid">
              <div><span>{tr('Registrations', 'Регистрации')}</span><strong>{dailyTotals.registrations}</strong></div>
              <div><span>{tr('First deposit', 'Первый депозит')}</span><strong>{formatMoney(dailyTotals.firstDeposits, locale)}</strong></div>
              <div><span>{tr('Deposits', 'Депозиты')}</span><strong>{formatMoney(dailyTotals.deposits, locale)}</strong></div>
              <div><span>{tr('Commission', 'Комиссия')}</span><strong>{formatMoney(dailyTotals.commissions, locale)}</strong></div>
            </div>
          </section>
        </div>
      )}

      {section === 'settings' && (
        <div className="aichatter-stack">
          <section className="admin-card">
            <h3 className="admin-section-title">{tr('Bot operation', 'Работа бота')}</h3>
            <div className="aichatter-toggle-grid">
              <Toggle checked={settings.system_enabled} onChange={(value) => updateField('system_enabled', value)} label={tr('System enabled', 'Система включена')} hint={tr('Globally allows bot replies', 'Глобально разрешает ответы бота')} />
              <Toggle checked={settings.ai_enabled} onChange={(value) => updateField('ai_enabled', value)} label={tr('AI enabled', 'ИИ включён')} hint={tr('Allows OpenAI requests', 'Разрешает запросы к OpenAI')} />
              {isMainBotProfile
                ? <div className="aichatter-toggle-row"><span><strong>{tr('Runs 24/7', 'Работает круглосуточно')}</strong><small>{tr('The main bot always replies 24/7', 'Основной бот всегда отвечает 24/7')}</small></span></div>
                : <Toggle checked={settings.work_24_7} onChange={(value) => updateField('work_24_7', value)} label={tr('Runs 24/7', 'Работает круглосуточно')} hint={tr('Ignores working hours and replies from the account around the clock', 'Игнорирует рабочие часы и отвечает 24/7 в переписке от аккаунта')} />}
            </div>
            <div className="admin-grid aichatter-form-grid">
              {!isMainBotProfile && <label>{tr('Working hours start', 'Начало работы')}<input className="admin-input" type="time" disabled={settings.work_24_7} value={settings.work_start || ''} onChange={(event) => updateField('work_start', event.target.value)} /><small className="admin-muted">{settings.work_24_7 ? tr('Not used: 24/7 mode is enabled', 'Не используется: включён режим 24/7') : tr('Automatic reply start time', 'Время начала автоматических ответов')}</small></label>}
              {!isMainBotProfile && <label>{tr('Working hours end', 'Конец работы')}<input className="admin-input" type="time" disabled={settings.work_24_7} value={settings.work_end || ''} onChange={(event) => updateField('work_end', event.target.value)} /><small className="admin-muted">{settings.work_24_7 ? tr('Not used: 24/7 mode is enabled', 'Не используется: включён режим 24/7') : tr('Automatic reply end time', 'Время окончания автоматических ответов')}</small></label>}
              <label>{tr('Manager name', 'Имя менеджера')}<input className="admin-input" value={settings.bot_name} onChange={(event) => updateField('bot_name', event.target.value)} /></label>
              <label>{tr('OpenAI model', 'Модель OpenAI')}<select className="admin-input" value={settings.ai_model} onChange={(event) => updateField('ai_model', event.target.value)}>{!aiModelOptions.some((item) => item.value === settings.ai_model) && <option value={settings.ai_model}>{settings.ai_model} — {tr('current', 'текущая')}</option>}{aiModelOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            </div>
          </section>
          <section className="admin-card">
            <h3 className="admin-section-title">{tr('Prompts', 'Промпты')}</h3>
            <label>{tr('System prompt', 'Основной промпт')}<textarea className="admin-textarea aichatter-prompt" value={settings.system_prompt} onChange={(event) => updateField('system_prompt', event.target.value)} /></label>
            <label>{tr('Planner prompt', 'Промпт планировщика')}<textarea className="admin-textarea aichatter-prompt small" value={settings.planner_system_prompt} onChange={(event) => updateField('planner_system_prompt', event.target.value)} /></label>
          </section>
          <section className="admin-card">
            <h3 className="admin-section-title">{tr('Postbacks and logging', 'Постбеки и логирование')}</h3>
            <div className="admin-grid aichatter-form-grid">
              <label>{tr('Log Chat ID', 'Chat ID для логов')}<input className="admin-input" value={settings.postback_log_chat_id} onChange={(event) => updateField('postback_log_chat_id', event.target.value)} /></label>
              <label>{tr('Commission mode', 'Режим комиссии')}<select className="admin-input" value={settings.commission_mode} onChange={(event) => updateField('commission_mode', event.target.value)}><option value="auto">{tr('Auto', 'Авто')}</option><option value="manual">{tr('Manual', 'Ручной')}</option><option value="auto_plus">{tr('Auto+', 'Авто+')}</option></select></label>
            </div>
            <div className="aichatter-toggle-grid">
              <Toggle checked={settings.log_registrations} onChange={(value) => updateField('log_registrations', value)} label={tr('Registrations', 'Регистрации')} />
              <Toggle checked={settings.log_deposits} onChange={(value) => updateField('log_deposits', value)} label={tr('Deposits', 'Депозиты')} />
              <Toggle checked={settings.log_withdrawals} onChange={(value) => updateField('log_withdrawals', value)} label={tr('Withdrawals', 'Выводы')} />
              <Toggle checked={settings.log_commissions} onChange={(value) => updateField('log_commissions', value)} label={tr('Commissions', 'Комиссии')} />
              <Toggle checked={settings.log_system_errors} onChange={(value) => updateField('log_system_errors', value)} label={tr('System errors', 'Системные ошибки')} />
            </div>
          </section>
          <button className="admin-btn aichatter-save" disabled={saving} onClick={saveSettings}>{saving ? tr('Saving…', 'Сохранение…') : tr('Save all settings', 'Сохранить все настройки')}</button>
        </div>
      )}

      {section === 'funnel' && (
        <div className="aichatter-stack">
          <section className="admin-card">
            <div className="aichatter-section-head">
              <div>
                <h3 className="admin-section-title">{isMainBotProfile ? tr('Main bot funnel and video notes', 'Воронка основного бота и видеокружки') : tr('EL CHATTER funnel and video notes', 'Воронка EL CHATTER и видеокружки')}</h3>
                <p className="admin-muted">{isMainBotProfile ? tr('This funnel is used only by @ElizabethVane_bot and does not depend on EL CHATTER settings.', 'Эта воронка используется только в @ElizabethVane_bot и не зависит от настроек EL CHATTER.') : tr('This funnel is used only by the Telegram account conversation service and does not control the main bot.', 'Эта воронка используется только сервисом переписки от Telegram-аккаунта и не управляет основным ботом.')}</p>
              </div>
              <Toggle checked={settings.funnel_media_enabled} onChange={(value) => updateField('funnel_media_enabled', value)} label={tr('Video notes enabled', 'Кружки включены')} hint={tr('Globally enables sending', 'Глобальное включение отправки')} />
            </div>
            <div className="aichatter-funnel-explainer">
              <div><strong>{tr('1. The prompt controls the dialog', '1. Промпт управляет диалогом')}</strong><span>{tr('AI determines the client stage and selects a technical tag, for example', 'AI определяет этап клиента и выбирает технический тег, например')} <code>[SEND:a1]</code>.</span></div>
              <div><strong>{tr('2. The tag selects an MP4', '2. Тег выбирает MP4')}</strong><span>{tr('The service finds the file below and converts it into a Telegram video note.', 'По тегу сервис находит файл ниже и преобразует его в Telegram-видеокружок.')}</span></div>
              <div><strong>{tr('3. The client receives the reply', '3. Клиент получает ответ')}</strong><span>{tr('The video note is sent first, followed by AI text. The same step is never sent twice.', 'Сначала уходит кружок, затем текст AI. Один и тот же шаг повторно не отправляется.')}</span></div>
            </div>
            <label className="aichatter-field-label">
              <span>{tr('Main system prompt for', 'Основной системный промпт')} {isMainBotProfile ? tr('Elizabeth bot', 'бота Elizabeth') : 'EL CHATTER'}</span>
              <small>{tr('Define Elizabeth’s personality, sales logic, reply language and tag selection rules here. Card names and instructions below are added automatically, so they do not need to be copied into the prompt.', 'Здесь задаются характер Элизабет, логика продажи, язык ответа и правила выбора тегов [SEND:id]. Названия и инструкции карточек ниже автоматически добавляются к этому промпту — копировать их сюда не нужно.')} <code>[SEND:id]</code></small>
              <textarea className="admin-textarea aichatter-prompt" value={settings.system_prompt} onChange={(event) => updateField('system_prompt', event.target.value)} placeholder={tr('Core AI dialog rules…', 'Основные правила диалога AI-чаттера…')} />
            </label>
            <button className="admin-btn" disabled={saving} onClick={saveSettings}>{saving ? tr('Saving…', 'Сохранение…') : `${tr('Save prompt for', 'Сохранить промпт')} ${isMainBotProfile ? tr('bot', 'бота') : 'EL CHATTER'}`}</button>
          </section>

          <section className="admin-card">
            <div className="aichatter-section-head">
              <div>
                <h3 className="admin-section-title">{tr('Tag and video-note routing', 'Маршрутизация тегов и кружков')}</h3>
                <p className="admin-muted">{tr('Each card connects an AI instruction, a technical tag and one MP4 file. Card order defines the recommended A → W → E → R → C sequence.', 'Каждая карточка связывает инструкцию для AI, технический тег и один MP4-файл. Порядок карточек задаёт рекомендуемую последовательность A → W → E → R → C.')}</p>
              </div>
              <div className="aichatter-funnel-total">{funnelItems.filter((item) => item.file_exists).length}/{funnelItems.length} {tr('uploaded', 'загружено')}</div>
            </div>

            <div className="aichatter-funnel-list">
              {funnelItems.map((item, index) => (
                <article className={`aichatter-funnel-item ${item.enabled ? '' : 'disabled'}`} key={item.media_key}>
                  <div className="aichatter-funnel-order">
                    <strong>{index + 1}</strong>
                    <button type="button" disabled={index === 0} onClick={() => moveFunnelItem(index, -1)} title={tr('Move up', 'Переместить выше')} aria-label={tr('Move step up', 'Переместить шаг выше')}>
                      <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 12.5 10 7l5.5 5.5" /></svg>
                    </button>
                    <button type="button" disabled={index === funnelItems.length - 1} onClick={() => moveFunnelItem(index, 1)} title={tr('Move down', 'Переместить ниже')} aria-label={tr('Move step down', 'Переместить шаг ниже')}>
                      <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m4.5 7.5 5.5 5.5 5.5-5.5" /></svg>
                    </button>
                  </div>
                  <div className="aichatter-funnel-fields">
                    <div className="aichatter-funnel-card-head">
                      <div>
                        <span className="aichatter-funnel-eyebrow">{tr('Step', 'Шаг')} {index + 1} · {funnelBlocks[item.block_code] || item.block_code}</span>
                        <strong>{item.title || `${tr('Video note', 'Кружок')} ${item.media_key}`}</strong>
                      </div>
                      <Toggle checked={item.enabled} onChange={(value) => updateFunnelItem(item.media_key, { enabled: value })} label={item.enabled ? tr('Step active', 'Шаг активен') : tr('Step disabled', 'Шаг выключен')} />
                    </div>

                    <div className="aichatter-funnel-config-grid">
                      <label className="aichatter-field-label">
                        <span>{tr('Technical tag in the AI reply', 'Технический тег в ответе AI')}</span>
                        <small>{tr('AI inserts this tag to send this specific MP4. The tag is generated from the filename and cannot be edited.', 'AI вставляет этот тег, чтобы отправить именно данный MP4. Тег формируется из имени файла и не редактируется.')}</small>
                        <code className="aichatter-funnel-key">[SEND:{item.media_key}]</code>
                      </label>
                      <label className="aichatter-field-label">
                        <span>{tr('Dialog stage', 'Этап диалога')}</span>
                        <small>{funnelBlockHints[item.block_code] || tr('Technical funnel step group.', 'Техническая группа шага воронки.')}</small>
                        <select className="admin-input" value={item.block_code} onChange={(event) => updateFunnelItem(item.media_key, { block_code: event.target.value })}>
                          {Object.entries(funnelBlocks).map(([code, label]) => <option key={code} value={code}>{code} · {label}</option>)}
                        </select>
                      </label>
                    </div>

                    <label className="aichatter-field-label">
                      <span>{tr('Step name for AI and administrators', 'Название шага для AI и администратора')}</span>
                      <small>{tr('Briefly describe the video. This name is automatically included in the AI technical hint.', 'Коротко опишите смысл ролика. Это название автоматически попадает в техническую подсказку AI.')}</small>
                      <input className="admin-input" value={item.title} onChange={(event) => updateFunnelItem(item.media_key, { title: event.target.value })} placeholder={tr('For example: First introduction to Elizabeth', 'Например: Первое знакомство с Элизабет')} />
                    </label>
                    <label className="aichatter-field-label">
                      <span>{tr('When AI should send this video note', 'Когда AI должен отправить этот кружок')}</span>
                      <small>{tr('State the exact condition: at which stage, after which client message, and for what purpose this tag should be selected. This is an internal AI instruction, not client-facing text.', 'Напишите конкретное условие: на каком этапе, после какой реплики клиента и с какой целью выбирать этот тег. Это не текст сообщения клиенту, а внутренняя инструкция для AI.')}</small>
                      <textarea className="admin-textarea aichatter-funnel-description" value={item.description || ''} onChange={(event) => updateFunnelItem(item.media_key, { description: event.target.value })} placeholder={tr('For example: send during the first introduction, before the client has seen Elizabeth’s presentation…', 'Например: отправить при первом знакомстве, когда клиент ещё не знает Элизабет и не видел презентацию…')} />
                    </label>
                    <div className="aichatter-funnel-file-row">
                      <div className="aichatter-funnel-file-meta">
                        <span className="aichatter-field-caption">{tr('MP4 file for Telegram video note', 'MP4-файл для Telegram-кружка')}</span>
                        <span className={`aichatter-pill ${item.file_exists ? 'ok' : 'off'}`}>{item.file_exists ? `${item.file_name} · ${formatBytes(item.file_size)}` : tr('File not uploaded', 'Файл не загружен')}</span>
                        <small className="admin-muted">{tr('Unique client sends', 'Уникальных отправок клиентам')}: {item.sent_count || 0}</small>
                      </div>
                      <label className="admin-btn-outline aichatter-file-button">
                        {uploadingKey === item.media_key ? tr('Uploading…', 'Загрузка…') : item.file_exists ? tr('Replace MP4', 'Заменить MP4') : tr('Upload MP4', 'Загрузить MP4')}
                        <input type="file" accept="video/mp4,.mp4" disabled={Boolean(uploadingKey)} onChange={(event) => uploadFunnelMedia(item.media_key, event.target.files?.[0])} />
                      </label>
                    </div>
                  </div>
                </article>
              ))}
              {!funnelItems.length && <div className="admin-muted">{tr('Funnel steps have not been loaded yet', 'Шаги воронки пока не загружены')}</div>}
            </div>
          </section>
          <button className="admin-btn aichatter-save" disabled={funnelSaving} onClick={saveFunnel}>{funnelSaving ? tr('Saving…', 'Сохранение…') : tr('Save order and video notes', 'Сохранить порядок и кружки')}</button>
        </div>
      )}

      {section === 'users' && (
        <div className="aichatter-stack">
          <section className="admin-card">
            <div className="aichatter-section-head">
              <div>
                <h3 className="admin-section-title">{tr('Users and dialogs', 'Пользователи и диалоги')}</h3>
                <div className="admin-muted">{tr('Found', 'Найдено')}: {usersTotal}</div>
              </div>
            </div>
            <div className="aichatter-inline-form">
              <input
                className="admin-input"
                placeholder={tr('ID, username, name or Trader ID', 'ID, username, имя или Trader ID')}
                value={userSearch}
                onChange={(event) => setUserSearch(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && loadUsers()}
              />
              <button className="admin-btn" onClick={() => loadUsers()}>{tr('Search', 'Найти')}</button>
            </div>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>{tr('User', 'Пользователь')}</th>
                    <th>{tr('Stage', 'Этап')}</th>
                    <th>{tr('Status', 'Статус')}</th>
                    <th>{tr('Messages', 'Сообщения')}</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.tg_user_id}>
                      <td>
                        <strong>{user.first_name || tr('No name', 'Без имени')}</strong><br />
                        <span className="admin-muted">@{user.username || '—'} · {user.tg_user_id}</span>
                      </td>
                      <td>{user.stage || 'new'}<br /><span className="admin-muted">Trader: {user.trader_id || '—'}</span></td>
                      <td>
                        <span className={`aichatter-pill ${user.bot_active ? 'ok' : 'off'}`}>
                          {user.bot_active ? tr('Bot enabled', 'Бот включён') : tr('Disabled', 'Отключён')}
                        </span><br />
                        <span className="admin-muted">
                          R: {user.registration_status ? tr('yes', 'да') : tr('no', 'нет')} · D: {user.deposit_status ? tr('yes', 'да') : tr('no', 'нет')}
                        </span>
                      </td>
                      <td>{user.messages_count || 0}</td>
                      <td><button className="admin-btn-outline" onClick={() => openConversation(user)}>{tr('Open', 'Открыть')}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {selectedUser && (
            <section className="admin-card">
              <div className="aichatter-section-head">
                <div>
                  <h3 className="admin-section-title">{tr('Dialog with', 'Диалог с')} {selectedUser.first_name || selectedUser.tg_user_id}</h3>
                  <div className="admin-muted">{selectedUser.notes || tr('No notes', 'Без заметок')}</div>
                </div>
                <div className="aichatter-conversation-actions">
                  <button className={`admin-btn-outline ${selectedUser.bot_active ? 'danger' : ''}`} onClick={() => toggleUser(selectedUser)}>
                    {selectedUser.bot_active ? tr('Disable bot', 'Отключить бота') : tr('Enable bot', 'Включить бота')}
                  </button>
                  <button className="admin-btn-outline danger" disabled={clearingHistory} onClick={() => clearConversationHistory(selectedUser)}>
                    {clearingHistory ? tr('Clearing…', 'Очистка…') : tr('Clear history', 'Очистить историю')}
                  </button>
                </div>
              </div>
              <div className="aichatter-conversation">
                {messages.length ? messages.map((message) => (
                  <div key={message.id} className={`aichatter-message ${message.direction === 'out' ? 'out' : 'in'}`}>
                    <div>{message.text || '—'}</div>
                    <small>{message.is_business ? 'Business · ' : ''}{formatDate(message.created_at, locale)}</small>
                  </div>
                )) : <div className="admin-muted">{tr('No messages yet', 'Сообщений пока нет')}</div>}
              </div>
            </section>
          )}
        </div>
      )}

      {section === 'triggers' && (
        <section className="admin-card">
          <h3 className="admin-section-title">{tr('Stop triggers', 'Стоп-триггеры')}</h3>
          <p className="admin-muted">{tr('If a client uses one of these phrases, the bot stops the automatic dialog and notifies administrators.', 'Если клиент использует одну из фраз, бот останавливает автоматический диалог и уведомляет администраторов.')}</p>
          <div className="aichatter-inline-form">
            <input className="admin-input" placeholder={tr('Comma-separated phrases', 'Несколько фраз через запятую')} value={triggerInput} onChange={(event) => setTriggerInput(event.target.value)} />
            <button className="admin-btn" onClick={addTriggers}>{tr('Add', 'Добавить')}</button>
          </div>
          <div className="aichatter-tags">
            {triggers.map((trigger) => (
              <button key={trigger} title={tr('Delete', 'Удалить')} onClick={() => saveTriggers(triggers.filter((item) => item !== trigger))}>
                {trigger}<span>×</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {section === 'postbacks' && (
        <div className="aichatter-stack">
          <section className="admin-card">
            <h3 className="admin-section-title">{tr('Pocket Option URLs', 'Ссылки Pocket Option')}</h3>
            <p className="admin-muted">{tr('Create three postback events in the affiliate dashboard. Deposits must include transaction_id.', 'Создайте три postback-события в партнёрском кабинете. Для депозитов обязательно передавайте transaction_id.')}</p>
            {['reg', 'dep1', 'dep'].map((code) => (
              <label key={code}>
                {code}
                <input
                  className="admin-input"
                  readOnly
                  value={pocketPostbackConfig.urls?.[code] || tr('Server secret is not configured yet', 'Секрет ещё не настроен на сервере')}
                  onFocus={(event) => event.target.select()}
                />
              </label>
            ))}
            <p className="admin-muted">{tr('Shared parameters: click_id, site_id, trader_id, cid, ac. Registration: country, promo, device_type. Deposits: sumdep, transaction_id.', 'Общие параметры: click_id, site_id, trader_id, cid, ac. Регистрация: country, promo, device_type. Депозиты: sumdep, transaction_id.')}</p>
          </section>

          <section className="admin-card">
            <div className="aichatter-section-head">
              <h3 className="admin-section-title">{tr('Postback events', 'События postback')}</h3>
              <div className="aichatter-inline-form compact">
                <select className="admin-input compact" value={postbackFilter} onChange={(event) => setPostbackFilter(event.target.value)}>
                  <option value="">{tr('All events', 'Все события')}</option>
                  <option value="reg">{tr('Registration', 'Регистрация')}</option>
                  <option value="dep1">{tr('First deposit', 'Первый депозит')}</option>
                  <option value="dep">{tr('Deposit', 'Депозит')}</option>
                  <option value="wdr">{tr('Withdrawal', 'Вывод')}</option>
                  <option value="commission">{tr('Commission', 'Комиссия')}</option>
                </select>
                <button className="admin-btn-outline" onClick={loadPostbacks}>{tr('Refresh', 'Обновить')}</button>
              </div>
            </div>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>{tr('Date', 'Дата')}</th>
                    <th>{tr('Event', 'Событие')}</th>
                    <th>{tr('User', 'Пользователь')}</th>
                    <th>Trader ID</th>
                    <th>{tr('Amount', 'Сумма')}</th>
                    <th>{tr('Status', 'Статус')}</th>
                  </tr>
                </thead>
                <tbody>
                  {postbacks.map((item) => (
                    <tr key={item.id}>
                      <td>{formatDate(item.created_at, locale)}</td>
                      <td>{item.event_code}</td>
                      <td>{item.tg_user_id || '—'}</td>
                      <td>{item.trader_id || '—'}</td>
                      <td>{formatMoney(item.commission || item.sumdep || item.wdr_sum, locale)}</td>
                      <td>{item.status || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="admin-card">
            <h3 className="admin-section-title">{tr('Manual commission', 'Ручная комиссия')}</h3>
            <div className="aichatter-inline-form">
              <input className="admin-input" type="date" value={manualDate} onChange={(event) => setManualDate(event.target.value)} />
              <input className="admin-input" type="number" min="0" step="0.01" placeholder={tr('Amount', 'Сумма')} value={manualAmount} onChange={(event) => setManualAmount(event.target.value)} />
              <button className="admin-btn" onClick={saveManualCommission}>{tr('Save', 'Сохранить')}</button>
            </div>
            {statistics.manual_commissions.length > 0 && (
              <div className="aichatter-manual-list">
                {statistics.manual_commissions.map((item) => (
                  <span key={item.stat_date}>{String(item.stat_date).slice(0, 10)}: <strong>{formatMoney(item.amount, locale)}</strong></span>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

    </div>
  );
}
