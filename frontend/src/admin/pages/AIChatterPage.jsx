import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';

const SECTIONS = [
  { id: 'overview', label: 'Обзор' },
  { id: 'settings', label: 'Настройки' },
  { id: 'funnel', label: 'Воронка' },
  { id: 'users', label: 'Диалоги' },
  { id: 'triggers', label: 'Триггеры' },
  { id: 'postbacks', label: 'Постбеки' },
];

const AI_MODEL_OPTIONS = [
  { value: 'gpt-5.6-sol', label: 'GPT-5.6 Sol — максимальное качество' },
  { value: 'gpt-5.6-terra', label: 'GPT-5.6 Terra — баланс качества и цены' },
  { value: 'gpt-5.6-luna', label: 'GPT-5.6 Luna — быстро и экономично' },
  { value: 'gpt-5.4', label: 'GPT-5.4 — предыдущее флагманское поколение' },
  { value: 'gpt-5.4-mini', label: 'GPT-5.4 mini — быстрее и дешевле' },
  { value: 'gpt-5.4-nano', label: 'GPT-5.4 nano — минимальная стоимость' },
  { value: 'gpt-4.1', label: 'GPT-4.1 — лучшее качество' },
  { value: 'gpt-4.1-mini', label: 'GPT-4.1 mini — быстрее и дешевле' },
  { value: 'gpt-4.1-nano', label: 'GPT-4.1 nano — минимальная стоимость' },
  { value: 'gpt-4o-mini', label: 'GPT-4o mini — экономичная' },
];

const FUNNEL_BLOCKS = {
  A: 'Прогрев',
  W: 'Механика',
  E: 'Депозит',
  R: 'После депозита',
  C: 'Копитрейдинг',
};

const FUNNEL_BLOCK_HINTS = {
  A: 'Первое знакомство, доверие и прогрев нового клиента.',
  W: 'Объяснение продукта, сигналов и механики работы.',
  E: 'Регистрация, депозит и ответы на сомнения до пополнения.',
  R: 'Сопровождение после депозита и первые торговые действия.',
  C: 'Копитрейдинг, дополнительные сценарии и возврат клиента.',
};

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

const formatDate = (value) => {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString('ru-RU');
};

