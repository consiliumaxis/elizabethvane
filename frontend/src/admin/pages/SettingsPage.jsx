import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';

const ACCESS_STORAGE_KEY = 'admin_system_access_enabled';
const STREAM_SIGNALS = ['BUY', 'SELL'];
const INDICATOR_SIGNAL_OPTIONS = ['AUTO', 'BUY', 'SELL', 'NEUTRAL'];
const STREAM_ANALYSIS_TYPES = [
  { key: 'forex', title: 'Forex' },
  { key: 'binary', title: 'Binary' },
];
const FOREX_STREAM_MARKETS = [
  { key: 'currencies', title: 'Валюты' },
  { key: 'indices', title: 'Индексы' },
  { key: 'commodities', title: 'Сырье' },
  { key: 'stocks', title: 'Акции' },
];
const BINARY_STREAM_MARKETS = [
  { key: 'forex', title: 'Forex' },
  { key: 'otc', title: 'OTC' },
  { key: 'commodities', title: 'Сырье' },
  { key: 'stocks', title: 'Акции' },
  { key: 'crypto', title: 'Crypto' },
];

const normalizeIndicatorKey = (value) =>
  String(value || '')
    .trim()
    .toUpperCase()
    .replace(/[\s_-]+/g, '');

const splitCsv = (value) =>
  String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

const parseStrategyIndicators = (strategy) => {
  if (!strategy) return [];
  const names = splitCsv(strategy.indicators_list);
  const keys = splitCsv(strategy.indicator_keys);

  const rows = [];
  if (keys.length) {
    keys.forEach((key, idx) => {
      rows.push({
        key,
        name: names[idx] || key,
      });
    });
  } else {
    names.forEach((name) => {
      rows.push({ key: name, name });
    });
  }

  const unique = [];
  const seen = new Set();
  rows.forEach((item) => {
    const norm = normalizeIndicatorKey(item.key || item.name);
    if (!norm || seen.has(norm)) return;
    seen.add(norm);
    unique.push({ ...item, norm });
  });

  return unique;
};

const toMaybeNumber = (value) => {
  if (value === null || value === undefined) return null;
  const raw = String(value).trim();
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
};

const formatLevel = (value) => {
  const numeric = toMaybeNumber(value);
  if (numeric === null) return '---';
  return numeric.toFixed(5);
};

const hashString = (input) => {
  const str = String(input || '');
  let hash = 0;
  for (let i = 0; i < str.length; i += 1) {
    hash = (hash * 31 + str.charCodeAt(i)) % 1000000007;
  }
  return hash;
};

const buildPreviewSignals = ({
  indicators,
  forcedSignal,
  indicatorMode,
  indicatorOverrides,
  seed,
}) => {
  const prepared = (indicators || []).map((indicator, idx) => ({
    ...indicator,
    idx,
    signal: 'NEUTRAL',
  }));

  if (!prepared.length) {
    return {
      indicators: [],
      votes: { BUY: 0, SELL: 0, NEUTRAL: 0 },
      percents: { buy: 0, sell: 0, neutral: 0 },
      pointer: 50,
    };
  }

  const opposite = forcedSignal === 'BUY' ? 'SELL' : 'BUY';
  const manualMode = indicatorMode === 'manual';

  const autoIndexes = [];
  prepared.forEach((item) => {
    const overridden = manualMode ? indicatorOverrides[item.norm] : null;
    if (overridden && overridden !== 'AUTO') {
      item.signal = overridden;
    } else {
      autoIndexes.push(item.idx);
    }
  });

  autoIndexes.forEach((index) => {
    const item = prepared[index];
    const h = hashString(`${seed}|${item.norm}|${index}`) % 100;
    if (h < 66) {
      item.signal = forcedSignal;
    } else if (h < 84) {
      item.signal = 'NEUTRAL';
    } else {
      item.signal = opposite;
    }
  });

  let forcedCount = prepared.filter((item) => item.signal === forcedSignal).length;
  const requiredMajority = Math.floor(prepared.length / 2) + 1;

  if (forcedCount < requiredMajority && autoIndexes.length) {
    const candidates = autoIndexes
      .filter((index) => prepared[index].signal !== forcedSignal)
      .sort((a, b) => {
        const ah = hashString(`${seed}|boost|${prepared[a].norm}|${a}`);
        const bh = hashString(`${seed}|boost|${prepared[b].norm}|${b}`);
        return bh - ah;
      });

    candidates.forEach((index) => {
      if (forcedCount >= requiredMajority) return;
      prepared[index].signal = forcedSignal;
      forcedCount += 1;
    });
  }

  const votes = { BUY: 0, SELL: 0, NEUTRAL: 0 };
  prepared.forEach((item) => {
    votes[item.signal] = (votes[item.signal] || 0) + 1;
  });

  const total = prepared.length || 1;
  const percents = {
    buy: Math.round((votes.BUY / total) * 100),
    sell: Math.round((votes.SELL / total) * 100),
    neutral: Math.round((votes.NEUTRAL / total) * 100),
  };
  const pointer = 50 + percents.buy * 0.5 - percents.sell * 0.5;

  return {
    indicators: prepared,
    votes,
    percents,
    pointer,
  };
};

