import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';
import { useAdminLocale } from '../useAdminLocale';

const STREAM_SIGNALS = ['BUY', 'SELL'];
const INDICATOR_SIGNAL_OPTIONS = ['AUTO', 'BUY', 'SELL', 'NEUTRAL'];
const ACCESS_POLICIES = [
  {
    key: 'registration',
    title: 'After registration',
    description: 'Signals unlock after a Pocket registration postback.',
  },
  {
    key: 'registration_deposit',
    title: 'After registration and deposit',
    description: 'FTD and repeat deposits are added together.',
  },
  {
    key: 'all',
    title: 'Signal access is open to everyone',
    description: 'Signals are available without registration or deposit checks.',
  },
];
const STREAM_ANALYSIS_TYPES = [
  { key: 'forex', title: 'Forex' },
  { key: 'binary', title: 'Binary' },
];
const FOREX_STREAM_MARKETS = [
  { key: 'currencies', title: 'Currencies' },
  { key: 'indices', title: 'Indices' },
  { key: 'commodities', title: 'Commodities' },
  { key: 'stocks', title: 'Stocks' },
];
const BINARY_STREAM_MARKETS = [
  { key: 'forex', title: 'Forex' },
  { key: 'otc', title: 'OTC' },
  { key: 'commodities', title: 'Commodities' },
  { key: 'stocks', title: 'Stocks' },
  { key: 'crypto', title: 'Crypto' },
];
const QUIZ_STEPS = [
  { key: 'experience', title: 'Question 1', hint: 'Trading experience' },
  { key: 'broker_experience', title: 'Question 2', hint: 'Broker experience' },
  { key: 'capital', title: 'Question 3', hint: 'Capital / deposit' },
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
const FINAL_MESSAGE_MAX_BUTTONS = 8;
const FINAL_MESSAGE_BUTTON_TYPES = ['url', 'menu', 'web_app'];
const QUIZ_INTRO_VIDEO_MAX_SIZE = 50 * 1024 * 1024;
const DEFAULT_FINAL_MESSAGE_CONFIG = {
  enabled: true,
  trigger_button_text: 'Go to trading',
  message_text: "You're all set. Choose what you'd like to do next.",
  buttons: [
    {
      id: 'open_menu',
      type: 'menu',
      text: 'Open Elizabeth Vane',
      url: '',
    },
  ],
};

const createFinalButtonId = () =>
  `button_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;

const normalizeFinalMessageConfig = (rawConfig) => {
  const source = rawConfig && typeof rawConfig === 'object' ? rawConfig : {};
  const rawButtons = Array.isArray(source.buttons)
    ? source.buttons
    : DEFAULT_FINAL_MESSAGE_CONFIG.buttons;
  const usedIds = new Set();
  const buttons = rawButtons.slice(0, FINAL_MESSAGE_MAX_BUTTONS).map((rawButton, index) => {
    const item = rawButton && typeof rawButton === 'object' ? rawButton : {};
    const type = FINAL_MESSAGE_BUTTON_TYPES.includes(item.type) ? item.type : 'url';
    let id = String(item.id || `button_${index + 1}`).replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 48);
    if (!id) id = `button_${index + 1}`;
    let uniqueId = id;
    let suffix = 2;
    while (usedIds.has(uniqueId)) {
      uniqueId = `${id}_${suffix}`.slice(0, 48);
      suffix += 1;
    }
    usedIds.add(uniqueId);
    return {
      id: uniqueId,
      type,
      text: String(item.text || '').slice(0, 64),
      url: type === 'url' ? String(item.url || '').slice(0, 1000) : '',
    };
  });
  return {
    enabled: source.enabled === undefined
      ? DEFAULT_FINAL_MESSAGE_CONFIG.enabled
      : Boolean(Number(source.enabled) || source.enabled === true),
    trigger_button_text: String(
      source.trigger_button_text || DEFAULT_FINAL_MESSAGE_CONFIG.trigger_button_text
    ).slice(0, 64),
    message_text: String(
      source.message_text || DEFAULT_FINAL_MESSAGE_CONFIG.message_text
    ).slice(0, 3500),
    buttons,
  };
};

const normalizeFinalButtonUrl = (value) => {
  let raw = String(value || '').trim();
  if (raw.startsWith('@')) raw = `https://t.me/${raw.slice(1).replace(/^\/+/, '')}`;
  if (raw.startsWith('t.me/')) raw = `https://${raw}`;
  return raw;
};

