import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';

const STREAM_SIGNALS = ['BUY', 'SELL'];
const INDICATOR_SIGNAL_OPTIONS = ['AUTO', 'BUY', 'SELL', 'NEUTRAL'];
const ACCESS_POLICIES = [
  {
    key: 'registration',
    title: 'После регистрации',
    description: 'Сигналы откроются после Pocket registration postback.',
  },
  {
    key: 'registration_deposit',
    title: 'После регистрации и депозита',
    description: 'Считаем общую сумму FTD и повторных депозитов.',
  },
  {
    key: 'all',
    title: 'Доступ к сигналам открыт всем',
    description: 'Сигналы доступны без проверки регистрации и депозита.',
  },
];
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
const QUIZ_STEPS = [
  { key: 'experience', title: 'Вопрос 1', hint: 'Опыт в трейдинге' },
  { key: 'broker_experience', title: 'Вопрос 2', hint: 'Опыт с брокером' },
  { key: 'capital', title: 'Вопрос 3', hint: 'Капитал / депозит' },
];
const DEFAULT_QUIZ_CONFIG = {
  experience: {
    question: 'What is your trading experience?',
    options: [
      'I have no experience',
      'Less than 1 year',
      '1-2 years',
      '2-5 years',
      'More than 5 years',
      'Skip',
    ],
  },
  broker_experience: {
    question: 'Have you worked with any of these brokers before?',
    options: [
      'Broker 1',
      'Broker 2',
      'Broker 3',
      'Other broker',
      'I have not worked with a broker',
      'Skip',
    ],
  },
  capital: {
    question: 'What is your trading capital (deposit)?\nThis helps us suggest a more relevant broker setup later.\nTrading involves risk.',
    options: [
      'Up to $100',
      '$100-$1,000',
      '$1,000-$10,000',
      '$10,000-$100,000',
      '$100,000+',
      'Skip',
    ],
  },
};

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

const normalizeQuizConfig = (rawConfig) => {
  const source = rawConfig && typeof rawConfig === 'object' ? rawConfig : {};
  return QUIZ_STEPS.reduce((acc, step) => {
    const fallback = DEFAULT_QUIZ_CONFIG[step.key];
    const rawItem = source[step.key] && typeof source[step.key] === 'object' ? source[step.key] : {};
    const question = String(rawItem.question || '').trim() || fallback.question;
    const seen = new Set();
    const options = Array.isArray(rawItem.options)
      ? rawItem.options
          .map((item) => String(item || '').trim())
          .filter((item) => {
            const key = item.toLowerCase();
            if (!item || seen.has(key)) return false;
            seen.add(key);
            return true;
          })
          .slice(0, 8)
      : [];
    acc[step.key] = {
      question,
      options: options.length ? options : [...fallback.options],
    };
    return acc;
  }, {});
};