export default function SettingsPage({ adminUser }) {
  const [activeSection, setActiveSection] = useState('menu');
  const [model, setModel] = useState('gpt-4o-mini');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [admins, setAdmins] = useState([]);
  const [grantId, setGrantId] = useState('');

  const [streamEnabled, setStreamEnabled] = useState(false);
  const [streamScope, setStreamScope] = useState('all');
  const [streamStrategyId, setStreamStrategyId] = useState('');
  const [streamSignal, setStreamSignal] = useState('BUY');
  const [streamLevelsMode, setStreamLevelsMode] = useState('auto');
  const [streamManualSL, setStreamManualSL] = useState('');
  const [streamManualTP, setStreamManualTP] = useState('');
  const [streamIndicatorMode, setStreamIndicatorMode] = useState('auto');
  const [streamIndicatorOverrides, setStreamIndicatorOverrides] = useState({});
  const [streamStrategies, setStreamStrategies] = useState([]);
  const [streamAnalysisType, setStreamAnalysisType] = useState('forex');
  const [streamMarket, setStreamMarket] = useState('currencies');
  const [streamSymbol, setStreamSymbol] = useState('');
  const [streamManualPrice, setStreamManualPrice] = useState('');
  const [streamMarketOptions, setStreamMarketOptions] = useState([]);
  const [streamMarketLoading, setStreamMarketLoading] = useState(false);

  const [systemAccessEnabled, setSystemAccessEnabled] = useState(true);
  const [channelUrl, setChannelUrl] = useState('');
  const [supportUrl, setSupportUrl] = useState('');
  const [pocketPartnerId, setPocketPartnerId] = useState('');
  const [pocketApiToken, setPocketApiToken] = useState('');
  const [pocketApiTokenMasked, setPocketApiTokenMasked] = useState('');
  const [pocketApiTokenConfigured, setPocketApiTokenConfigured] = useState(false);

  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(ACCESS_STORAGE_KEY);
      if (saved === '0') {
        setSystemAccessEnabled(false);
      }
    } catch {}
  }, []);

  const loadAll = useCallback(async () => {
    setError('');
    try {
      const [settingsRes, adminsRes] = await Promise.all([
        apiAdminFetchJson('/api/admin/settings'),
        apiAdminFetchJson('/api/admin/admins'),
      ]);

      const ai = settingsRes?.settings?.ai || {};
      setModel(ai.model || 'gpt-4o-mini');
      setSystemPrompt(ai.system_prompt || '');
      setAdmins(adminsRes.admins || []);

      const streams = settingsRes?.settings?.streams || {};
      setStreamEnabled(Boolean(Number(streams.is_enabled || 0)));
      setStreamScope((streams.scope || 'all') === 'strategy' ? 'strategy' : 'all');
      setStreamStrategyId(
        streams.strategy_id !== null && streams.strategy_id !== undefined
          ? String(streams.strategy_id)
          : ''
      );
      const forced = String(streams.forced_signal || 'BUY').toUpperCase();
      setStreamSignal(STREAM_SIGNALS.includes(forced) ? forced : 'BUY');

      const levelsMode = String(streams.levels_mode || 'auto').toLowerCase();
      setStreamLevelsMode(levelsMode === 'manual' ? 'manual' : 'auto');
      setStreamManualSL(streams.manual_conservative_sl !== null && streams.manual_conservative_sl !== undefined ? String(streams.manual_conservative_sl) : '');
      setStreamManualTP(streams.manual_take_profit !== null && streams.manual_take_profit !== undefined ? String(streams.manual_take_profit) : '');

      const indicatorMode = String(streams.indicator_mode || 'auto').toLowerCase();
      setStreamIndicatorMode(indicatorMode === 'manual' ? 'manual' : 'auto');

      const overridesRaw = streams.indicator_overrides;
      const nextOverrides = {};
      if (overridesRaw && typeof overridesRaw === 'object') {
        Object.entries(overridesRaw).forEach(([rawKey, rawSignal]) => {
          const norm = normalizeIndicatorKey(rawKey);
          const signal = String(rawSignal || '').toUpperCase();
          if (!norm) return;
          if (signal === 'BUY' || signal === 'SELL' || signal === 'NEUTRAL') {
            nextOverrides[norm] = signal;
          }
        });
      }
      setStreamIndicatorOverrides(nextOverrides);
      const emulationType = String(streams.emulation_analysis_type || 'forex').trim().toLowerCase();
      const nextAnalysisType = STREAM_ANALYSIS_TYPES.some((item) => item.key === emulationType) ? emulationType : 'forex';
      const marketOptions = nextAnalysisType === 'binary' ? BINARY_STREAM_MARKETS : FOREX_STREAM_MARKETS;
      const fallbackMarket = nextAnalysisType === 'binary' ? 'forex' : 'currencies';
      const emulationMarket = String(streams.emulation_market || '').trim().toLowerCase();
      setStreamAnalysisType(nextAnalysisType);
      setStreamMarket(marketOptions.some((item) => item.key === emulationMarket) ? emulationMarket : fallbackMarket);
      setStreamSymbol(streams.emulation_symbol || '');
      setStreamManualPrice(streams.emulation_price !== null && streams.emulation_price !== undefined ? String(streams.emulation_price) : '');

      setStreamStrategies(settingsRes?.settings?.stream_strategies || []);

      const support = settingsRes?.settings?.support || {};
      setChannelUrl(support.channel_url || '');
      setSupportUrl(support.support_url || '');

      const pocket = settingsRes?.settings?.pocket_api || {};
      setPocketPartnerId(pocket.partner_id || '');
      setPocketApiToken('');
      setPocketApiTokenMasked(pocket.api_token_masked || '');
      setPocketApiTokenConfigured(Boolean(Number(pocket.api_token_configured || 0)));
    } catch (e) {
      setError(e.message || 'Не удалось загрузить настройки');
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    let cancelled = false;
    const loadMarketOptions = async () => {
      if (activeSection !== 'streams' || !streamMarket) {
        return;
      }
      setStreamMarketLoading(true);
      try {
        const res = await apiAdminFetchJson(`/api/admin/stream-assets?analysis_type=${encodeURIComponent(streamAnalysisType)}&market=${encodeURIComponent(streamMarket)}`);
        if (!cancelled) {
          setStreamMarketOptions(Array.isArray(res?.pairs) ? res.pairs : []);
        }
      } catch {
        if (!cancelled) {
          setStreamMarketOptions([]);
        }
      } finally {
        if (!cancelled) {
          setStreamMarketLoading(false);
        }
      }
    };
    loadMarketOptions();
    return () => {
      cancelled = true;
    };
  }, [activeSection, streamAnalysisType, streamMarket]);

  const activeStreamMarkets = useMemo(
    () => (streamAnalysisType === 'binary' ? BINARY_STREAM_MARKETS : FOREX_STREAM_MARKETS),
    [streamAnalysisType]
  );

  const selectedStreamMarketTitle = useMemo(() => {
    return activeStreamMarkets.find((item) => item.key === streamMarket)?.title || streamMarket || 'Market';
  }, [activeStreamMarkets, streamMarket]);

  const selectedStrategy = useMemo(
    () => streamStrategies.find((item) => String(item.id) === String(streamStrategyId)) || null,
    [streamStrategies, streamStrategyId]
  );

  const previewStrategy = useMemo(() => {
    if (streamScope === 'strategy' && selectedStrategy) {
      return selectedStrategy;
    }
    return streamStrategies[0] || null;
  }, [selectedStrategy, streamScope, streamStrategies]);

  const strategyIndicators = useMemo(
    () => parseStrategyIndicators(selectedStrategy),
    [selectedStrategy]
  );

  const previewIndicatorsBase = useMemo(() => {
    const parsed = parseStrategyIndicators(previewStrategy);
    if (parsed.length) return parsed;
    return [
      { key: 'RSI', name: 'RSI', norm: 'RSI' },
      { key: 'MACD', name: 'MACD', norm: 'MACD' },
      { key: 'EMA50', name: 'EMA50', norm: 'EMA50' },
      { key: 'EMA200', name: 'EMA200', norm: 'EMA200' },
      { key: 'ADX', name: 'ADX', norm: 'ADX' },
      { key: 'DMI', name: 'DMI', norm: 'DMI' },
      { key: 'ATR', name: 'ATR', norm: 'ATR' },
      { key: 'ICHIMOKU', name: 'Ichimoku', norm: 'ICHIMOKU' },
    ];
  }, [previewStrategy]);

  const previewData = useMemo(() => {
    const effectiveIndicatorMode = streamScope === 'strategy' ? streamIndicatorMode : 'auto';
    return buildPreviewSignals({
      indicators: previewIndicatorsBase,
      forcedSignal: streamSignal,
      indicatorMode: effectiveIndicatorMode,
      indicatorOverrides: streamIndicatorOverrides,
      seed: `${streamSignal}|${streamScope}|${streamStrategyId || 'all'}`,
    });
  }, [previewIndicatorsBase, streamScope, streamSignal, streamStrategyId, streamIndicatorMode, streamIndicatorOverrides]);

  const saveSettings = async (source = 'all') => {
    const shouldSaveStreams = source === 'streams' || source === 'all';
    const shouldSaveSupport = source === 'support' || source === 'all';
    const shouldSavePocket = source === 'pocket' || source === 'all';

    if (shouldSaveStreams && streamEnabled && streamScope === 'strategy' && !streamStrategyId) {
      setError('Выберите стратегию для стрима');
      return;
    }

    const manualSL = toMaybeNumber(streamManualSL);
    const manualTP = toMaybeNumber(streamManualTP);
    const emulationPrice = toMaybeNumber(streamManualPrice);
    if (shouldSaveStreams && streamEnabled && streamLevelsMode === 'manual' && (manualSL === null || manualTP === null)) {
      setError('Для ручных уровней нужно указать Conservative SL и Target (Take Profit)');
      return;
    }
    if (shouldSaveStreams && streamManualPrice.trim() && emulationPrice === null) {
      setError('Текущая цена должна быть числом');
      return;
    }

    setSaving(true);
    setError('');
    setStatus('');

    try {
      const payload = {
        ai: {
          model: model.trim(),
          system_prompt: systemPrompt,
        },
      };

      if (shouldSaveStreams) {
        payload.streams = {
          is_enabled: streamEnabled,
          scope: streamScope,
          strategy_id: streamScope === 'strategy' ? Number(streamStrategyId) : null,
          forced_signal: streamSignal,
          levels_mode: streamLevelsMode,
          manual_conservative_sl: streamLevelsMode === 'manual' ? manualSL : null,
          manual_take_profit: streamLevelsMode === 'manual' ? manualTP : null,
          indicator_mode: streamScope === 'strategy' ? streamIndicatorMode : 'auto',
          indicator_overrides:
            streamScope === 'strategy' && streamIndicatorMode === 'manual'
              ? streamIndicatorOverrides
              : {},
          emulation_analysis_type: streamAnalysisType,
          emulation_market: streamSymbol.trim() ? streamMarket : '',
          emulation_symbol: streamSymbol.trim(),
          emulation_price: emulationPrice,
          emulation_strategy_id: streamScope === 'strategy' && streamStrategyId ? Number(streamStrategyId) : null,
        };
      }

      if (shouldSaveSupport) {
        payload.support = {
          channel_url: channelUrl.trim(),
          support_url: supportUrl.trim(),
        };
      }

      if (shouldSavePocket) {
        payload.pocket_api = {
          partner_id: pocketPartnerId.trim(),
          api_token: pocketApiToken.trim(),
        };
      }

      await apiAdminFetchJson('/api/admin/settings', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      if (source === 'ai') {
        setStatus('Настройки AI чата сохранены');
      } else if (source === 'streams') {
        setStatus('Настройки стримов сохранены');
      } else if (source === 'support') {
        setStatus('Ссылки поддержки сохранены');
      } else if (source === 'pocket') {
        setStatus('Pocket API сохранен');
        setPocketApiToken('');
        await loadAll();
      } else {
        setStatus('Настройки сохранены');
      }
    } catch (e) {
      setError(e.message || 'Не удалось сохранить настройки');
    } finally {
      setSaving(false);
    }
  };

  const grantAdmin = async () => {
    const userId = Number(grantId);
    if (!userId) return;

    setError('');
    setStatus('');
    try {
      await apiAdminFetchJson('/api/admin/admins/grant', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId }),
      });
      setGrantId('');
      setStatus(`Админка выдана: ${userId}`);
      await loadAll();
    } catch (e) {
      setError(e.message || 'Не удалось выдать админку');
    }
  };

  const revokeAdmin = async (userId) => {
    setError('');
    setStatus('');
    try {
      await apiAdminFetchJson('/api/admin/admins/revoke', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId }),
      });
      setStatus(`Админка снята: ${userId}`);
      await loadAll();
    } catch (e) {
      setError(e.message || 'Не удалось снять админку');
    }
  };

  const toggleSystemAccess = () => {
    const next = !systemAccessEnabled;
    setSystemAccessEnabled(next);
    setError('');
    setStatus(next ? 'Доступ к системе включен (frontend fallback)' : 'Доступ к системе выключен (frontend fallback)');
    try {
      window.localStorage.setItem(ACCESS_STORAGE_KEY, next ? '1' : '0');
    } catch {}
  };

  const setIndicatorSignal = (indicatorNorm, signal) => {
    setStreamIndicatorOverrides((prev) => {
      const next = { ...prev };
      if (signal === 'AUTO') {
        delete next[indicatorNorm];
      } else {
        next[indicatorNorm] = signal;
      }
      return next;
    });
  };

  const cards = useMemo(
    () => [
      {
        key: 'streams',
        icon: '📡',
        title: 'Стримы',
        subtitle: streamEnabled ? 'Fallback включен' : 'Fallback выключен',
      },
      {
        key: 'ai',
        icon: '🤖',
        title: 'AI чат',
        subtitle: `Модель: ${model || '-'}`,
      },
      {
        key: 'access',
        icon: systemAccessEnabled ? '✅' : '⛔',
        title: 'Доступ к системе',
        subtitle: systemAccessEnabled ? 'Доступ открыт' : 'Доступ ограничен',
      },
      {
        key: 'support',
        icon: '🔗',
        title: 'Управление ссылками',
        subtitle: channelUrl || supportUrl ? 'Ссылки настроены' : 'Ссылки не заданы',
      },
      {
        key: 'pocket',
        icon: '🔑',
        title: 'API',
        subtitle: pocketPartnerId || pocketApiTokenConfigured ? `Pocket: ${pocketPartnerId || '-'} ${pocketApiTokenMasked || ''}` : 'Pocket API не настроен',
      },
      {
        key: 'admins',
        icon: '🛡️',
        title: 'Выдать админку',
        subtitle: `Текущих админов: ${admins.length}`,
      },
    ],
    [admins.length, channelUrl, model, pocketApiTokenConfigured, pocketApiTokenMasked, pocketPartnerId, streamEnabled, supportUrl, systemAccessEnabled]
  );

  const goMenu = () => {
    setActiveSection('menu');
    setError('');
    setStatus('');
  };

  if (activeSection === 'menu') {
    return (
      <div className="admin-page">
        <div className="admin-card">
          <h3 className="admin-section-title">Настройки</h3>
          <div className="admin-muted">Откройте карточку нужного раздела</div>

          <div className="admin-settings-menu-grid">
            {cards.map((card) => (
              <button
                key={card.key}
                type="button"
                className="admin-settings-menu-card"
                onClick={() => setActiveSection(card.key)}
              >
                <div className="admin-settings-menu-head">
                  <span className="admin-settings-menu-icon">{card.icon}</span>
                  <span className="admin-settings-menu-title">{card.title}</span>
                </div>
                <div className="admin-settings-menu-subtitle">{card.subtitle}</div>
              </button>
            ))}
          </div>
        </div>

        {error ? <div className="admin-error">{error}</div> : null}
        {status ? <div className="admin-success">{status}</div> : null}
      </div>
    );
  }

  if (activeSection === 'ai') {
    return (
      <div className="admin-card admin-settings-detail">
        <div className="admin-row-between">
          <h3 className="admin-section-title">AI чат</h3>
          <button className="admin-btn-outline" onClick={goMenu}>← К карточкам</button>
        </div>

        <div className="admin-field">
          <label className="admin-label">Модель</label>
          <input className="admin-input" value={model} onChange={(e) => setModel(e.target.value)} />
        </div>

        <div className="admin-field">
          <label className="admin-label">Системный промпт</label>
          <textarea
            className="admin-textarea"
            rows={8}
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
          />
        </div>

        <div className="admin-row-actions">
          <button className="admin-btn" onClick={() => saveSettings('ai')} disabled={saving}>
            {saving ? 'Сохранение...' : 'Сохранить AI чат'}
          </button>
        </div>

        {error ? <div className="admin-error">{error}</div> : null}
        {status ? <div className="admin-success">{status}</div> : null}
      </div>
    );
  }

  if (activeSection === 'streams') {
    const previewVerdict = streamEnabled ? streamSignal : 'OFF';

    return (
      <div className="admin-card admin-settings-detail admin-streams-detail">
        <div className="admin-row-between">
          <h3 className="admin-section-title">Стримы</h3>
          <button className="admin-btn-outline" onClick={goMenu}>← К карточкам</button>
        </div>

        <div className="admin-stream-guide">
          <div>Этот раздел управляет fallback-режимом сигнала, когда админ задаёт приоритетное направление.</div>
          <div>Обязательно: выберите направление BUY/SELL. Для режима «По выбранной стратегии» укажите стратегию.</div>
          <div>Опционально: ручные уровни SL/TP и ручные сигналы индикаторов. Если пропустить, система рассчитает автоматически.</div>
        </div>

        <div className="admin-stream-block">
          <label className="admin-label">Режим стрима</label>
          <label className="admin-switch-line">
            <input
              type="checkbox"
              checked={streamEnabled}
              onChange={(e) => setStreamEnabled(e.target.checked)}
            />
            <span>{streamEnabled ? 'Включен' : 'Выключен'}</span>
          </label>
        </div>

        <div className="admin-stream-block">
          <label className="admin-label">Применять fallback</label>
          <div className="admin-pill-group">
            <button
              type="button"
              className={`admin-pill-btn ${streamScope === 'all' ? 'active' : ''}`}
              onClick={() => setStreamScope('all')}
            >
              По всем стратегиям
            </button>
            <button
              type="button"
              className={`admin-pill-btn ${streamScope === 'strategy' ? 'active' : ''}`}
              onClick={() => setStreamScope('strategy')}
            >
              По выбранной стратегии
            </button>
          </div>
        </div>

        {streamScope === 'strategy' ? (
          <div className="admin-stream-block">
            <label className="admin-label">Стратегия</label>
            <select
              className="admin-input"
              value={streamStrategyId}
              onChange={(e) => setStreamStrategyId(e.target.value)}
            >
              <option value="">Выберите стратегию</option>
              {streamStrategies.map((strategy) => (
                <option key={strategy.id} value={strategy.id}>
                  {(strategy.icon || '📌') + ' ' + strategy.name}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div className="admin-stream-block admin-stream-emulation-block">
          <label className="admin-label">Актив и цена для эмуляции записи</label>
          <div className="admin-stream-hint">
            Сначала выберите тип сигнала. Для Forex подтягиваются рынки и пары из Forex-раздела: валюты, индексы, сырье и акции. Для Binary подтягиваются binary-рынки с payout.
          </div>
          <div className="admin-stream-type-row">
            {STREAM_ANALYSIS_TYPES.map((type) => (
              <button
                key={type.key}
                type="button"
                className={`admin-pill-btn ${streamAnalysisType === type.key ? 'active' : ''}`}
                onClick={() => {
                  setStreamAnalysisType(type.key);
                  setStreamMarket(type.key === 'binary' ? 'forex' : 'currencies');
                  setStreamSymbol('');
                }}
              >
                {type.title}
              </button>
            ))}
          </div>
          <div className="admin-stream-hint compact">
            Можно оставить актив пустым: тогда пользовательский актив и live-цена останутся как обычно. Если указать актив, именно он попадёт в карточку и историю сигнала.
          </div>
          <div className="admin-stream-emulation-grid">
            <div className="admin-field">
              <label className="admin-label">Рынок</label>
              <select
                className="admin-input"
                value={streamMarket}
                onChange={(e) => {
                  setStreamMarket(e.target.value);
                  setStreamSymbol('');
                }}
              >
                {activeStreamMarkets.map((market) => (
                  <option key={market.key} value={market.key}>{market.title}</option>
                ))}
              </select>
            </div>
            <div className="admin-field">
              <label className="admin-label">Актив</label>
              <input
                className="admin-input"
                list={`stream-asset-options-${streamAnalysisType}-${streamMarket}`}
                placeholder={streamMarketLoading ? 'Загружаем активы...' : streamAnalysisType === 'binary' ? 'Например Netflix OTC' : 'Например AUD/CHF'}
                value={streamSymbol}
                onChange={(e) => setStreamSymbol(e.target.value)}
              />
              <datalist id={`stream-asset-options-${streamAnalysisType}-${streamMarket}`}>
                {streamMarketOptions.map((asset) => (
                  <option key={`${asset.pair}-${asset.payout || asset.label || 'np'}`} value={asset.pair}>
                    {asset.payout ? `${asset.payout}%` : asset.label || selectedStreamMarketTitle}
                  </option>
                ))}
              </datalist>
            </div>
            <div className="admin-field">
              <label className="admin-label">Текущая цена</label>
              <input
                className="admin-input"
                inputMode="decimal"
                placeholder="Автоматически, если пусто"
                value={streamManualPrice}
                onChange={(e) => setStreamManualPrice(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="admin-stream-block">
          <label className="admin-label">Итоговый вердикт системы</label>
          <div className="admin-pill-group">
            {STREAM_SIGNALS.map((signal) => (
              <button
                key={signal}
                type="button"
                className={`admin-pill-btn ${streamSignal === signal ? 'active' : ''}`}
                onClick={() => setStreamSignal(signal)}
              >
                {signal}
              </button>
            ))}
          </div>
        </div>

        <div className="admin-stream-block">
          <label className="admin-label">Conservative SL и Target (Take Profit)</label>
          <div className="admin-pill-group">
            <button
              type="button"
              className={`admin-pill-btn ${streamLevelsMode === 'auto' ? 'active' : ''}`}
              onClick={() => setStreamLevelsMode('auto')}
            >
              Автоматически
            </button>
            <button
              type="button"
              className={`admin-pill-btn ${streamLevelsMode === 'manual' ? 'active' : ''}`}
              onClick={() => setStreamLevelsMode('manual')}
            >
              Вручную
            </button>
          </div>
          {streamLevelsMode === 'manual' ? (
            <div className="admin-stream-levels-grid">
              <div className="admin-field">
                <label className="admin-label">Conservative SL</label>
                <input
                  className="admin-input"
                  inputMode="decimal"
                  placeholder="Например 1.23456"
                  value={streamManualSL}
                  onChange={(e) => setStreamManualSL(e.target.value)}
                />
              </div>
              <div className="admin-field">
                <label className="admin-label">Target (Take Profit)</label>
                <input
                  className="admin-input"
                  inputMode="decimal"
                  placeholder="Например 1.24567"
                  value={streamManualTP}
                  onChange={(e) => setStreamManualTP(e.target.value)}
                />
              </div>
            </div>
          ) : (
            <div className="admin-muted">Уровни будут взяты из стандартного анализа автоматически.</div>
          )}
        </div>

        <div className="admin-stream-block">
          <label className="admin-label">Сигналы индикаторов (для выбранной стратегии)</label>
          {streamScope !== 'strategy' ? (
            <div className="admin-muted">Этот блок доступен только в режиме «По выбранной стратегии».</div>
          ) : (
            <>
              <div className="admin-pill-group">
                <button
                  type="button"
                  className={`admin-pill-btn ${streamIndicatorMode === 'auto' ? 'active' : ''}`}
                  onClick={() => setStreamIndicatorMode('auto')}
                >
                  Автоматически
                </button>
                <button
                  type="button"
                  className={`admin-pill-btn ${streamIndicatorMode === 'manual' ? 'active' : ''}`}
                  onClick={() => setStreamIndicatorMode('manual')}
                  disabled={!selectedStrategy}
                >
                  Вручную
                </button>
              </div>

              {streamIndicatorMode === 'manual' ? (
                selectedStrategy ? (
                  strategyIndicators.length ? (
                    <div className="admin-stream-indicators-list">
                      {strategyIndicators.map((indicator) => {
                        const current = streamIndicatorOverrides[indicator.norm] || 'AUTO';
                        return (
                          <div key={indicator.norm} className="admin-stream-indicator-row">
                            <div className="admin-stream-indicator-name">{indicator.name}</div>
                            <div className="admin-stream-mini-toggle">
                              {INDICATOR_SIGNAL_OPTIONS.map((option) => (
                                <button
                                  key={option}
                                  type="button"
                                  className={`admin-stream-mini-btn ${current === option ? 'active' : ''}`}
                                  onClick={() => setIndicatorSignal(indicator.norm, option)}
                                >
                                  {option}
                                </button>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="admin-muted">У выбранной стратегии нет подключенных индикаторов.</div>
                  )
                ) : (
                  <div className="admin-muted">Сначала выберите стратегию, затем настройте индикаторы.</div>
                )
              ) : (
                <div className="admin-muted">Система сама распределит сигналы индикаторов с перевесом в выбранный вердикт.</div>
              )}
            </>
          )}
        </div>

        <div className="admin-stream-preview-card">
          <div className="admin-stream-preview-head">
            <div>
              <div className="admin-stream-preview-title">Превью итогового сигнала</div>
              <div className="admin-stream-preview-meta">
                {previewStrategy ? `${previewStrategy.icon || '📌'} ${previewStrategy.name}` : 'Без выбранной стратегии'}
                {previewStrategy?.allowed_timeframes ? ` | ${previewStrategy.allowed_timeframes}` : ''}
              </div>
              <div className="admin-stream-preview-note">
                Тип: {streamAnalysisType === 'binary' ? 'Binary' : 'Forex'} · Актив: {streamSymbol.trim() ? `${selectedStreamMarketTitle} · ${streamSymbol.trim()}` : 'как выбрал пользователь'}
                {' · '}
                Цена: {toMaybeNumber(streamManualPrice) !== null ? formatLevel(streamManualPrice) : 'live'}
              </div>
            </div>
            <div className={`admin-stream-verdict ${previewVerdict === 'BUY' ? 'buy' : previewVerdict === 'SELL' ? 'sell' : 'off'}`}>
              {previewVerdict === 'OFF' ? 'STREAM OFF' : previewVerdict}
            </div>
          </div>

          <div className="admin-stream-preview-grid">
            {previewData.indicators.map((indicator) => (
              <div key={`${indicator.norm}-${indicator.idx}`} className="admin-stream-preview-item">
                <div className="admin-stream-preview-name">{indicator.name}</div>
                <div className="admin-stream-preview-value">---</div>
                <div className={`admin-stream-preview-signal sig-${indicator.signal.toLowerCase()}`}>
                  {indicator.signal}
                </div>
              </div>
            ))}
          </div>

          <div className="admin-stream-gauge-wrap">
            <div className="admin-stream-gauge-title">Consensus</div>
            <div className="admin-stream-gauge-bar">
              <div className="admin-stream-gauge-pointer" style={{ left: `${previewData.pointer}%` }}></div>
            </div>
            <div className="admin-stream-gauge-labels">
              <span className="sell">SELL ({previewData.votes.SELL}) {previewData.percents.sell}%</span>
              <span className="neutral">NEUTRAL ({previewData.votes.NEUTRAL}) {previewData.percents.neutral}%</span>
              <span className="buy">BUY ({previewData.votes.BUY}) {previewData.percents.buy}%</span>
            </div>
          </div>

          <div className="admin-stream-levels-preview">
            <div className="admin-stream-level-row">
              <span>Conservative SL</span>
              <strong>{streamLevelsMode === 'manual' ? formatLevel(streamManualSL) : 'AUTO'}</strong>
            </div>
            <div className="admin-stream-level-row">
              <span>Target (Take Profit)</span>
              <strong>{streamLevelsMode === 'manual' ? formatLevel(streamManualTP) : 'AUTO'}</strong>
            </div>
          </div>
        </div>

        <div className="admin-row-actions admin-stream-save-row">
          <button className="admin-btn" onClick={() => saveSettings('streams')} disabled={saving}>
            {saving ? 'Сохранение...' : 'Сохранить стримы'}
          </button>
        </div>

        {error ? <div className="admin-error">{error}</div> : null}
        {status ? <div className="admin-success">{status}</div> : null}
      </div>
    );
  }

  if (activeSection === 'access') {
    return (
      <div className="admin-card admin-settings-detail">
        <div className="admin-row-between">
          <h3 className="admin-section-title">Доступ к системе</h3>
          <button className="admin-btn-outline" onClick={goMenu}>← К карточкам</button>
        </div>

        <div className="admin-field">
          <label className="admin-label">Режим доступа</label>
          <label className="admin-muted">
            <input
              type="checkbox"
              checked={systemAccessEnabled}
              onChange={toggleSystemAccess}
            />{' '}
            {systemAccessEnabled ? 'Доступ открыт' : 'Доступ ограничен'}
          </label>
        </div>

        <div className="admin-muted">
          Сейчас это временный frontend fallback. Когда подключим backend и БД под доступ, логика автоматически переедет сюда.
        </div>

        {error ? <div className="admin-error">{error}</div> : null}
        {status ? <div className="admin-success">{status}</div> : null}
      </div>
    );
  }

  if (activeSection === 'support') {
    return (
      <div className="admin-card admin-settings-detail">
        <div className="admin-row-between">
          <h3 className="admin-section-title">Управление ссылками</h3>
          <button className="admin-btn-outline" onClick={goMenu}>← К карточкам</button>
        </div>

        <div className="admin-muted">
          Эти ссылки используются в разделе поддержки: кнопка канала и кнопка личного обращения.
        </div>

        <div className="admin-field">
          <label className="admin-label">Ссылка на канал</label>
          <input
            className="admin-input"
            placeholder="https://t.me/channel"
            value={channelUrl}
            onChange={(e) => setChannelUrl(e.target.value)}
          />
        </div>

        <div className="admin-field">
          <label className="admin-label">Ссылка на личный чат / поддержку</label>
          <input
            className="admin-input"
            placeholder="https://t.me/support_username"
            value={supportUrl}
            onChange={(e) => setSupportUrl(e.target.value)}
          />
        </div>

        <div className="admin-row-actions">
          <button className="admin-btn" onClick={() => saveSettings('support')} disabled={saving}>
            {saving ? 'Сохранение...' : 'Сохранить ссылки'}
          </button>
        </div>

        {error ? <div className="admin-error">{error}</div> : null}
        {status ? <div className="admin-success">{status}</div> : null}
      </div>
    );
  }

  if (activeSection === 'pocket') {
    return (
      <div className="admin-card admin-settings-detail">
        <div className="admin-row-between">
          <h3 className="admin-section-title">API</h3>
          <button className="admin-btn-outline" onClick={goMenu}>← К карточкам</button>
        </div>

        <div className="admin-muted">
          Настройки Pocket Partners. Токен хранится на backend и показывается только маской: первые 2 и последние 2 символа.
        </div>

        <div className="admin-field">
          <label className="admin-label">ID кабинета / Partner ID</label>
          <input
            className="admin-input"
            placeholder="Например 123456"
            value={pocketPartnerId}
            onChange={(e) => setPocketPartnerId(e.target.value.replace(/[^\w.-]/g, '').slice(0, 64))}
          />
        </div>

        <div className="admin-field">
          <label className="admin-label">API token</label>
          <input
            className="admin-input"
            type="password"
            placeholder={pocketApiTokenConfigured ? `Текущий: ${pocketApiTokenMasked}. Введите новый для замены` : 'Введите API token'}
            value={pocketApiToken}
            onChange={(e) => setPocketApiToken(e.target.value)}
            autoComplete="new-password"
          />
        </div>

        <div className="admin-row-actions">
          <button className="admin-btn" onClick={() => saveSettings('pocket')} disabled={saving}>
            {saving ? 'Сохранение...' : 'Сохранить API'}
          </button>
        </div>

        {error ? <div className="admin-error">{error}</div> : null}
        {status ? <div className="admin-success">{status}</div> : null}
      </div>
    );
  }

  return (
    <div className="admin-card admin-settings-detail">
      <div className="admin-row-between">
        <h3 className="admin-section-title">Выдать админку</h3>
        <button className="admin-btn-outline" onClick={goMenu}>← К карточкам</button>
      </div>

      <div className="admin-inline-form">
        <input
          className="admin-input"
          inputMode="numeric"
          placeholder="Введите user_id"
          value={grantId}
          onChange={(e) => setGrantId(e.target.value.replace(/\D/g, ''))}
        />
        <button className="admin-btn" onClick={grantAdmin}>Выдать</button>
      </div>

      <h4 className="admin-subtitle">Текущие админы</h4>
      <div className="admin-list">
        {admins.map((item) => (
          <div className="admin-list-row" key={item.user_id}>
            <span>
              {item.first_name || item.username || 'Админ'} | {item.user_id}
            </span>
            <button
              className="admin-btn-outline"
              disabled={Number(item.user_id) === Number(adminUser?.user_id)}
              onClick={() => revokeAdmin(item.user_id)}
            >
              Забрать
            </button>
          </div>
        ))}
        {admins.length === 0 ? <div className="admin-muted">Список админов пуст</div> : null}
      </div>

      {error ? <div className="admin-error">{error}</div> : null}
      {status ? <div className="admin-success">{status}</div> : null}
    </div>
  );
}