const isValidFinalButtonUrl = (value) => {
  const normalized = normalizeFinalButtonUrl(value);
  try {
    const url = new URL(normalized);
    return (
      ((url.protocol === 'http:' || url.protocol === 'https:') && Boolean(url.host))
      || (url.protocol === 'tg:' && Boolean(url.host || url.pathname))
    );
  } catch {
    return false;
  }
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

const formatBytes = (value) => {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 MB';
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(bytes >= 10 * 1024 * 1024 ? 1 : 2)} MB`;
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

export default function SettingsPage() {
  const { language, setLanguage, tr } = useAdminLocale();
  const accessPolicies = useMemo(() => [
    {
      key: 'registration',
      title: tr('After registration', 'После регистрации'),
      description: tr('Signals unlock after a Pocket registration postback.', 'Сигналы откроются после Pocket registration postback.'),
    },
    {
      key: 'registration_deposit',
      title: tr('After registration and deposit', 'После регистрации и депозита'),
      description: tr('FTD and repeat deposits are added together.', 'Считаем общую сумму FTD и повторных депозитов.'),
    },
    {
      key: 'all',
      title: tr('Signal access is open to everyone', 'Доступ к сигналам открыт всем'),
      description: tr('Signals are available without registration or deposit checks.', 'Сигналы доступны без проверки регистрации и депозита.'),
    },
  ], [tr]);
  const localizedForexMarkets = useMemo(() => [
    { key: 'currencies', title: tr('Currencies', 'Валюты') },
    { key: 'indices', title: tr('Indices', 'Индексы') },
    { key: 'commodities', title: tr('Commodities', 'Сырье') },
    { key: 'stocks', title: tr('Stocks', 'Акции') },
  ], [tr]);
  const localizedBinaryMarkets = useMemo(() => [
    { key: 'forex', title: 'Forex' },
    { key: 'otc', title: 'OTC' },
    { key: 'commodities', title: tr('Commodities', 'Сырье') },
    { key: 'stocks', title: tr('Stocks', 'Акции') },
    { key: 'crypto', title: 'Crypto' },
  ], [tr]);
  const localizedQuizSteps = useMemo(() => [
    { key: 'experience', title: tr('Question 1', 'Вопрос 1'), hint: tr('Trading experience', 'Опыт в трейдинге') },
    { key: 'broker_experience', title: tr('Question 2', 'Вопрос 2'), hint: tr('Broker experience', 'Опыт с брокером') },
    { key: 'capital', title: tr('Question 3', 'Вопрос 3'), hint: tr('Capital / deposit', 'Капитал / депозит') },
  ], [tr]);
  const [activeSection, setActiveSection] = useState('menu');
  const [model, setModel] = useState('gpt-4o-mini');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [openAiApiKey, setOpenAiApiKey] = useState('');
  const [openAiKeyConfigured, setOpenAiKeyConfigured] = useState(false);
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
  const [quizIntroVideoEnabled, setQuizIntroVideoEnabled] = useState(true);
  const [quizIntroVideoMeta, setQuizIntroVideoMeta] = useState({
    file_exists: false,
    file_name: '',
    file_size: 0,
    source: 'missing',
    max_size: QUIZ_INTRO_VIDEO_MAX_SIZE,
  });
  const [quizIntroVideoUploading, setQuizIntroVideoUploading] = useState(false);
  const [funnelEditorTab, setFunnelEditorTab] = useState('quiz');
  const [finalMessageConfig, setFinalMessageConfig] = useState(() =>
    normalizeFinalMessageConfig(DEFAULT_FINAL_MESSAGE_CONFIG)
  );
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
      const settingsRes = await apiAdminFetchJson('/api/admin/settings');

      const ai = settingsRes?.settings?.ai || {};
      setModel(ai.model || 'gpt-4o-mini');
      setSystemPrompt(ai.system_prompt || '');
      setOpenAiApiKey('');
      setOpenAiKeyConfigured(Boolean(ai.openai_key_configured));
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
      const quizIntroVideo = support.quiz_intro_video || {};
      setQuizIntroVideoEnabled(Boolean(Number(
        quizIntroVideo.enabled ?? support.quiz_intro_video_enabled ?? 1
      )));
      setQuizIntroVideoMeta({
        file_exists: Boolean(quizIntroVideo.file_exists),
        file_name: String(quizIntroVideo.file_name || ''),
        file_size: Number(quizIntroVideo.file_size || 0),
        source: String(quizIntroVideo.source || 'missing'),
        max_size: Number(quizIntroVideo.max_size || QUIZ_INTRO_VIDEO_MAX_SIZE),
      });
      setFinalMessageConfig(normalizeFinalMessageConfig(support.final_message_config));

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
      setError(e.message || tr('Could not load settings', 'Не удалось загрузить настройки'));
    }
  }, [tr]);

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
    () => (streamAnalysisType === 'binary' ? localizedBinaryMarkets : localizedForexMarkets),
    [streamAnalysisType, localizedBinaryMarkets, localizedForexMarkets]
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
      setError(tr('Select a strategy for the stream', 'Выберите стратегию для стрима'));
      return;
    }

    const manualSL = toMaybeNumber(streamManualSL);
    const manualTP = toMaybeNumber(streamManualTP);
    const emulationPrice = toMaybeNumber(streamManualPrice);
    if (shouldSaveStreams && streamEnabled && streamLevelsMode === 'manual' && (manualSL === null || manualTP === null)) {
      setError(tr('Manual levels require Conservative SL and Target (Take Profit)', 'Для ручных уровней нужно указать Conservative SL и Target (Take Profit)'));
      return;
    }
    if (shouldSaveStreams && streamManualPrice.trim() && emulationPrice === null) {
      setError(tr('Current price must be a number', 'Текущая цена должна быть числом'));
      return;
    }
    const minDeposit = toMaybeNumber(systemMinDeposit);
    if (shouldSaveAccess && systemAccessPolicy === 'registration_deposit' && minDeposit === null) {
      setError(tr('Minimum deposit must be a number', 'Минимальная сумма депозита должна быть числом'));
      return;
    }
    const preparedFinalMessageConfig = {
      enabled: Boolean(finalMessageConfig.enabled),
      trigger_button_text: String(finalMessageConfig.trigger_button_text || '').trim(),
      message_text: String(finalMessageConfig.message_text || '').trim(),
      buttons: finalMessageConfig.buttons.map((button) => ({
        id: button.id,
        type: button.type,
        text: String(button.text || '').trim(),
        url: button.type === 'url' ? normalizeFinalButtonUrl(button.url) : '',
      })),
    };
    if (shouldSaveSupport) {
      const preparedQuiz = normalizeQuizConfig(quizConfig);
      const invalidStep = localizedQuizSteps.find((step) => {
        const item = preparedQuiz[step.key];
        return !String(item.question || '').trim() || !Array.isArray(item.options) || item.options.length === 0;
      });
      if (invalidStep) {
        setError(tr(
          `Fill in the question and at least one answer: ${invalidStep.title}`,
          `Заполните вопрос и хотя бы один вариант ответа: ${invalidStep.title}`
        ));
        return;
      }
      if (!preparedFinalMessageConfig.trigger_button_text) {
        setError(tr('Enter the post-subscription button label', 'Укажите название кнопки перехода после подписки'));
        setFunnelEditorTab('final');
        return;
      }
      if (preparedFinalMessageConfig.enabled && !preparedFinalMessageConfig.message_text) {
        setError(tr('Enter the final message text', 'Укажите текст финального сообщения'));
        setFunnelEditorTab('final');
        return;
      }
      if (
        preparedFinalMessageConfig.enabled
        && preparedFinalMessageConfig.buttons.length === 0
      ) {
        setError(tr('Add at least one final-message button', 'Добавьте хотя бы одну кнопку финального сообщения'));
        setFunnelEditorTab('final');
        return;
      }
      const menuButtons = preparedFinalMessageConfig.buttons.filter((button) => button.type === 'menu');
      if (menuButtons.length > 1) {
        setError(tr('Only one menu button can be added', 'Можно добавить только одну кнопку открытия меню'));
        setFunnelEditorTab('final');
        return;
      }
      const webAppButtons = preparedFinalMessageConfig.buttons.filter((button) => button.type === 'web_app');
      if (webAppButtons.length > 1) {
        setError(tr('Only one mini-app button can be added', 'Можно добавить только одну кнопку открытия мини-приложения'));
        setFunnelEditorTab('final');
        return;
      }
      const invalidFinalButtonIndex = preparedFinalMessageConfig.buttons.findIndex((button) => (
        !button.text
        || !FINAL_MESSAGE_BUTTON_TYPES.includes(button.type)
        || (button.type === 'url' && !isValidFinalButtonUrl(button.url))
      ));
      if (invalidFinalButtonIndex >= 0) {
        setError(tr(
          `Check the label and URL of button ${invalidFinalButtonIndex + 1}`,
          `Проверьте название и ссылку кнопки ${invalidFinalButtonIndex + 1}`
        ));
        setFunnelEditorTab('final');
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
          quiz_intro_video_enabled: quizIntroVideoEnabled,
          quiz_config: normalizeQuizConfig(quizConfig),
          final_message_config: preparedFinalMessageConfig,
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
        setStatus(tr('AI chat settings saved', 'Настройки AI чата сохранены'));
        setOpenAiApiKey('');
        await loadAll();
      } else if (source === 'streams') {
        setStatus(tr('Stream settings saved', 'Настройки стримов сохранены'));
      } else if (source === 'support') {
        setStatus(tr('Bot funnel settings saved', 'Настройки воронки бота сохранены'));
      } else if (source === 'pocket') {
        setStatus(tr('Pocket API saved', 'Pocket API сохранен'));
        setPocketApiToken('');
        await loadAll();
      } else if (source === 'access') {
        setStatus(tr('Access settings saved', 'Настройки доступа сохранены'));
      } else {
        setStatus(tr('Settings saved', 'Настройки сохранены'));
      }
    } catch (e) {
      setError(e.message || tr('Could not save settings', 'Не удалось сохранить настройки'));
    } finally {
      setSaving(false);
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

  const uploadQuizIntroVideo = async (file) => {
    if (!file) return;
    const extensionIsMp4 = String(file.name || '').toLowerCase().endsWith('.mp4');
    if (!extensionIsMp4) {
      setError(tr('Select an MP4 video file', 'Выберите видеофайл в формате MP4'));
      return;
    }
    const maxSize = Number(quizIntroVideoMeta.max_size || QUIZ_INTRO_VIDEO_MAX_SIZE);
    if (file.size > maxSize) {
      setError(tr(
        `The MP4 file must be no larger than ${formatBytes(maxSize)}`,
        `Размер MP4 не должен превышать ${formatBytes(maxSize)}`
      ));
      return;
    }

    setQuizIntroVideoUploading(true);
    setError('');
    setStatus('');
    try {
      const response = await apiAdminFetchJson('/api/admin/settings/quiz-intro-video', {
        method: 'PUT',
        headers: { 'Content-Type': file.type || 'video/mp4' },
        body: file,
      });
      const video = response?.quiz_intro_video || {};
      setQuizIntroVideoMeta({
        file_exists: Boolean(video.file_exists),
        file_name: String(video.file_name || file.name || ''),
        file_size: Number(video.file_size || file.size || 0),
        source: String(video.source || 'uploaded'),
        max_size: Number(video.max_size || maxSize),
      });
      setStatus(tr(
        'The quiz intro video note was replaced',
        'Кружок перед опросником заменён'
      ));
    } catch (e) {
      setError(e.message || tr('Could not upload the MP4 file', 'Не удалось загрузить MP4'));
    } finally {
      setQuizIntroVideoUploading(false);
    }
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

  const updateFinalMessageField = (field, value) => {
    setFinalMessageConfig((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const addFinalMessageButton = (type) => {
    setError('');
    if (finalMessageConfig.buttons.length >= FINAL_MESSAGE_MAX_BUTTONS) {
      setError(tr(`No more than ${FINAL_MESSAGE_MAX_BUTTONS} buttons can be added`, `Можно добавить не более ${FINAL_MESSAGE_MAX_BUTTONS} кнопок`));
      return;
    }
    if (type === 'menu' && finalMessageConfig.buttons.some((button) => button.type === 'menu')) {
      setError(tr('A menu button has already been added', 'Кнопка открытия меню уже добавлена'));
      return;
    }
    if (type === 'web_app' && finalMessageConfig.buttons.some((button) => button.type === 'web_app')) {
      setError(tr('A mini-app button has already been added', 'Кнопка открытия мини-приложения уже добавлена'));
      return;
    }
    setFinalMessageConfig((prev) => ({
      ...prev,
      buttons: [
        ...prev.buttons,
        {
          id: createFinalButtonId(),
          type,
          text: type === 'menu'
            ? 'Open menu'
            : (type === 'web_app' ? 'Open Elizabeth Vane' : 'Open link'),
          url: type === 'url' ? 'https://' : '',
        },
      ],
    }));
  };

  const updateFinalMessageButton = (buttonId, patch) => {
    setFinalMessageConfig((prev) => ({
      ...prev,
      buttons: prev.buttons.map((button) => (
        button.id === buttonId
          ? {
              ...button,
              ...patch,
              url: patch.type && patch.type !== 'url' ? '' : (patch.url ?? button.url),
            }
          : button
      )),
    }));
  };

  const changeFinalMessageButtonType = (buttonId, type) => {
    if (
      ['menu', 'web_app'].includes(type)
      && finalMessageConfig.buttons.some((button) => button.type === type && button.id !== buttonId)
    ) {
      setError(
        type === 'menu'
          ? tr('Only one menu button can be added', 'Можно добавить только одну кнопку открытия меню')
          : tr('Only one mini-app button can be added', 'Можно добавить только одну кнопку открытия мини-приложения')
      );
      return;
    }
    setError('');
    updateFinalMessageButton(buttonId, { type, url: type === 'url' ? 'https://' : '' });
  };

  const removeFinalMessageButton = (buttonId) => {
    setFinalMessageConfig((prev) => ({
      ...prev,
      buttons: prev.buttons.filter((button) => button.id !== buttonId),
    }));
  };

  const moveFinalMessageButton = (buttonId, direction) => {
    setFinalMessageConfig((prev) => {
      const index = prev.buttons.findIndex((button) => button.id === buttonId);
      const targetIndex = index + direction;
      if (index < 0 || targetIndex < 0 || targetIndex >= prev.buttons.length) return prev;
      const buttons = [...prev.buttons];
      [buttons[index], buttons[targetIndex]] = [buttons[targetIndex], buttons[index]];
      return { ...prev, buttons };
    });
  };

  const resetFinalMessage = () => {
    setFinalMessageConfig(normalizeFinalMessageConfig(DEFAULT_FINAL_MESSAGE_CONFIG));
    setError('');
  };

  const cards = useMemo(
    () => [
      {
        key: 'streams',
        icon: '📡',
        title: tr('Streams', 'Стримы'),
        subtitle: streamEnabled ? tr('Fallback enabled', 'Fallback включен') : tr('Fallback disabled', 'Fallback выключен'),
      },
      {
        key: 'ai',
        icon: '🤖',
        title: tr('AI chat', 'AI чат'),
        subtitle: `${tr('Model', 'Модель')}: ${model || '-'}`,
      },
      {
        key: 'access',
        icon: '✅',
        title: tr('System access', 'Доступ к системе'),
        subtitle: accessPolicies.find((item) => item.key === systemAccessPolicy)?.title || tr('Access rule', 'Правило доступа'),
      },
      {
        key: 'support',
        icon: '🔗',
        title: tr('Bot funnel', 'Воронка бота'),
        subtitle: tr('Quiz, subscription and final message', 'Опросник, подписка и финальное сообщение'),
      },
      {
        key: 'pocket',
        icon: '🔑',
        title: 'API',
        subtitle: pocketPartnerId || pocketApiTokenConfigured
          ? `Pocket: ${pocketPartnerId || '-'} ${pocketApiTokenMasked || ''}`
          : tr('Pocket API is not configured', 'Pocket API не настроен'),
      },
      {
        key: 'interface',
        icon: '🌐',
        title: tr('Interface language', 'Язык интерфейса'),
        subtitle: language === 'ru' ? 'Русский' : 'English',
      },
    ],
    [accessPolicies, language, model, pocketApiTokenConfigured, pocketApiTokenMasked, pocketPartnerId, streamEnabled, systemAccessPolicy, tr]
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
          <h3 className="admin-section-title">{tr('Settings', 'Настройки')}</h3>
          <div className="admin-muted">
            {tr('Open the section you need', 'Откройте карточку нужного раздела')}
          </div>

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

  if (activeSection === 'interface') {
    return (
      <div className="admin-card admin-settings-detail">
        <div className="admin-row-between">
          <div>
            <div className="admin-badge">{tr('Interface', 'Интерфейс')}</div>
            <h3 className="admin-section-title">
              {tr('Interface language', 'Язык интерфейса')}
            </h3>
          </div>
          <button className="admin-btn-outline" onClick={goMenu}>
            {tr('← Back to settings', '← К настройкам')}
          </button>
        </div>

        <div className="admin-language-panel">
          <p className="admin-muted">
            {tr(
              'English is the default language for client-facing recordings. Your choice is saved only in this browser.',
              'Английский используется по умолчанию для клиентских записей. Выбор сохраняется только в этом браузере.'
            )}
          </p>
          <div className="admin-language-options">
            <button
              type="button"
              className={language === 'en' ? 'active' : ''}
              onClick={() => setLanguage('en')}
            >
              <span className="admin-language-code">EN</span>
              <span>
                <strong>English</strong>
                <small>{tr('Default for Admin Center', 'По умолчанию для админ-центра')}</small>
              </span>
              <b>{language === 'en' ? '✓' : ''}</b>
            </button>
            <button
              type="button"
              className={language === 'ru' ? 'active' : ''}
              onClick={() => setLanguage('ru')}
            >
              <span className="admin-language-code">RU</span>
              <span>
                <strong>Русский</strong>
                <small>{tr('Optional working language', 'Дополнительный рабочий язык')}</small>
              </span>
              <b>{language === 'ru' ? '✓' : ''}</b>
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (activeSection === 'ai') {
    return (
      <div className="admin-card admin-settings-detail">
        <div className="admin-row-between">
          <h3 className="admin-section-title">{tr('AI chat', 'AI чат')}</h3>
          <button className="admin-btn-outline" onClick={goMenu}>{tr('← Back to settings', '← К карточкам')}</button>
        </div>

        <div className="admin-field">
          <label className="admin-label">{tr('Model', 'Модель')}</label>
          <input className="admin-input" value={model} onChange={(e) => setModel(e.target.value)} />
        </div>

        <div className="admin-field">
          <label className="admin-label">{tr('OpenAI API key', 'OpenAI API-ключ')}</label>
          <input
            className="admin-input"
            type="password"
            autoComplete="off"
            value={openAiApiKey}
            onChange={(e) => setOpenAiApiKey(e.target.value)}
            placeholder={openAiKeyConfigured ? tr('Key configured — enter a new key only to replace it', 'Ключ настроен — введите новый только для замены') : 'sk-proj-…'}
          />
          <div className="admin-muted">
            {openAiKeyConfigured
              ? tr('The key is saved and hidden. It is shared by AI chat, EL CHATTER and the main Elizabeth bot.', 'Ключ сохранён и скрыт. Его используют AI-чат, EL CHATTER и основной бот Elizabeth.')
              : tr('The key is not configured yet.', 'Ключ ещё не настроен.')}
          </div>
        </div>

        <div className="admin-field">
          <label className="admin-label">{tr('System prompt', 'Системный промпт')}</label>
          <textarea
            className="admin-textarea"
            rows={8}
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
          />
        </div>

        <div className="admin-row-actions">
          <button className="admin-btn" onClick={() => saveSettings('ai')} disabled={saving}>
            {saving ? tr('Saving…', 'Сохранение...') : tr('Save AI chat', 'Сохранить AI чат')}
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
          <h3 className="admin-section-title">{tr('Streams', 'Стримы')}</h3>
          <button className="admin-btn-outline" onClick={goMenu}>{tr('← Back to settings', '← К карточкам')}</button>
        </div>

        <div className="admin-stream-guide">
          <div>{tr('This section controls the signal fallback mode when an administrator sets a preferred direction.', 'Этот раздел управляет fallback-режимом сигнала, когда админ задаёт приоритетное направление.')}</div>
          <div>{tr('Required: select BUY/SELL. Select a strategy when using “Selected strategy”.', 'Обязательно: выберите направление BUY/SELL. Для режима «По выбранной стратегии» укажите стратегию.')}</div>
          <div>{tr('Optional: manual SL/TP levels and indicator signals. If omitted, the system calculates them automatically.', 'Опционально: ручные уровни SL/TP и ручные сигналы индикаторов. Если пропустить, система рассчитает автоматически.')}</div>
        </div>

        <div className="admin-stream-block">
          <label className="admin-label">{tr('Stream mode', 'Режим стрима')}</label>
          <label className="admin-switch-line">
            <input
              type="checkbox"
              checked={streamEnabled}
              onChange={(e) => setStreamEnabled(e.target.checked)}
            />
            <span>{streamEnabled ? tr('Enabled', 'Включен') : tr('Disabled', 'Выключен')}</span>
          </label>
        </div>

        <div className="admin-stream-block">
          <label className="admin-label">{tr('Apply fallback', 'Применять fallback')}</label>
          <div className="admin-pill-group">
            <button
              type="button"
              className={`admin-pill-btn ${streamScope === 'all' ? 'active' : ''}`}
              onClick={() => setStreamScope('all')}
            >
              {tr('All strategies', 'По всем стратегиям')}
            </button>
            <button
              type="button"
              className={`admin-pill-btn ${streamScope === 'strategy' ? 'active' : ''}`}
              onClick={() => setStreamScope('strategy')}
            >
              {tr('Selected strategy', 'По выбранной стратегии')}
            </button>
          </div>
        </div>

        {streamScope === 'strategy' ? (
          <div className="admin-stream-block">
            <label className="admin-label">{tr('Strategy', 'Стратегия')}</label>
            <select
              className="admin-input"
              value={streamStrategyId}
              onChange={(e) => setStreamStrategyId(e.target.value)}
            >
              <option value="">{tr('Select strategy', 'Выберите стратегию')}</option>
              {streamStrategies.map((strategy) => (
                <option key={strategy.id} value={strategy.id}>
                  {(strategy.icon || '📌') + ' ' + strategy.name}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div className="admin-stream-block admin-stream-emulation-block">
          <label className="admin-label">{tr('Asset and price for record emulation', 'Актив и цена для эмуляции записи')}</label>
          <div className="admin-stream-hint">
            {tr(
              'Select the signal type first. Forex uses markets and pairs from the Forex section; Binary uses binary markets with payout.',
              'Сначала выберите тип сигнала. Для Forex подтягиваются рынки и пары из Forex-раздела: валюты, индексы, сырье и акции. Для Binary подтягиваются binary-рынки с payout.'
            )}
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
            {tr(
              'The asset can be left empty to keep the user-selected asset and live price. If set, this asset is written to the card and signal history.',
              'Можно оставить актив пустым: тогда пользовательский актив и live-цена останутся как обычно. Если указать актив, именно он попадёт в карточку и историю сигнала.'
            )}
          </div>
          <div className="admin-stream-emulation-grid">
            <div className="admin-field">
              <label className="admin-label">{tr('Market', 'Рынок')}</label>
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
              <label className="admin-label">{tr('Asset', 'Актив')}</label>
              <input
                className="admin-input"
                list={`stream-asset-options-${streamAnalysisType}-${streamMarket}`}
                placeholder={streamMarketLoading
                  ? tr('Loading assets…', 'Загружаем активы...')
                  : streamAnalysisType === 'binary'
                    ? tr('For example, Netflix OTC', 'Например Netflix OTC')
                    : tr('For example, AUD/CHF', 'Например AUD/CHF')}
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
              <label className="admin-label">{tr('Current price', 'Текущая цена')}</label>
              <input
                className="admin-input"
                inputMode="decimal"
                placeholder={tr('Automatic when empty', 'Автоматически, если пусто')}
                value={streamManualPrice}
                onChange={(e) => setStreamManualPrice(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="admin-stream-block">
          <label className="admin-label">{tr('Final system verdict', 'Итоговый вердикт системы')}</label>
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
          <label className="admin-label">Conservative SL {tr('and', 'и')} Target (Take Profit)</label>
          <div className="admin-pill-group">
            <button
              type="button"
              className={`admin-pill-btn ${streamLevelsMode === 'auto' ? 'active' : ''}`}
              onClick={() => setStreamLevelsMode('auto')}
            >
              {tr('Automatic', 'Автоматически')}
            </button>
            <button
              type="button"
              className={`admin-pill-btn ${streamLevelsMode === 'manual' ? 'active' : ''}`}
              onClick={() => setStreamLevelsMode('manual')}
            >
              {tr('Manual', 'Вручную')}
            </button>
          </div>
          {streamLevelsMode === 'manual' ? (
            <div className="admin-stream-levels-grid">
              <div className="admin-field">
                <label className="admin-label">Conservative SL</label>
                <input
                  className="admin-input"
                  inputMode="decimal"
                  placeholder={tr('For example 1.23456', 'Например 1.23456')}
                  value={streamManualSL}
                  onChange={(e) => setStreamManualSL(e.target.value)}
                />
              </div>
              <div className="admin-field">
                <label className="admin-label">Target (Take Profit)</label>
                <input
                  className="admin-input"
                  inputMode="decimal"
                  placeholder={tr('For example 1.24567', 'Например 1.24567')}
                  value={streamManualTP}
                  onChange={(e) => setStreamManualTP(e.target.value)}
                />
              </div>
            </div>
          ) : (
            <div className="admin-muted">{tr('Levels will be taken automatically from the standard analysis.', 'Уровни будут взяты из стандартного анализа автоматически.')}</div>
          )}
        </div>

        <div className="admin-stream-block">
          <label className="admin-label">{tr('Indicator signals (for selected strategy)', 'Сигналы индикаторов (для выбранной стратегии)')}</label>
          {streamScope !== 'strategy' ? (
            <div className="admin-muted">{tr('This block is available only in “Selected strategy” mode.', 'Этот блок доступен только в режиме «По выбранной стратегии».')}</div>
          ) : (
            <>
              <div className="admin-pill-group">
                <button
                  type="button"
                  className={`admin-pill-btn ${streamIndicatorMode === 'auto' ? 'active' : ''}`}
                  onClick={() => setStreamIndicatorMode('auto')}
                >
                  {tr('Automatic', 'Автоматически')}
                </button>
                <button
                  type="button"
                  className={`admin-pill-btn ${streamIndicatorMode === 'manual' ? 'active' : ''}`}
                  onClick={() => setStreamIndicatorMode('manual')}
                  disabled={!selectedStrategy}
                >
                  {tr('Manual', 'Вручную')}
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
                    <div className="admin-muted">{tr('The selected strategy has no connected indicators.', 'У выбранной стратегии нет подключенных индикаторов.')}</div>
                  )
                ) : (
                  <div className="admin-muted">{tr('Select a strategy before configuring indicators.', 'Сначала выберите стратегию, затем настройте индикаторы.')}</div>
                )
              ) : (
                <div className="admin-muted">{tr('The system will distribute indicator signals toward the selected verdict.', 'Система сама распределит сигналы индикаторов с перевесом в выбранный вердикт.')}</div>
              )}
            </>
          )}
        </div>

        <div className="admin-stream-preview-card">
          <div className="admin-stream-preview-head">
            <div>
              <div className="admin-stream-preview-title">{tr('Final signal preview', 'Превью итогового сигнала')}</div>
              <div className="admin-stream-preview-meta">
                {previewStrategy ? `${previewStrategy.icon || '📌'} ${previewStrategy.name}` : tr('No selected strategy', 'Без выбранной стратегии')}
                {previewStrategy?.allowed_timeframes ? ` | ${previewStrategy.allowed_timeframes}` : ''}
              </div>
              <div className="admin-stream-preview-note">
                {tr('Type', 'Тип')}: {streamAnalysisType === 'binary' ? 'Binary' : 'Forex'} · {tr('Asset', 'Актив')}: {streamSymbol.trim() ? `${selectedStreamMarketTitle} · ${streamSymbol.trim()}` : tr('user selection', 'как выбрал пользователь')}
                {' · '}
                {tr('Price', 'Цена')}: {toMaybeNumber(streamManualPrice) !== null ? formatLevel(streamManualPrice) : 'live'}
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
            {saving ? tr('Saving…', 'Сохранение...') : tr('Save streams', 'Сохранить стримы')}
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
          <h3 className="admin-section-title">{tr('System access', 'Доступ к системе')}</h3>
          <button className="admin-btn-outline" onClick={goMenu}>{tr('← Back to settings', '← К карточкам')}</button>
        </div>

        <div className="admin-muted">
          {tr(
            'These settings control access to signals. Manual access configured in a user profile remains a personal override.',
            'Эти переменные управляют доступом к получению сигналов. Ручная выдача доступа в карточке пользователя остается персональным override.'
          )}
        </div>

        <div className="admin-access-policy-list">
          {accessPolicies.map((item) => (
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
            <label className="admin-label">{tr('Minimum total deposits, $', 'Минимальная общая сумма депозитов, $')}</label>
            <input
              className="admin-input"
              value={systemMinDeposit}
              onChange={(e) => setSystemMinDeposit(e.target.value)}
              placeholder="100.00"
              inputMode="decimal"
            />
            <div className="admin-muted">
              {tr(
                'FTD and repeat deposits are added together. Signal access unlocks automatically when the total reaches this value.',
                'FTD и повторные депозиты суммируются. Когда сумма станет равна или выше этого значения, доступ к сигналам откроется автоматически.'
              )}
            </div>
          </div>
        ) : null}

        <div className="admin-field">
          <label className="admin-label">{tr('Pocket Option registration URL', 'Ссылка регистрации на Pocket Option')}</label>
          <input
            className="admin-input"
            type="url"
            value={systemRegistrationUrl}
            onChange={(e) => setSystemRegistrationUrl(e.target.value)}
            placeholder="https://pocketoption.com/..."
          />
          <div className="admin-muted">
            {tr('One shared URL for account conversations and the main bot. The ', 'Одна общая ссылка для переписки от аккаунта и основного бота. Шаблон ')}
            {'{click_id}'}
            {tr(' placeholder is replaced with the user ID; other unknown parameters are sent empty.', ' заменяется ID пользователя, остальные неизвестные параметры передаются пустыми.')}
          </div>
        </div>

        <div className="admin-row-actions">
          <button className="admin-btn" onClick={() => saveSettings('access')} disabled={saving}>
            {saving ? tr('Saving…', 'Сохранение...') : tr('Save access', 'Сохранить доступ')}
          </button>
        </div>

        {error ? <div className="admin-error">{error}</div> : null}
        {status ? <div className="admin-success">{status}</div> : null}
      </div>
    );
  }

  if (activeSection === 'support') {
    const visibleQuizConfig = normalizeQuizConfig(quizConfig);
    const hasMenuButton = finalMessageConfig.buttons.some((button) => button.type === 'menu');
    const hasWebAppButton = finalMessageConfig.buttons.some((button) => button.type === 'web_app');
    return (
      <div className="admin-card admin-settings-detail">
        <div className="admin-row-between">
          <h3 className="admin-section-title">{tr('Bot funnel', 'Воронка бота')}</h3>
          <button className="admin-btn-outline" onClick={goMenu}>{tr('← Back to settings', '← К карточкам')}</button>
        </div>

        <div className="admin-muted">
          {tr(
            'Configure the Elizabeth Bot journey: quiz, channel subscription and final message.',
            'Настройте путь пользователя в Elizabeth Bot: опросник, подписку на канал и финальное сообщение.'
          )}
        </div>

        <div className="admin-funnel-tabs" role="tablist" aria-label={tr('Funnel sections', 'Разделы воронки')}>
          {[
            ['quiz', tr('Quiz', 'Опросник')],
            ['channel', tr('Subscription', 'Подписка')],
            ['final', tr('Final', 'Финал')],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={funnelEditorTab === key}
              className={funnelEditorTab === key ? 'active' : ''}
              onClick={() => {
                setFunnelEditorTab(key);
                setError('');
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {funnelEditorTab === 'quiz' ? (
          <div className="admin-funnel-quiz">
            <div className="admin-funnel-head">
              <div>
                <div className="admin-funnel-title">{tr('Onboarding quiz', 'Стартовый опросник')}</div>
                <div className="admin-muted">{tr('Each answer becomes a separate Telegram inline button.', 'Каждый вариант станет отдельной inline-кнопкой в Telegram.')}</div>
              </div>
              <button
                type="button"
                className="admin-btn-outline"
                onClick={() => setQuizConfig(normalizeQuizConfig())}
              >
                {tr('Reset all', 'Сбросить все')}
              </button>
            </div>

            <div className="admin-quiz-video-card">
              <div className="admin-quiz-video-title-row">
                <div>
                  <div className="admin-quiz-video-eyebrow">{tr('Before question 1', 'Перед вопросом 1')}</div>
                  <div className="admin-quiz-video-title">{tr('Quiz intro video note', 'Кружок перед опросником')}</div>
                  <div className="admin-muted">
                    {tr(
                      'The main Elizabeth bot sends this video note once, immediately before the first quiz question.',
                      'Основной бот Elizabeth отправляет этот кружок один раз — непосредственно перед первым вопросом.'
                    )}
                  </div>
                </div>
                <span className={`admin-quiz-video-status ${quizIntroVideoMeta.file_exists ? 'ready' : 'missing'}`}>
                  {quizIntroVideoMeta.file_exists
                    ? tr('MP4 ready', 'MP4 загружен')
                    : tr('No MP4', 'Нет MP4')}
                </span>
              </div>

              <label className={`admin-final-enabled-card ${quizIntroVideoEnabled ? 'is-on' : ''}`}>
                <input
                  type="checkbox"
                  checked={quizIntroVideoEnabled}
                  onChange={(e) => setQuizIntroVideoEnabled(e.target.checked)}
                />
                <span>
                  <strong>{tr('Send the video note before the quiz', 'Отправлять кружок перед опросником')}</strong>
                  <small>
                    {quizIntroVideoEnabled
                      ? tr('Enabled: the video note is sent before question 1.', 'Включено: кружок уйдёт перед вопросом 1.')
                      : tr('Disabled: the funnel starts directly with the welcome text and question 1.', 'Выключено: воронка сразу начнётся с приветствия и вопроса 1.')}
                  </small>
                </span>
                <b>{quizIntroVideoEnabled ? tr('ON', 'ВКЛ') : tr('OFF', 'ВЫКЛ')}</b>
              </label>

              <div className="admin-quiz-video-file">
                <div className="admin-quiz-video-file-info">
                  <strong>
                    {quizIntroVideoMeta.file_exists
                      ? (quizIntroVideoMeta.source === 'uploaded'
                        ? tr('Custom video note', 'Свой кружок')
                        : tr('Default video note', 'Стандартный кружок'))
                      : tr('Video note is missing', 'Кружок не загружен')}
                  </strong>
                  <span>
                    {quizIntroVideoMeta.file_exists
                      ? `${quizIntroVideoMeta.file_name} · ${formatBytes(quizIntroVideoMeta.file_size)}`
                      : tr('Upload an MP4 file to enable sending.', 'Загрузите MP4, чтобы включить отправку.')}
                  </span>
                  <small>
                    {tr(
                      `MP4 only, up to ${formatBytes(quizIntroVideoMeta.max_size)}. Telegram will send it as a round video note.`,
                      `Только MP4, до ${formatBytes(quizIntroVideoMeta.max_size)}. Telegram отправит файл как круглый видеокружок.`
                    )}
                  </small>
                </div>
                <label className={`admin-quiz-video-upload ${quizIntroVideoUploading ? 'is-loading' : ''}`}>
                  <input
                    type="file"
                    accept="video/mp4,.mp4"
                    disabled={quizIntroVideoUploading}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      e.target.value = '';
                      uploadQuizIntroVideo(file);
                    }}
                  />
                  {quizIntroVideoUploading
                    ? tr('Uploading…', 'Загрузка...')
                    : (quizIntroVideoMeta.file_exists
                      ? tr('Replace MP4', 'Заменить MP4')
                      : tr('Upload MP4', 'Загрузить MP4'))}
                </label>
              </div>

            </div>

            {localizedQuizSteps.map((step) => {
              const item = visibleQuizConfig[step.key];
              return (
                <div className="admin-quiz-card" key={step.key}>
                  <div className="admin-row-between">
                    <div>
                      <div className="admin-quiz-title">{step.title}</div>
                      <div className="admin-muted">{step.hint}</div>
                    </div>
                    <button type="button" className="admin-mini-action" onClick={() => resetQuizStep(step.key)}>
                      {tr('Reset', 'Сбросить')}
                    </button>
                  </div>

                  <label className="admin-label">{tr('Question text', 'Текст вопроса')}</label>
                  <textarea
                    className="admin-input admin-textarea admin-quiz-question"
                    value={item.question}
                    onChange={(e) => updateQuizQuestion(step.key, e.target.value)}
                    rows={3}
                    maxLength={600}
                  />

                  <div className="admin-quiz-options-head">
                    <label className="admin-label">{tr('Answer buttons', 'Кнопки ответов')}</label>
                    <button
                      type="button"
                      className="admin-mini-action"
                      onClick={() => addQuizOption(step.key)}
                      disabled={item.options.length >= 8}
                    >
                      + {tr('Answer', 'Вариант')}
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
                          {tr('Delete', 'Удалить')}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}

        {funnelEditorTab === 'channel' ? (
          <div className="admin-funnel-panel">
            <div className="admin-funnel-head">
              <div>
                <div className="admin-funnel-title">{tr('Subscription and channel', 'Подписка и канал')}</div>
                <div className="admin-muted">{tr('Access check before showing the final message.', 'Проверка доступа перед переходом к финальному сообщению.')}</div>
              </div>
            </div>

            <div className="admin-field">
              <label className="admin-label">{tr('Subscription event', 'Событие подписки')}</label>
              <label className="admin-toggle-line">
                <input
                  type="checkbox"
                  checked={checkSubscriptionEnabled}
                  onChange={(e) => setCheckSubscriptionEnabled(e.target.checked)}
                />{' '}
                {checkSubscriptionEnabled ? 'Chatterfy' : tr('Request via Telegram bot', 'Заявка через Telegram-бота')}
              </label>
              <div className="admin-muted">
                {checkSubscriptionEnabled
                  ? tr('Subscription confirmation arrives as a Chatterfy postback event.', 'Факт подписки приходит postback-событием из Chatterfy.')
                  : tr('The button opens Telegram directly. The bot accepts the join request, records the subscription and starts video notes. The bot must be a channel administrator with permission to invite users.', 'Кнопка ведёт напрямую в Telegram. Бот принимает заявку, фиксирует подписку и запускает отправку кружков. Бот должен быть администратором канала с правом приглашать пользователей.')}
              </div>
            </div>

            <div className="admin-field">
              <label className="admin-label">{tr('Channel ID', 'ID канала')}</label>
              <input
                className="admin-input"
                placeholder="-1003584421739"
                value={channelId}
                onChange={(e) => setChannelId(e.target.value)}
              />
            </div>

            <div className="admin-field">
              <label className="admin-label">{tr('Channel URL', 'Ссылка на канал')}</label>
              <input
                className="admin-input"
                placeholder="https://t.me/channel"
                value={channelUrl}
                onChange={(e) => setChannelUrl(e.target.value)}
              />
            </div>

            <div className="admin-field">
              <label className="admin-label">{tr('Personal chat / support URL', 'Ссылка на личный чат / поддержку')}</label>
              <input
                className="admin-input"
                placeholder="https://t.me/support_username"
                value={supportUrl}
                onChange={(e) => setSupportUrl(e.target.value)}
              />
            </div>
          </div>
        ) : null}

        {funnelEditorTab === 'final' ? (
          <div className="admin-final-message-builder">
            <div className="admin-funnel-head">
              <div>
                <div className="admin-funnel-title">{tr('Final message', 'Финальное сообщение')}</div>
                <div className="admin-muted">
                  {tr('The bot shows it after the trading button is successfully pressed.', 'Бот показывает его после успешного нажатия кнопки перехода к трейдингу.')}
                </div>
              </div>
              <button type="button" className="admin-btn-outline" onClick={resetFinalMessage}>
                {tr('Reset', 'Сбросить')}
              </button>
            </div>

            <label className={`admin-final-enabled-card ${finalMessageConfig.enabled ? 'is-on' : ''}`}>
              <input
                type="checkbox"
                checked={finalMessageConfig.enabled}
                onChange={(e) => updateFinalMessageField('enabled', e.target.checked)}
              />
              <span>
                <strong>{tr('Use final message', 'Использовать финальное сообщение')}</strong>
                <small>
                  {finalMessageConfig.enabled
                    ? tr('After subscription verification, the bot replaces the message and shows the configured buttons.', 'После проверки подписки бот заменит сообщение и покажет настроенные кнопки.')
                    : tr('Disabled: the bot sends the legacy main menu.', 'Выключено: бот отправит старое главное меню.')}
                </small>
              </span>
              <b>{finalMessageConfig.enabled ? tr('ON', 'ВКЛ') : tr('OFF', 'ВЫКЛ')}</b>
            </label>

            <div className="admin-field">
              <label className="admin-label">{tr('Continue button label', 'Название кнопки перехода')}</label>
              <input
                className="admin-input"
                value={finalMessageConfig.trigger_button_text}
                onChange={(e) => updateFinalMessageField('trigger_button_text', e.target.value)}
                maxLength={64}
                placeholder="Go to trading"
              />
              <div className="admin-muted">
                {tr('This button appears under the channel URL and opens the final message.', 'Эта кнопка показывается под ссылкой на канал и открывает финальное сообщение.')}
              </div>
            </div>

            <div className="admin-field">
              <div className="admin-row-between">
                <label className="admin-label">{tr('Message after click', 'Текст после нажатия')}</label>
                <span className="admin-field-counter">{finalMessageConfig.message_text.length}/3500</span>
              </div>
              <textarea
                className="admin-input admin-textarea admin-final-message-text"
                value={finalMessageConfig.message_text}
                onChange={(e) => updateFinalMessageField('message_text', e.target.value)}
                rows={6}
                maxLength={3500}
                placeholder={tr('Enter the final message for the client', 'Введите финальное сообщение для клиента')}
              />
              <div className="admin-muted">{tr('Sent as plain safe text without HTML markup.', 'Отправляется как обычный безопасный текст без HTML-разметки.')}</div>
            </div>

            <div className="admin-final-buttons-head">
              <div>
                <div className="admin-funnel-title">
                  {tr('Inline buttons', 'Inline-кнопки')} <span className="admin-count-badge">{finalMessageConfig.buttons.length}/{FINAL_MESSAGE_MAX_BUTTONS}</span>
                </div>
                <div className="admin-muted">{tr('Buttons are sent one per row in the specified order.', 'Кнопки отправляются по одной строке в указанном порядке.')}</div>
              </div>
              <div className="admin-final-add-actions">
                <button
                  type="button"
                  className="admin-btn-outline"
                  onClick={() => addFinalMessageButton('url')}
                  disabled={finalMessageConfig.buttons.length >= FINAL_MESSAGE_MAX_BUTTONS}
                >
                  + {tr('URL', 'Ссылка')}
                </button>
                <button
                  type="button"
                  className="admin-btn-outline"
                  onClick={() => addFinalMessageButton('menu')}
                  disabled={hasMenuButton || finalMessageConfig.buttons.length >= FINAL_MESSAGE_MAX_BUTTONS}
                >
                  + {tr('Bot menu', 'Меню бота')}
                </button>
                <button
                  type="button"
                  className="admin-btn-outline"
                  onClick={() => addFinalMessageButton('web_app')}
                  disabled={hasWebAppButton || finalMessageConfig.buttons.length >= FINAL_MESSAGE_MAX_BUTTONS}
                >
                  + {tr('Mini app', 'Мини-апка')}
                </button>
              </div>
            </div>

            <div className="admin-final-button-list">
              {finalMessageConfig.buttons.map((button, index) => (
                <div className="admin-final-button-card" key={button.id}>
                  <div className="admin-final-button-order">
                    <strong>{index + 1}</strong>
                    <button
                      type="button"
                      onClick={() => moveFinalMessageButton(button.id, -1)}
                      disabled={index === 0}
                      aria-label={tr(`Move button ${index + 1} up`, `Поднять кнопку ${index + 1}`)}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      onClick={() => moveFinalMessageButton(button.id, 1)}
                      disabled={index === finalMessageConfig.buttons.length - 1}
                      aria-label={tr(`Move button ${index + 1} down`, `Опустить кнопку ${index + 1}`)}
                    >
                      ↓
                    </button>
                  </div>

                  <div className="admin-final-button-fields">
                    <div className="admin-final-button-card-head">
                      <span className={`admin-final-button-type ${button.type}`}>
                        {button.type === 'menu'
                          ? tr('Bot menu', 'Меню бота')
                          : (button.type === 'web_app' ? tr('Mini app', 'Мини-приложение') : tr('External URL', 'Внешняя ссылка'))}
                      </span>
                      <button
                        type="button"
                        className="admin-mini-action danger"
                        onClick={() => removeFinalMessageButton(button.id)}
                      >
                        {tr('Delete', 'Удалить')}
                      </button>
                    </div>

                    <div className="admin-final-button-grid">
                      <label>
                        <span>{tr('Label', 'Название')}</span>
                        <input
                          className="admin-input"
                          value={button.text}
                          onChange={(e) => updateFinalMessageButton(button.id, { text: e.target.value })}
                          maxLength={64}
                          placeholder={tr('Button label', 'Название кнопки')}
                        />
                      </label>
                      <label>
                        <span>{tr('Action', 'Действие')}</span>
                        <select
                          className="admin-input"
                          value={button.type}
                          onChange={(e) => changeFinalMessageButtonType(button.id, e.target.value)}
                        >
                          <option value="url">{tr('Open URL', 'Открыть ссылку')}</option>
                          <option
                            value="menu"
                            disabled={hasMenuButton && button.type !== 'menu'}
                          >
                            {tr('Show bot menu', 'Показать меню бота')}
                          </option>
                          <option
                            value="web_app"
                            disabled={hasWebAppButton && button.type !== 'web_app'}
                          >
                            {tr('Open mini app', 'Открыть мини-приложение')}
                          </option>
                        </select>
                      </label>
                    </div>

                    {button.type === 'url' ? (
                      <label className="admin-final-url-field">
                        <span>{tr('URL', 'Ссылка')}</span>
                        <input
                          className="admin-input"
                          value={button.url}
                          onChange={(e) => updateFinalMessageButton(button.id, { url: e.target.value })}
                          maxLength={1000}
                          placeholder="https://example.com"
                        />
                      </label>
                    ) : button.type === 'menu' ? (
                      <div className="admin-final-menu-note">
                        {tr('Sends the complete main bot menu, identical to the /start response.', 'Отправит полноценное главное меню бота — такое же, как после команды /start.')}
                      </div>
                    ) : (
                      <div className="admin-final-menu-note">
                        {tr('Opens the Elizabeth Vane mini app immediately. Its URL is loaded automatically.', 'Сразу откроет мини-приложение Elizabeth Vane. Ссылка берётся из системы автоматически.')}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {!finalMessageConfig.buttons.length ? (
                <div className="admin-final-empty">
                  {tr('No buttons yet. Add a URL, bot menu or mini app.', 'Кнопок пока нет. Добавьте ссылку, меню бота или мини-приложение.')}
                </div>
              ) : null}
            </div>

            <div className="admin-final-preview">
              <div className="admin-final-preview-title">{tr('Telegram preview', 'Предпросмотр в Telegram')}</div>
              <div className="admin-final-preview-bubble">
                <div className="admin-final-preview-text">
                  {finalMessageConfig.message_text || tr('Final message text', 'Текст финального сообщения')}
                </div>
                <div className="admin-final-preview-buttons">
                  {finalMessageConfig.buttons.map((button) => (
                    <div key={`preview-${button.id}`}>
                      <span>{button.text || tr('Untitled', 'Без названия')}</span>
                      <b>{button.type === 'menu' ? 'MENU' : (button.type === 'web_app' ? 'APP' : '↗')}</b>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {error ? <div className="admin-error">{error}</div> : null}
        {status ? <div className="admin-success">{status}</div> : null}

        <div className="admin-funnel-save-bar">
          <span>{tr('Settings from all three tabs are saved together', 'Сохраняются настройки всех трёх вкладок')}</span>
          <button className="admin-btn" onClick={() => saveSettings('support')} disabled={saving}>
            {saving ? tr('Saving…', 'Сохранение...') : tr('Save funnel', 'Сохранить воронку')}
          </button>
        </div>
      </div>
    );
  }

  if (activeSection === 'pocket') {
    return (
      <div className="admin-card admin-settings-detail">
        <div className="admin-row-between">
          <h3 className="admin-section-title">API</h3>
          <button className="admin-btn-outline" onClick={goMenu}>{tr('← Back to settings', '← К карточкам')}</button>
        </div>

        <div className="admin-muted">
          {tr(
            'Pocket Partners settings. The token is stored on the backend and shown only as a mask: first 2 and last 2 characters.',
            'Настройки Pocket Partners. Токен хранится на backend и показывается только маской: первые 2 и последние 2 символа.'
          )}
        </div>

        <div className="admin-field">
          <label className="admin-label">{tr('Account ID / Partner ID', 'ID кабинета / Partner ID')}</label>
          <input
            className="admin-input"
            placeholder={tr('For example 123456', 'Например 123456')}
            value={pocketPartnerId}
            onChange={(e) => setPocketPartnerId(e.target.value.replace(/[^\w.-]/g, '').slice(0, 64))}
          />
        </div>

        <div className="admin-field">
          <label className="admin-label">API token</label>
          <input
            className="admin-input"
            type="password"
            placeholder={pocketApiTokenConfigured
              ? tr(`Current: ${pocketApiTokenMasked}. Enter a new value to replace it`, `Текущий: ${pocketApiTokenMasked}. Введите новый для замены`)
              : tr('Enter API token', 'Введите API token')}
            value={pocketApiToken}
            onChange={(e) => setPocketApiToken(e.target.value)}
            autoComplete="new-password"
          />
        </div>

        <div className="admin-row-actions">
          <button className="admin-btn" onClick={() => saveSettings('pocket')} disabled={saving}>
            {saving ? tr('Saving…', 'Сохранение...') : tr('Save API', 'Сохранить API')}
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
        <h3 className="admin-section-title">{tr('Section not found', 'Раздел не найден')}</h3>
        <button className="admin-btn-outline" onClick={goMenu}>{tr('← Back to settings', '← К карточкам')}</button>
      </div>
      <div className="admin-muted">{tr('Return to the settings list.', 'Вернитесь к списку настроек.')}</div>
    </div>
  );
}