const normalizeIndicatorOverride = (entry) => {
  if (entry && typeof entry === 'object') {
    const signal = String(entry.signal || 'AUTO').toUpperCase();
    return {
      signal: INDICATOR_SIGNAL_OPTIONS.includes(signal) ? signal : 'AUTO',
      value: entry.value === null || entry.value === undefined ? '' : String(entry.value),
    };
  }
  const signal = String(entry || 'AUTO').toUpperCase();
  return {
    signal: INDICATOR_SIGNAL_OPTIONS.includes(signal) ? signal : 'AUTO',
    value: '',
  };
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
    const overridden = manualMode ? normalizeIndicatorOverride(indicatorOverrides[item.norm]).signal : null;
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
  const [openAiApiKey, setOpenAiApiKey] = useState('');
  const [openAiKeyConfigured, setOpenAiKeyConfigured] = useState(false);
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

  const [systemAccessPolicy, setSystemAccessPolicy] = useState('registration_deposit');
  const [systemMinDeposit, setSystemMinDeposit] = useState('0.00');
  const [systemRegistrationUrl, setSystemRegistrationUrl] = useState('');
  const [channelId, setChannelId] = useState('-1003584421739');
  const [channelUrl, setChannelUrl] = useState('');
  const [checkSubscriptionEnabled, setCheckSubscriptionEnabled] = useState(true);
  const [supportUrl, setSupportUrl] = useState('');
  const [quizConfig, setQuizConfig] = useState(() => normalizeQuizConfig());
  const [pocketPartnerId, setPocketPartnerId] = useState('');
  const [pocketApiToken, setPocketApiToken] = useState('');
  const [pocketApiTokenMasked, setPocketApiTokenMasked] = useState('');
  const [pocketApiTokenConfigured, setPocketApiTokenConfigured] = useState(false);

  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [saving, setSaving] = useState(false);

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
      setOpenAiApiKey('');
      setOpenAiKeyConfigured(Boolean(ai.openai_key_configured));
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
        Object.entries(overridesRaw).forEach(([rawKey, rawEntry]) => {
          const norm = normalizeIndicatorKey(rawKey);
          const entry = normalizeIndicatorOverride(rawEntry);
          if (!norm) return;
          if (entry.signal !== 'AUTO' || entry.value.trim()) {
            nextOverrides[norm] = entry;
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
      setChannelId(
        support.channel_id !== null && support.channel_id !== undefined
          ? String(support.channel_id)
          : '-1003584421739'
      );
      setChannelUrl(support.channel_url || '');
      setCheckSubscriptionEnabled(Boolean(Number(support.check_subscription_enabled ?? 1)));
      setSupportUrl(support.support_url || '');
      setQuizConfig(normalizeQuizConfig(support.quiz_config));

      const pocket = settingsRes?.settings?.pocket_api || {};
      setPocketPartnerId(pocket.partner_id || '');
      setPocketApiToken('');
      setPocketApiTokenMasked(pocket.api_token_masked || '');
      setPocketApiTokenConfigured(Boolean(Number(pocket.api_token_configured || 0)));

      const access = settingsRes?.settings?.system_access || {};
      const nextPolicy = ACCESS_POLICIES.some((item) => item.key === access.policy)
        ? access.policy
        : 'registration_deposit';
      setSystemAccessPolicy(nextPolicy);
      setSystemMinDeposit(access.min_deposit_amount !== null && access.min_deposit_amount !== undefined ? String(access.min_deposit_amount) : '0.00');
      setSystemRegistrationUrl(access.registration_url || '');
    } catch (e) {
      setError(e.message || 'Не удалось загрузить настройки');
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => loadAll(), 0);
    return () => window.clearTimeout(timer);
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
    const shouldSaveAccess = source === 'access' || source === 'all';

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
    const minDeposit = toMaybeNumber(systemMinDeposit);
    if (shouldSaveAccess && systemAccessPolicy === 'registration_deposit' && minDeposit === null) {
      setError('Минимальная сумма депозита должна быть числом');
      return;
    }
    if (shouldSaveSupport) {
      const preparedQuiz = normalizeQuizConfig(quizConfig);
      const invalidStep = QUIZ_STEPS.find((step) => {
        const item = preparedQuiz[step.key];
        return !String(item.question || '').trim() || !Array.isArray(item.options) || item.options.length === 0;
      });
      if (invalidStep) {
        setError(`Заполните вопрос и хотя бы один вариант ответа: ${invalidStep.title}`);
        return;
      }
    }

    setSaving(true);
    setError('');
    setStatus('');

    try {
      const payload = {
        ai: {
          model: model.trim(),
          system_prompt: systemPrompt,
          openai_api_key: openAiApiKey.trim(),
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
          channel_id: channelId.trim(),
          channel_url: channelUrl.trim(),
          check_subscription_enabled: checkSubscriptionEnabled,
          support_url: supportUrl.trim(),
          quiz_config: normalizeQuizConfig(quizConfig),
        };
      }

      if (shouldSavePocket) {
        payload.pocket_api = {
          partner_id: pocketPartnerId.trim(),
          api_token: pocketApiToken.trim(),
        };
      }

      if (shouldSaveAccess) {
        payload.system_access = {
          policy: systemAccessPolicy,
          min_deposit_amount: systemAccessPolicy === 'registration_deposit' ? minDeposit : 0,
          registration_url: systemRegistrationUrl.trim(),
        };
      }

      await apiAdminFetchJson('/api/admin/settings', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      if (source === 'ai') {
        setStatus('Настройки AI чата сохранены');
        setOpenAiApiKey('');
        await loadAll();
      } else if (source === 'streams') {
        setStatus('Настройки стримов сохранены');
      } else if (source === 'support') {
        setStatus('Ссылки поддержки сохранены');
      } else if (source === 'pocket') {
        setStatus('Pocket API сохранен');
        setPocketApiToken('');
        await loadAll();
      } else if (source === 'access') {
        setStatus('Настройки доступа сохранены');
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

  const setIndicatorSignal = (indicatorNorm, signal) => {
    setStreamIndicatorOverrides((prev) => {
      const next = { ...prev };
      const previous = normalizeIndicatorOverride(next[indicatorNorm]);
      const value = previous.value;
      if (signal === 'AUTO' && !value.trim()) {
        delete next[indicatorNorm];
      } else {
        next[indicatorNorm] = { ...previous, signal };
      }
      return next;
    });
  };

  const setIndicatorValue = (indicatorNorm, value) => {
    setStreamIndicatorOverrides((prev) => {
      const next = { ...prev };
      const previous = normalizeIndicatorOverride(next[indicatorNorm]);
      if (!String(value || '').trim() && previous.signal === 'AUTO') {
        delete next[indicatorNorm];
      } else {
        next[indicatorNorm] = { ...previous, value };
      }
      return next;
    });
  };

  const updateQuizQuestion = (stepKey, question) => {
    setQuizConfig((prev) => ({
      ...prev,
      [stepKey]: {
        ...normalizeQuizConfig(prev)[stepKey],
        question,
      },
    }));
  };

  const updateQuizOption = (stepKey, index, value) => {
    setQuizConfig((prev) => {
      const current = normalizeQuizConfig(prev)[stepKey];
      const options = [...current.options];
      options[index] = value;
      return {
        ...prev,
        [stepKey]: {
          ...current,
          options,
        },
      };
    });
  };

  const addQuizOption = (stepKey) => {
    setQuizConfig((prev) => {
      const current = normalizeQuizConfig(prev)[stepKey];
      if (current.options.length >= 8) return prev;
      return {
        ...prev,
        [stepKey]: {
          ...current,
          options: [...current.options, 'New option'],
        },
      };
    });
  };

  const removeQuizOption = (stepKey, index) => {
    setQuizConfig((prev) => {
      const current = normalizeQuizConfig(prev)[stepKey];
      if (current.options.length <= 1) return prev;
      return {
        ...prev,
        [stepKey]: {
          ...current,
          options: current.options.filter((_, optionIndex) => optionIndex !== index),
        },
      };
    });
  };

  const resetQuizStep = (stepKey) => {
    setQuizConfig((prev) => ({
      ...prev,
      [stepKey]: {
        question: DEFAULT_QUIZ_CONFIG[stepKey].question,
        options: [...DEFAULT_QUIZ_CONFIG[stepKey].options],
      },
    }));
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
        icon: '✅',
        title: 'Доступ к системе',
        subtitle: ACCESS_POLICIES.find((item) => item.key === systemAccessPolicy)?.title || 'Правило доступа',
      },
      {
        key: 'support',
        icon: '🔗',
        title: 'Старт и канал',
        subtitle: 'Опросник и событие подписки из Chatterfy',
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
    [admins.length, channelUrl, checkSubscriptionEnabled, model, pocketApiTokenConfigured, pocketApiTokenMasked, pocketPartnerId, streamEnabled, supportUrl, systemAccessPolicy]
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
          <label className="admin-label">OpenAI API-ключ</label>
          <input
            className="admin-input"
            type="password"
            autoComplete="off"
            value={openAiApiKey}
            onChange={(e) => setOpenAiApiKey(e.target.value)}
            placeholder={openAiKeyConfigured ? 'Ключ настроен — введите новый только для замены' : 'sk-proj-…'}
          />
          <div className="admin-muted">
            {openAiKeyConfigured ? 'Ключ сохранён и скрыт. Его используют AI-чат, EL CHATTER и основной бот Elizabeth.' : 'Ключ ещё не настроен.'}
          </div>
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
                        const current = normalizeIndicatorOverride(streamIndicatorOverrides[indicator.norm]);
                        return (
                          <div key={indicator.norm} className="admin-stream-indicator-row">
                            <div className="admin-stream-indicator-name">{indicator.name}</div>
                            <div className="admin-stream-indicator-controls">
                              <div className="admin-stream-mini-toggle">
                                {INDICATOR_SIGNAL_OPTIONS.map((option) => (
                                  <button
                                    key={option}
                                    type="button"
                                    className={`admin-stream-mini-btn ${current.signal === option ? 'active' : ''}`}
                                    onClick={() => setIndicatorSignal(indicator.norm, option)}
                                  >
                                    {option}
                                  </button>
                                ))}
                              </div>
                              <input
                                className="admin-input admin-stream-value-input"
                                value={current.value}
                                onChange={(e) => setIndicatorValue(indicator.norm, e.target.value)}
                                placeholder="Value"
                              />
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
                <div className="admin-stream-preview-value">{normalizeIndicatorOverride(streamIndicatorOverrides[indicator.norm]).value || '---'}</div>
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

        <div className="admin-muted">
          Эти переменные управляют доступом к получению сигналов. Ручная выдача доступа в карточке пользователя остается персональным override.
        </div>

        <div className="admin-access-policy-list">
          {ACCESS_POLICIES.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`admin-access-policy ${systemAccessPolicy === item.key ? 'active' : ''}`}
              onClick={() => setSystemAccessPolicy(item.key)}
            >
              <span className="admin-access-radio">{systemAccessPolicy === item.key ? '●' : '○'}</span>
              <span className="admin-access-policy-text">
                <strong>{item.title}</strong>
                <small>{item.description}</small>
              </span>
            </button>
          ))}
        </div>

        {systemAccessPolicy === 'registration_deposit' ? (
          <div className="admin-field">
            <label className="admin-label">Минимальная общая сумма депозитов, $</label>
            <input
              className="admin-input"
              value={systemMinDeposit}
              onChange={(e) => setSystemMinDeposit(e.target.value)}
              placeholder="100.00"
              inputMode="decimal"
            />
            <div className="admin-muted">
              FTD и повторные депозиты суммируются. Когда сумма станет равна или выше этого значения, доступ к сигналам откроется автоматически.
            </div>
          </div>
        ) : null}

        <div className="admin-field">
          <label className="admin-label">Ссылка регистрации на Pocket Option</label>
          <input
            className="admin-input"
            type="url"
            value={systemRegistrationUrl}
            onChange={(e) => setSystemRegistrationUrl(e.target.value)}
            placeholder="https://pocketoption.com/..."
          />
          <div className="admin-muted">
            Одна общая ссылка для переписки от аккаунта и основного бота. Шаблон {'{click_id}'} заменяется ID пользователя, остальные неизвестные параметры передаются пустыми.
          </div>
        </div>

        <div className="admin-row-actions">
          <button className="admin-btn" onClick={() => saveSettings('access')} disabled={saving}>
            {saving ? 'Сохранение...' : 'Сохранить доступ'}
          </button>
        </div>

        {error ? <div className="admin-error">{error}</div> : null}
        {status ? <div className="admin-success">{status}</div> : null}
      </div>
    );
  }

  if (activeSection === 'support') {
    const visibleQuizConfig = normalizeQuizConfig(quizConfig);
    return (
      <div className="admin-card admin-settings-detail">
        <div className="admin-row-between">
          <h3 className="admin-section-title">Старт и канал</h3>
          <button className="admin-btn-outline" onClick={goMenu}>← К карточкам</button>
        </div>

        <div className="admin-muted">
          Эти настройки используются в Telegram-воронке: стартовый опросник, кнопки ответов и переход в канал.
        </div>

        <div className="admin-funnel-quiz">
          <div className="admin-funnel-head">
            <div>
              <div className="admin-funnel-title">Стартовый опросник</div>
              <div className="admin-muted">Каждый вариант станет отдельной inline-кнопкой в Telegram.</div>
            </div>
            <button
              type="button"
              className="admin-btn-outline"
              onClick={() => setQuizConfig(normalizeQuizConfig())}
            >
              Сбросить все
            </button>
          </div>

          {QUIZ_STEPS.map((step) => {
            const item = visibleQuizConfig[step.key];
            return (
              <div className="admin-quiz-card" key={step.key}>
                <div className="admin-row-between">
                  <div>
                    <div className="admin-quiz-title">{step.title}</div>
                    <div className="admin-muted">{step.hint}</div>
                  </div>
                  <button type="button" className="admin-mini-action" onClick={() => resetQuizStep(step.key)}>
                    Сбросить
                  </button>
                </div>

                <label className="admin-label">Текст вопроса</label>
                <textarea
                  className="admin-input admin-textarea admin-quiz-question"
                  value={item.question}
                  onChange={(e) => updateQuizQuestion(step.key, e.target.value)}
                  rows={3}
                  maxLength={600}
                />

                <div className="admin-quiz-options-head">
                  <label className="admin-label">Кнопки ответов</label>
                  <button
                    type="button"
                    className="admin-mini-action"
                    onClick={() => addQuizOption(step.key)}
                    disabled={item.options.length >= 8}
                  >
                    + Вариант
                  </button>
                </div>

                <div className="admin-quiz-options">
                  {item.options.map((option, index) => (
                    <div className="admin-quiz-option-row" key={`${step.key}-${index}`}>
                      <span className="admin-quiz-option-index">{index + 1}</span>
                      <input
                        className="admin-input"
                        value={option}
                        onChange={(e) => updateQuizOption(step.key, index, e.target.value)}
                        maxLength={64}
                      />
                      <button
                        type="button"
                        className="admin-mini-action danger"
                        onClick={() => removeQuizOption(step.key, index)}
                        disabled={item.options.length <= 1}
                      >
                        Удалить
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        <div className="admin-field">
          <label className="admin-label">Событие подписки</label>
          <label className="admin-toggle-line">
            <input
              type="checkbox"
              checked={checkSubscriptionEnabled}
              onChange={(e) => setCheckSubscriptionEnabled(e.target.checked)}
            />{' '}
            {checkSubscriptionEnabled ? 'Chatterfy' : 'Заявка через Telegram-бота'}
          </label>
          <div className="admin-muted">
            {checkSubscriptionEnabled
              ? 'Факт подписки приходит postback-событием из Chatterfy.'
              : 'Кнопка ведёт напрямую в Telegram. Бот принимает заявку, фиксирует подписку и запускает отправку кружков. Бот должен быть администратором канала с правом приглашать пользователей.'}
          </div>
        </div>

        <div className="admin-field">
          <label className="admin-label">ID канала</label>
          <input
            className="admin-input"
            placeholder="-1003584421739"
            value={channelId}
            onChange={(e) => setChannelId(e.target.value)}
          />
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
            {saving ? 'Сохранение...' : 'Сохранить воронку'}
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