const formatMoney = (value) => Number(value || 0).toLocaleString('ru-RU', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const formatBytes = (value) => {
  const bytes = Number(value || 0);
  if (!bytes) return '0 МБ';
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
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
        .catch((requestError) => setError(requestError.message || 'Не удалось загрузить АИЧАТТЕР'))
        .finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadOverview, loadTriggers, loadStatistics]);

  useEffect(() => {
    if (section !== 'funnel') return undefined;
    const timer = window.setTimeout(() => {
      loadFunnel().catch((requestError) => setError(requestError.message || 'Не удалось загрузить воронку'));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [profile, section, loadFunnel]);

  const selectSection = async (nextSection) => {
    setSection(nextSection);
    try {
      if (nextSection === 'users') await loadUsers();
      if (nextSection === 'postbacks') await loadPostbacks();
      if (nextSection === 'funnel') await loadFunnel();
    } catch (requestError) {
      setError(requestError.message || 'Не удалось загрузить данные');
    }
  };

  const changeStatsDays = async (days) => {
    setStatsDays(days);
    try {
      await loadStatistics(days);
    } catch (requestError) {
      setError(requestError.message || 'Не удалось загрузить статистику');
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
      flash('Настройки сохранены. Бот применит их в течение 10 секунд.');
    } catch (requestError) {
      setError(requestError.message || 'Не удалось сохранить настройки');
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
      setError(requestError.message || 'Не удалось загрузить переписку');
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
      flash(user.bot_active ? 'Бот отключён для пользователя' : 'Бот включён для пользователя');
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const clearConversationHistory = async (user) => {
    const confirmed = window.confirm(
      `Очистить историю диалога с ${user.first_name || user.tg_user_id}?\n\nСообщения и AI-память будут удалены без возможности восстановления.`,
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
      flash('История диалога и AI-память очищены');
    } catch (requestError) {
      setError(requestError.message || 'Не удалось очистить историю диалога');
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
      flash('Триггеры обновлены');
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
      setError('Укажи дату и корректную сумму');
      return;
    }
    try {
      await apiAdminFetchJson('/api/admin/aichatter/statistics/manual-commission', {
        method: 'PUT',
        body: JSON.stringify({ stat_date: manualDate, amount }),
      });
      setManualAmount('');
      await loadStatistics(statsDays);
      flash('Ручная комиссия сохранена');
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
      flash('Порядок и настройки воронки сохранены');
    } catch (requestError) {
      setError(requestError.message || 'Не удалось сохранить воронку');
    } finally {
      setFunnelSaving(false);
    }
  };

  const uploadFunnelMedia = async (mediaKey, file) => {
    if (!file) return;
    if (file.type && file.type !== 'video/mp4') {
      setError('Для кружка нужен MP4-файл');
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
      flash(`Кружок ${mediaKey.toUpperCase()} загружен`);
    } catch (requestError) {
      setError(requestError.message || 'Не удалось загрузить кружок');
    } finally {
      setUploadingKey('');
    }
  };

  if (loading) return <div className="admin-card admin-muted">Загрузка АИЧАТТЕР…</div>;

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
          <strong>Канал общения</strong>
          <small>У каждого канала свои настройки, промпты, расписание и набор кружков.</small>
        </div>
        <div className="aichatter-profile-buttons">
          <button type="button" className={`admin-btn-outline ${!isMainBotProfile ? 'active' : ''}`} onClick={() => switchProfile('chatter')}>EL CHATTER · аккаунт</button>
          <button type="button" className={`admin-btn-outline ${isMainBotProfile ? 'active' : ''}`} onClick={() => switchProfile('elizabeth_bot')}>БОТ ELIZABETH · кружки</button>
        </div>
      </section>
      <section className="admin-card aichatter-hero">
        <div>
          <div className="admin-badge">{isMainBotProfile ? '@ElizabethVane_bot' : 'Telegram Business · аккаунт Elizabeth'}</div>
          <h2 className="admin-subtitle">{isMainBotProfile ? 'Основной бот Elizabeth Vane' : 'EL CHATTER — переписка от аккаунта'}</h2>
          <p className="admin-muted">{isMainBotProfile ? 'Отдельные настройки ответов основного Telegram-бота и его видеокружков.' : 'Отдельный сервис, подключённый к Telegram-аккаунту и ведущий переписку от его имени.'}</p>
        </div>
        <div className={`aichatter-status ${settings.system_enabled && settings.ai_enabled ? 'online' : 'paused'}`}>
          {settings.system_enabled && settings.ai_enabled ? 'Работает' : 'Приостановлен'}
        </div>
      </section>

      <nav className="admin-card aichatter-nav">
        {SECTIONS.map((item) => (
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
              ['Пользователи', counts.users_total || 0],
              ['Активен бот', counts.users_active || 0],
              ['Сообщения', counts.messages_total || 0],
              ['Регистрации', counts.registrations || 0],
              ['Депозиты', counts.deposits || 0],
              ['Триггеры', counts.triggers_total || 0],
            ].map(([label, value]) => (
              <div className="admin-kpi-chip" key={label}><div className="admin-kpi-label">{label}</div><div className="admin-kpi-value">{value}</div></div>
            ))}
          </section>
          <section className="admin-card">
            <div className="aichatter-section-head">
              <div><h3 className="admin-section-title">Статистика</h3><div className="admin-muted">Последние {statsDays} дней</div></div>
              <select className="admin-input compact" value={statsDays} onChange={(event) => changeStatsDays(Number(event.target.value))}>
                <option value={1}>Сегодня</option><option value={7}>7 дней</option><option value={14}>14 дней</option><option value={30}>30 дней</option>
              </select>
            </div>
            <div className="aichatter-summary-grid">
              <div><span>Регистрации</span><strong>{dailyTotals.registrations}</strong></div>
              <div><span>Первый депозит</span><strong>{formatMoney(dailyTotals.firstDeposits)}</strong></div>
              <div><span>Депозиты</span><strong>{formatMoney(dailyTotals.deposits)}</strong></div>
              <div><span>Комиссия</span><strong>{formatMoney(dailyTotals.commissions)}</strong></div>
            </div>
          </section>
        </div>
      )}

      {section === 'settings' && (
        <div className="aichatter-stack">
          <section className="admin-card">
            <h3 className="admin-section-title">Работа бота</h3>
            <div className="aichatter-toggle-grid">
              <Toggle checked={settings.system_enabled} onChange={(value) => updateField('system_enabled', value)} label="Система включена" hint="Глобально разрешает ответы бота" />
              <Toggle checked={settings.ai_enabled} onChange={(value) => updateField('ai_enabled', value)} label="ИИ включён" hint="Разрешает запросы к OpenAI" />
              {isMainBotProfile
                ? <div className="aichatter-toggle-row"><span><strong>Работает круглосуточно</strong><small>Основной бот всегда отвечает 24/7</small></span></div>
                : <Toggle checked={settings.work_24_7} onChange={(value) => updateField('work_24_7', value)} label="Работает круглосуточно" hint="Игнорирует рабочие часы и отвечает 24/7 в переписке от аккаунта" />}
            </div>
            <div className="admin-grid aichatter-form-grid">
              {!isMainBotProfile && <label>Начало работы<input className="admin-input" type="time" disabled={settings.work_24_7} value={settings.work_start || ''} onChange={(event) => updateField('work_start', event.target.value)} /><small className="admin-muted">{settings.work_24_7 ? 'Не используется: включён режим 24/7' : 'Время начала автоматических ответов'}</small></label>}
              {!isMainBotProfile && <label>Конец работы<input className="admin-input" type="time" disabled={settings.work_24_7} value={settings.work_end || ''} onChange={(event) => updateField('work_end', event.target.value)} /><small className="admin-muted">{settings.work_24_7 ? 'Не используется: включён режим 24/7' : 'Время окончания автоматических ответов'}</small></label>}
              <label>Имя менеджера<input className="admin-input" value={settings.bot_name} onChange={(event) => updateField('bot_name', event.target.value)} /></label>
              <label>Модель OpenAI<select className="admin-input" value={settings.ai_model} onChange={(event) => updateField('ai_model', event.target.value)}>{!AI_MODEL_OPTIONS.some((item) => item.value === settings.ai_model) && <option value={settings.ai_model}>{settings.ai_model} — текущая</option>}{AI_MODEL_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            </div>
          </section>
          <section className="admin-card">
            <h3 className="admin-section-title">Промпты</h3>
            <label>Основной промпт<textarea className="admin-textarea aichatter-prompt" value={settings.system_prompt} onChange={(event) => updateField('system_prompt', event.target.value)} /></label>
            <label>Промпт планировщика<textarea className="admin-textarea aichatter-prompt small" value={settings.planner_system_prompt} onChange={(event) => updateField('planner_system_prompt', event.target.value)} /></label>
          </section>
          <section className="admin-card">
            <h3 className="admin-section-title">Постбеки и логирование</h3>
            <div className="admin-grid aichatter-form-grid">
              <label>Chat ID для логов<input className="admin-input" value={settings.postback_log_chat_id} onChange={(event) => updateField('postback_log_chat_id', event.target.value)} /></label>
              <label>Режим комиссии<select className="admin-input" value={settings.commission_mode} onChange={(event) => updateField('commission_mode', event.target.value)}><option value="auto">Авто</option><option value="manual">Ручной</option><option value="auto_plus">Авто+</option></select></label>
            </div>
            <div className="aichatter-toggle-grid">
              <Toggle checked={settings.log_registrations} onChange={(value) => updateField('log_registrations', value)} label="Регистрации" />
              <Toggle checked={settings.log_deposits} onChange={(value) => updateField('log_deposits', value)} label="Депозиты" />
              <Toggle checked={settings.log_withdrawals} onChange={(value) => updateField('log_withdrawals', value)} label="Выводы" />
              <Toggle checked={settings.log_commissions} onChange={(value) => updateField('log_commissions', value)} label="Комиссии" />
              <Toggle checked={settings.log_system_errors} onChange={(value) => updateField('log_system_errors', value)} label="Системные ошибки" />
            </div>
          </section>
          <button className="admin-btn aichatter-save" disabled={saving} onClick={saveSettings}>{saving ? 'Сохранение…' : 'Сохранить все настройки'}</button>
        </div>
      )}

      {section === 'funnel' && (
        <div className="aichatter-stack">
          <section className="admin-card">
            <div className="aichatter-section-head">
              <div>
                <h3 className="admin-section-title">{isMainBotProfile ? 'Воронка основного бота и видеокружки' : 'Воронка EL CHATTER и видеокружки'}</h3>
                <p className="admin-muted">{isMainBotProfile ? 'Эта воронка используется только в @ElizabethVane_bot и не зависит от настроек EL CHATTER.' : 'Эта воронка используется только сервисом переписки от Telegram-аккаунта и не управляет основным ботом.'}</p>
              </div>
              <Toggle checked={settings.funnel_media_enabled} onChange={(value) => updateField('funnel_media_enabled', value)} label="Кружки включены" hint="Глобальное включение отправки" />
            </div>
            <div className="aichatter-funnel-explainer">
              <div><strong>1. Промпт управляет диалогом</strong><span>AI определяет этап клиента и выбирает технический тег, например <code>[SEND:a1]</code>.</span></div>
              <div><strong>2. Тег выбирает MP4</strong><span>По тегу сервис находит файл ниже и преобразует его в Telegram-видеокружок.</span></div>
              <div><strong>3. Клиент получает ответ</strong><span>Сначала уходит кружок, затем текст AI. Один и тот же шаг повторно не отправляется.</span></div>
            </div>
            <label className="aichatter-field-label">
              <span>Основной системный промпт {isMainBotProfile ? 'бота Elizabeth' : 'EL CHATTER'}</span>
              <small>Здесь задаются характер Элизабет, логика продажи, язык ответа и правила выбора тегов <code>[SEND:id]</code>. Названия и инструкции карточек ниже автоматически добавляются к этому промпту — копировать их сюда не нужно.</small>
              <textarea className="admin-textarea aichatter-prompt" value={settings.system_prompt} onChange={(event) => updateField('system_prompt', event.target.value)} placeholder="Основные правила диалога AI-чаттера…" />
            </label>
            <button className="admin-btn" disabled={saving} onClick={saveSettings}>{saving ? 'Сохранение…' : `Сохранить промпт ${isMainBotProfile ? 'бота' : 'EL CHATTER'}`}</button>
          </section>

          <section className="admin-card">
            <div className="aichatter-section-head">
              <div>
                <h3 className="admin-section-title">Маршрутизация тегов и кружков</h3>
                <p className="admin-muted">Каждая карточка связывает инструкцию для AI, технический тег и один MP4-файл. Порядок карточек задаёт рекомендуемую последовательность A → W → E → R → C.</p>
              </div>
              <div className="aichatter-funnel-total">{funnelItems.filter((item) => item.file_exists).length}/{funnelItems.length} загружено</div>
            </div>

            <div className="aichatter-funnel-list">
              {funnelItems.map((item, index) => (
                <article className={`aichatter-funnel-item ${item.enabled ? '' : 'disabled'}`} key={item.media_key}>
                  <div className="aichatter-funnel-order">
                    <strong>{index + 1}</strong>
                    <button type="button" disabled={index === 0} onClick={() => moveFunnelItem(index, -1)} title="Переместить выше" aria-label="Переместить шаг выше">
                      <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4.5 12.5 10 7l5.5 5.5" /></svg>
                    </button>
                    <button type="button" disabled={index === funnelItems.length - 1} onClick={() => moveFunnelItem(index, 1)} title="Переместить ниже" aria-label="Переместить шаг ниже">
                      <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m4.5 7.5 5.5 5.5 5.5-5.5" /></svg>
                    </button>
                  </div>
                  <div className="aichatter-funnel-fields">
                    <div className="aichatter-funnel-card-head">
                      <div>
                        <span className="aichatter-funnel-eyebrow">Шаг {index + 1} · {FUNNEL_BLOCKS[item.block_code] || item.block_code}</span>
                        <strong>{item.title || `Кружок ${item.media_key}`}</strong>
                      </div>
                      <Toggle checked={item.enabled} onChange={(value) => updateFunnelItem(item.media_key, { enabled: value })} label={item.enabled ? 'Шаг активен' : 'Шаг выключен'} />
                    </div>

                    <div className="aichatter-funnel-config-grid">
                      <label className="aichatter-field-label">
                        <span>Технический тег в ответе AI</span>
                        <small>AI вставляет этот тег, чтобы отправить именно данный MP4. Тег формируется из имени файла и не редактируется.</small>
                        <code className="aichatter-funnel-key">[SEND:{item.media_key}]</code>
                      </label>
                      <label className="aichatter-field-label">
                        <span>Этап диалога</span>
                        <small>{FUNNEL_BLOCK_HINTS[item.block_code] || 'Техническая группа шага воронки.'}</small>
                        <select className="admin-input" value={item.block_code} onChange={(event) => updateFunnelItem(item.media_key, { block_code: event.target.value })}>
                          {Object.entries(FUNNEL_BLOCKS).map(([code, label]) => <option key={code} value={code}>{code} · {label}</option>)}
                        </select>
                      </label>
                    </div>

                    <label className="aichatter-field-label">
                      <span>Название шага для AI и администратора</span>
                      <small>Коротко опишите смысл ролика. Это название автоматически попадает в техническую подсказку AI.</small>
                      <input className="admin-input" value={item.title} onChange={(event) => updateFunnelItem(item.media_key, { title: event.target.value })} placeholder="Например: Первое знакомство с Элизабет" />
                    </label>
                    <label className="aichatter-field-label">
                      <span>Когда AI должен отправить этот кружок</span>
                      <small>Напишите конкретное условие: на каком этапе, после какой реплики клиента и с какой целью выбирать этот тег. Это не текст сообщения клиенту, а внутренняя инструкция для AI.</small>
                      <textarea className="admin-textarea aichatter-funnel-description" value={item.description || ''} onChange={(event) => updateFunnelItem(item.media_key, { description: event.target.value })} placeholder="Например: отправить при первом знакомстве, когда клиент ещё не знает Элизабет и не видел презентацию…" />
                    </label>
                    <div className="aichatter-funnel-file-row">
                      <div className="aichatter-funnel-file-meta">
                        <span className="aichatter-field-caption">MP4-файл для Telegram-кружка</span>
                        <span className={`aichatter-pill ${item.file_exists ? 'ok' : 'off'}`}>{item.file_exists ? `${item.file_name} · ${formatBytes(item.file_size)}` : 'Файл не загружен'}</span>
                        <small className="admin-muted">Уникальных отправок клиентам: {item.sent_count || 0}</small>
                      </div>
                      <label className="admin-btn-outline aichatter-file-button">
                        {uploadingKey === item.media_key ? 'Загрузка…' : item.file_exists ? 'Заменить MP4' : 'Загрузить MP4'}
                        <input type="file" accept="video/mp4,.mp4" disabled={Boolean(uploadingKey)} onChange={(event) => uploadFunnelMedia(item.media_key, event.target.files?.[0])} />
                      </label>
                    </div>
                  </div>
                </article>
              ))}
              {!funnelItems.length && <div className="admin-muted">Шаги воронки пока не загружены</div>}
            </div>
          </section>
          <button className="admin-btn aichatter-save" disabled={funnelSaving} onClick={saveFunnel}>{funnelSaving ? 'Сохранение…' : 'Сохранить порядок и кружки'}</button>
        </div>
      )}

      {section === 'users' && (
        <div className="aichatter-stack">
          <section className="admin-card">
            <div className="aichatter-section-head"><div><h3 className="admin-section-title">Пользователи и диалоги</h3><div className="admin-muted">Найдено: {usersTotal}</div></div></div>
            <div className="aichatter-inline-form"><input className="admin-input" placeholder="ID, username, имя или Trader ID" value={userSearch} onChange={(event) => setUserSearch(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && loadUsers()} /><button className="admin-btn" onClick={() => loadUsers()}>Найти</button></div>
            <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Пользователь</th><th>Этап</th><th>Статус</th><th>Сообщения</th><th /></tr></thead><tbody>{users.map((user) => <tr key={user.tg_user_id}><td><strong>{user.first_name || 'Без имени'}</strong><br /><span className="admin-muted">@{user.username || '—'} · {user.tg_user_id}</span></td><td>{user.stage || 'new'}<br /><span className="admin-muted">Trader: {user.trader_id || '—'}</span></td><td><span className={`aichatter-pill ${user.bot_active ? 'ok' : 'off'}`}>{user.bot_active ? 'Бот включён' : 'Отключён'}</span><br /><span className="admin-muted">R: {user.registration_status ? 'да' : 'нет'} · D: {user.deposit_status ? 'да' : 'нет'}</span></td><td>{user.messages_count || 0}</td><td><button className="admin-btn-outline" onClick={() => openConversation(user)}>Открыть</button></td></tr>)}</tbody></table></div>
          </section>
          {selectedUser && <section className="admin-card"><div className="aichatter-section-head"><div><h3 className="admin-section-title">Диалог с {selectedUser.first_name || selectedUser.tg_user_id}</h3><div className="admin-muted">{selectedUser.notes || 'Без заметок'}</div></div><div className="aichatter-conversation-actions"><button className={`admin-btn-outline ${selectedUser.bot_active ? 'danger' : ''}`} onClick={() => toggleUser(selectedUser)}>{selectedUser.bot_active ? 'Отключить бота' : 'Включить бота'}</button><button className="admin-btn-outline danger" disabled={clearingHistory} onClick={() => clearConversationHistory(selectedUser)}>{clearingHistory ? 'Очистка…' : 'Очистить историю'}</button></div></div><div className="aichatter-conversation">{messages.length ? messages.map((message) => <div key={message.id} className={`aichatter-message ${message.direction === 'out' ? 'out' : 'in'}`}><div>{message.text || '—'}</div><small>{message.is_business ? 'Business · ' : ''}{formatDate(message.created_at)}</small></div>) : <div className="admin-muted">Сообщений пока нет</div>}</div></section>}
        </div>
      )}

      {section === 'triggers' && <section className="admin-card"><h3 className="admin-section-title">Стоп-триггеры</h3><p className="admin-muted">Если клиент использует одну из фраз, бот останавливает автоматический диалог и уведомляет администраторов.</p><div className="aichatter-inline-form"><input className="admin-input" placeholder="Несколько фраз через запятую" value={triggerInput} onChange={(event) => setTriggerInput(event.target.value)} /><button className="admin-btn" onClick={addTriggers}>Добавить</button></div><div className="aichatter-tags">{triggers.map((trigger) => <button key={trigger} title="Удалить" onClick={() => saveTriggers(triggers.filter((item) => item !== trigger))}>{trigger}<span>×</span></button>)}</div></section>}

      {section === 'postbacks' && <section className="admin-card"><h3 className="admin-section-title">Ссылки Pocket Option</h3><p className="admin-muted">Создайте три postback-события в партнёрском кабинете. Для депозитов обязательно передавайте transaction_id.</p>{['reg', 'dep1', 'dep'].map((code) => <label key={code}>{code}<input className="admin-input" readOnly value={pocketPostbackConfig.urls?.[code] || 'Секрет ещё не настроен на сервере'} onFocus={(event) => event.target.select()} /></label>)}<p className="admin-muted">Общие параметры: click_id, site_id, trader_id, cid, ac. Регистрация: country, promo, device_type. Депозиты: sumdep, transaction_id.</p></section>}
      {section === 'postbacks' && <div className="aichatter-stack"><section className="admin-card"><div className="aichatter-section-head"><h3 className="admin-section-title">События postback</h3><div className="aichatter-inline-form compact"><select className="admin-input compact" value={postbackFilter} onChange={(event) => setPostbackFilter(event.target.value)}><option value="">Все события</option><option value="reg">Регистрация</option><option value="dep1">Первый депозит</option><option value="dep">Депозит</option><option value="wdr">Вывод</option><option value="commission">Комиссия</option></select><button className="admin-btn-outline" onClick={loadPostbacks}>Обновить</button></div></div><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Дата</th><th>Событие</th><th>Пользователь</th><th>Trader ID</th><th>Сумма</th><th>Статус</th></tr></thead><tbody>{postbacks.map((item) => <tr key={item.id}><td>{formatDate(item.created_at)}</td><td>{item.event_code}</td><td>{item.tg_user_id || '—'}</td><td>{item.trader_id || '—'}</td><td>{formatMoney(item.commission || item.sumdep || item.wdr_sum)}</td><td>{item.status || '—'}</td></tr>)}</tbody></table></div></section><section className="admin-card"><h3 className="admin-section-title">Ручная комиссия</h3><div className="aichatter-inline-form"><input className="admin-input" type="date" value={manualDate} onChange={(event) => setManualDate(event.target.value)} /><input className="admin-input" type="number" min="0" step="0.01" placeholder="Сумма" value={manualAmount} onChange={(event) => setManualAmount(event.target.value)} /><button className="admin-btn" onClick={saveManualCommission}>Сохранить</button></div>{statistics.manual_commissions.length > 0 && <div className="aichatter-manual-list">{statistics.manual_commissions.map((item) => <span key={item.stat_date}>{String(item.stat_date).slice(0, 10)}: <strong>{formatMoney(item.amount)}</strong></span>)}</div>}</section></div>}

    </div>
  );
}
