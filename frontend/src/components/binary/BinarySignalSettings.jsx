import React, { useState, useEffect, useRef } from 'react';
import Loader from '../Loader/Loader';
import Lottie from 'lottie-react';
import animationData from '../../assets/analize.json';
import { apiFetchJson } from '../../lib/api';
import './BinarySignalSettings.css';
import iconEdit from '../../assets/icons/edit.svg?url';

const DEFAULT_MARKETS = [
  { key: 'forex', title: 'Forex' },
  { key: 'otc', title: 'OTC' },
  { key: 'commodities', title: 'Metals' },
  { key: 'stocks', title: 'Stocks' },
  { key: 'crypto', title: 'Crypto' }
];

const DEFAULT_EXPIRATIONS = ['5s', '15s', '1m', '3m', '5m', '15m', '1h'].map(value => ({ value, label: value }));

function normalizeExpirationOptions(items) {
  const source = Array.isArray(items) && items.length ? items : DEFAULT_EXPIRATIONS;
  const seen = new Set();
  return source.reduce((acc, item) => {
    const value = String(item?.value || item?.label || item || '').trim().toLowerCase();
    if (!value || seen.has(value)) return acc;
    seen.add(value);
    acc.push({ value, label: item?.label || value });
    return acc;
  }, []);
}

function getExpirationSeconds(value) {
  const raw = String(value || '').trim().toLowerCase();
  const match = raw.match(/^(\d+)\s*([smh])$/);
  if (!match) return 60;
  const amount = Number(match[1]);
  if (!Number.isFinite(amount) || amount <= 0) return 60;
  if (match[2] === 's') return amount;
  if (match[2] === 'm') return amount * 60;
  if (match[2] === 'h') return amount * 60 * 60;
  return 60;
}

function formatCountdown(totalSeconds) {
  const total = Math.max(0, Number(totalSeconds || 0));
  const minutes = Math.floor(total / 60);
  const seconds = Math.floor(total % 60);
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function safeRender(value, fallback = '---') {
  if (value === null || value === undefined || value === '') return fallback;
  if (typeof value === 'object') {
    const primitive = Object.values(value).find(item => typeof item !== 'object');
    return primitive !== undefined ? String(primitive) : fallback;
  }
  return String(value);
}

function formatPrice(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return '---';
  if (parsed >= 100) return parsed.toFixed(2);
  if (parsed >= 1) return parsed.toFixed(4);
  return parsed.toFixed(6);
}

function formatLevelValue(value) {
  const parsed = Number(String(value ?? '').replace(',', '.'));
  if (Number.isFinite(parsed)) return formatPrice(parsed);
  return safeRender(value);
}

export default function BinarySignalSettings({
  t: globalT,
  binaryParams,
  setBinaryParams,
  onGoHome,
  setBackHandler,
  user = {},
  strategies = []
}) {
  const t = globalT.binarySettings;
  const disclaimerText = globalT.binaryAnalytics.disclaimer;

  const [pairs, setPairs] = useState([]);
  const [availableMarkets, setAvailableMarkets] = useState(DEFAULT_MARKETS);
  const [expOptions, setExpOptions] = useState(DEFAULT_EXPIRATIONS);
  const [marketKind, setMarketKind] = useState(binaryParams.market || 'forex');
  const [loadError, setLoadError] = useState('');
  const [loading, setLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [loadingPhraseIndex, setLoadingPhraseIndex] = useState(0);
  const [analysisData, setAnalysisData] = useState(null);
  const [timeStats, setTimeStats] = useState({ remaining: 0, expired: false });
  const settleStartedRef = useRef(false);
  const expirationDeadlineRef = useRef(null);

  const [editMode, setEditMode] = useState(null);

  const appliedStrategyId = user?.strategy_id;
  const selectedStrategy = strategies?.find(s => Number(s.id) === Number(appliedStrategyId)) || strategies?.find(s => s.is_system) || {};

  useEffect(() => {
    if (setBackHandler) {
      setBackHandler(() => {
        if (editMode) {

          setEditMode(null);
        } else if (analysisData) {

          setAnalysisData(null);
        } else {

          onGoHome();
        }
      });
    }
  }, [editMode, analysisData, onGoHome, setBackHandler]);

  useEffect(() => {
    let isActive = true;
    setLoading(true);
    setLoadError('');

    apiFetchJson(`/api/market/options?kind=${encodeURIComponent(marketKind)}`)
      .then(data => {
        if (!isActive) return;
        const nextMarkets = Array.isArray(data?.available_markets) && data.available_markets.length
          ? data.available_markets
          : DEFAULT_MARKETS;
        const nextPairs = Array.isArray(data?.pairs) ? data.pairs : [];
        const nextExp = normalizeExpirationOptions(data?.expirations);

        setAvailableMarkets(nextMarkets);
        setPairs(nextPairs);
        setExpOptions(nextExp);

        if (nextPairs.length > 0) {
          setBinaryParams(prev => ({
            market: data?.kind || marketKind,
            pair: prev.market === (data?.kind || marketKind) && prev.pair && nextPairs.some(p => p.pair === prev.pair)
              ? prev.pair
              : nextPairs[0].pair,
            exp: prev.exp && nextExp.some(item => item.value === prev.exp)
              ? prev.exp
              : nextExp[0]?.value || '5m'
          }));
        } else {
          setBinaryParams(prev => ({
            ...prev,
            market: data?.kind || marketKind,
            pair: null,
            exp: prev.exp && nextExp.some(item => item.value === prev.exp)
              ? prev.exp
              : nextExp[0]?.value || '5m'
          }));
        }
        setLoading(false);
      })
      .catch((error) => {
        if (!isActive) return;
        setPairs([]);
        setExpOptions(DEFAULT_EXPIRATIONS);
        setLoadError(error.message || 'Failed to load markets');
        setLoading(false);
      });
    return () => {
      isActive = false;
    };
  }, [marketKind, setBinaryParams]);

  useEffect(() => {
    let intervalId;
    if (isProcessing) {
      intervalId = setInterval(() => {
        setLoadingPhraseIndex(prev => (prev + 1) % (globalT.loadingPhrases?.length || 1));
      }, 1500);
    }
    return () => clearInterval(intervalId);
  }, [isProcessing, globalT.loadingPhrases]);

  useEffect(() => {
    if (!analysisData || analysisData.status !== 'active') return undefined;
    settleStartedRef.current = false;
    const serverRemaining = Number(analysisData.remaining_seconds);
    if (Number.isFinite(serverRemaining) && serverRemaining >= 0) {
      expirationDeadlineRef.current = Date.now() + serverRemaining * 1000;
    } else {
      const createdAtRaw = analysisData.created_at || analysisData.raw_data?.fetched_at || new Date().toISOString();
      const createdAtMs = new Date(String(createdAtRaw).replace(' ', 'T')).getTime();
      const totalSeconds = getExpirationSeconds(analysisData.timeframe || binaryParams.exp);
      expirationDeadlineRef.current = createdAtMs + totalSeconds * 1000;
    }
    const tick = () => {
      const deadline = expirationDeadlineRef.current || Date.now();
      const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      setTimeStats({ remaining, expired: remaining <= 0 });
      if (remaining <= 0 && !settleStartedRef.current) {
        settleStartedRef.current = true;
        handleSettleSignal(analysisData.id);
      }
    };
    tick();
    const intervalId = setInterval(tick, 1000);
    return () => clearInterval(intervalId);
  }, [analysisData?.id, analysisData?.status, analysisData?.remaining_seconds, analysisData?.created_at, analysisData?.timeframe, binaryParams.exp]);

  const handleSelectPair = (pairStr) => {
    setBinaryParams({ ...binaryParams, market: marketKind, pair: pairStr });
    setEditMode(null);
  };

  const handleSelectExp = (expStr) => {
    setBinaryParams({ ...binaryParams, exp: expStr });
    setEditMode(null);
  };

  const handleSelectMarket = (market) => {
    setMarketKind(market);
    setBinaryParams(prev => ({ ...prev, market, pair: null }));
  };

  const handleSettleSignal = async (analysisId) => {
    if (!analysisId) return;
    try {
      const result = await apiFetchJson('/api/analysis/settle', {
        method: 'POST',
        body: JSON.stringify({ analysis_id: analysisId })
      });
      if (result?.analysis) {
        setAnalysisData(result.analysis);
      }
    } catch (error) {
      setTimeStats(prev => ({ ...prev, expired: true, error: error.message || 'Unable to close signal' }));
    }
  };

  const handleGetSignal = async () => {
    if (!binaryParams.pair || !binaryParams.exp || isProcessing) return;
    setIsProcessing(true);
    setAnalysisData(null);
    setEditMode(null);
    setLoadError('');
    settleStartedRef.current = false;
    const stratKeys = selectedStrategy?.indicator_keys
      ? selectedStrategy.indicator_keys.split(',').map(item => item.trim().toUpperCase()).filter(Boolean)
      : [];
    const startTime = Date.now();
    const uiDelay = Math.floor(Math.random() * 2500) + 2500;
    try {
      const result = await apiFetchJson('/api/analysis/binary', {
        method: 'POST',
        body: JSON.stringify({
          market: binaryParams.market || marketKind,
          pair: binaryParams.pair,
          exp: binaryParams.exp,
          strategy_id: user.strategy_id,
          allowed_indicators: stratKeys
        })
      });
      const wait = uiDelay - (Date.now() - startTime);
      if (wait > 0) await new Promise(resolve => setTimeout(resolve, wait));
      if (result?.status === 'success') {
        setAnalysisData(result.analysis || {
          id: result.analysis_id,
          pair: binaryParams.pair,
          timeframe: binaryParams.exp,
          strategy_id: user.strategy_id,
          analysis_type: 'binary',
          market_kind: binaryParams.market || marketKind,
          status: 'active',
          raw_data: result.data,
          created_at: new Date().toISOString()
        });
      } else {
        throw new Error(result?.error || t.noDataError || 'Signal is unavailable');
      }
    } catch (error) {
      setLoadError(error.message || t.noDataError || 'Signal is unavailable');
    } finally {
      setIsProcessing(false);
    }
  };

  if (isProcessing) {
    return (
      <div className="profile-wrapper">
        <div className="loading-screen-container fade-in">
          <Lottie animationData={animationData} loop={true} className="loading-lottie" />
          <div className="loading-text-dynamic">{globalT.loadingPhrases?.[loadingPhraseIndex] || 'Analyzing market...'}</div>
        </div>
      </div>
    );
  }

  if (loading) {
    return <Loader t={globalT} />;
  }

  if (analysisData) {
    const data = analysisData.raw_data || {};
    const normalizedIndicators = {};
    Object.entries(data.indicators || {}).forEach(([key, ind]) => {
      if (key === 'EMA9_21' && ind?.value && typeof ind.value === 'object') {
        normalizedIndicators.EMA9 = { value: ind.value.e9, signal: ind.signal };
        normalizedIndicators.EMA21 = { value: ind.value.e21, signal: ind.signal };
      } else {
        normalizedIndicators[key] = ind;
      }
    });
    const filteredInds = Object.entries(normalizedIndicators);
    const votes = { BUY: 0, SELL: 0, NEUTRAL: 0 };
    filteredInds.forEach(([, ind]) => {
      const signal = String(ind?.signal || '').toUpperCase();
      if (signal === 'BUY') votes.BUY += 1;
      else if (signal === 'SELL') votes.SELL += 1;
      else votes.NEUTRAL += 1;
    });
    const totalVotes = votes.BUY + votes.SELL + votes.NEUTRAL;
    const buyPct = totalVotes > 0 ? Math.round((votes.BUY / totalVotes) * 100) : 0;
    const sellPct = totalVotes > 0 ? Math.round((votes.SELL / totalVotes) * 100) : 0;
    const neutralPct = totalVotes > 0 ? Math.round((votes.NEUTRAL / totalVotes) * 100) : 0;
    const pointerPosition = 50 + (buyPct * 0.5) - (sellPct * 0.5);
    const signal = String(data.recommendation || data.signal || 'NEUTRAL').toUpperCase();
    const signalTone = signal === 'BUY' ? 'sig-buy' : signal === 'SELL' ? 'sig-sell' : 'sig-neutral';
    const price = analysisData.entry_price || data.entry_price || data.price;
    const finalPrice = analysisData.exit_price;
    const isActive = analysisData.status === 'active' && ['BUY', 'SELL'].includes(signal);
    const resultLabel = analysisData.status === 'success'
      ? 'Success'
      : analysisData.status === 'fail'
        ? 'Failed'
        : analysisData.status === 'skipped'
          ? 'Skipped'
          : 'Active signal';
    const resultClass = analysisData.status === 'success'
      ? 'binary-result-success'
      : analysisData.status === 'fail'
        ? 'binary-result-fail'
        : 'binary-result-active';

    return (
      <div className="profile-wrapper analysis-result-container">
        <div className="analysis-head">
          <h2 className="settings-main-title analysis-asset-title">{safeRender(analysisData.pair || data.symbol || binaryParams.pair)}</h2>
          <div className="analysis-meta-row">
            <span>{safeRender(analysisData.timeframe || data.selected_expiration || binaryParams.exp)}</span>
            <span>{formatPrice(price)}</span>
          </div>
          <div className="analysis-strategy-row">
            {globalT.analysisSettings?.strategyLabel || 'Strategy'}:
            <span className="analysis-strategy-value">
              <span style={{ fontSize: '1.1em' }}>{safeRender(selectedStrategy?.icon, '\u26A1')}</span>
              {safeRender(selectedStrategy?.name || analysisData.strategy_name || 'System Strategy')}
            </span>
          </div>
        </div>

        <div className="binary-signal-hero">
          <span className="binary-signal-caption">Signal</span>
          <strong className={signalTone}>{signal}</strong>
          <small>{safeRender(data.confidence, 0)}% confidence</small>
        </div>

        <div className="clean-analysis-card">
          <div className="indicator-grid">
            {filteredInds.map(([key, ind]) => (
              <div key={key} className="ind-item">
                <span className="ind-name">{safeRender(key)}</span>
                <span className="ind-val">{typeof ind?.value === 'number' ? ind.value.toFixed(3) : safeRender(ind?.value)}</span>
                <span className={`ind-sig ${ind?.signal === 'BUY' ? 'sig-buy' : ind?.signal === 'SELL' ? 'sig-sell' : 'sig-neutral'}`}>
                  {safeRender(ind?.signal)}
                </span>
              </div>
            ))}
          </div>

          <div className="recommendation-gauge-container" style={{ borderTop: '1px dashed rgba(212, 175, 55, 0.3)', marginTop: '12px', paddingTop: '12px' }}>
            <div className="gauge-title">{globalT.analysisSettings?.overallForecast || 'Consensus'}</div>
            <div className="gauge-bar-bg">
              <div className="gauge-pointer" style={{ left: `${pointerPosition}%` }}></div>
            </div>
            <div className="gauge-labels">
              <span className="gl-sell">SELL ({votes.SELL}) {sellPct}%</span>
              <span className="gl-neutral">NEUTRAL ({votes.NEUTRAL}) {neutralPct}%</span>
              <span className="gl-buy">BUY ({votes.BUY}) {buyPct}%</span>
            </div>
          </div>

          {data.key_levels && (
            <div className="levels-list binary-levels-list">
              <div className="level-row">
                <span className="level-label">{globalT.analysisSettings?.conservativeSl || 'Conservative SL'}</span>
                <span className="level-val">{formatLevelValue(data.key_levels.conservative_sl)}</span>
              </div>
              <div className="level-row">
                <span className="level-label">{globalT.analysisSettings?.targetLabel || 'Target'}</span>
                <span className="level-val">{formatLevelValue(data.key_levels.rr_2_1_target)}</span>
              </div>
            </div>
          )}
        </div>

        <div className={`binary-result-card ${resultClass}`}>
          <div>
            <span>Result</span>
            <strong>{resultLabel}</strong>
          </div>
          {isActive ? (
            <div className="binary-countdown">
              <span>Closes in</span>
              <strong>{formatCountdown(Number.isFinite(Number(timeStats.remaining)) ? timeStats.remaining : (analysisData.remaining_seconds || getExpirationSeconds(analysisData.timeframe)))}</strong>
            </div>
          ) : (
            <div className="binary-countdown">
              <span>Final price</span>
              <strong>{formatPrice(finalPrice)}</strong>
            </div>
          )}
        </div>

        {timeStats.error && <div className="market-load-error">{timeStats.error}</div>}

        <button className="conduct-analysis-btn" onClick={() => setAnalysisData(null)}>
          {t.getNewAnalysis || 'Get new signal'}
        </button>

        <div className="actions-wrapper" style={{ marginTop: '12px' }}>
          <button className="go-back-outline-btn" onClick={onGoHome}>
            {t.goHome}
          </button>
        </div>

        <div className="disclaimer-box">
          <p>{disclaimerText}</p>
        </div>
      </div>
    );
  }

  if (pairs.length === 0) {
    return (
      <div className="profile-wrapper">
        <div className="empty-market-card">
          <div className="market-chip-grid empty-market-switcher">
            {availableMarkets.map((market) => (
              <button
                key={market.key}
                type="button"
                className={`market-chip-btn ${marketKind === market.key ? 'active' : ''}`}
                onClick={() => handleSelectMarket(market.key)}
              >
                {market.title}
              </button>
            ))}
          </div>
          <p>{t.marketClosed}</p>
          {loadError && <div className="market-load-error">{loadError}</div>}
          <button className="binary-cta-btn" style={{ marginTop: '20px' }} onClick={onGoHome}>
            {t.goHome}
          </button>
        </div>
      </div>
    );
  }

  const isSelectingPair = editMode === 'pair';
  const isSelectingExp = editMode === 'exp';
  const isShowingSummary = !editMode && binaryParams.pair && binaryParams.exp;
  const selectedMarketTitle = availableMarkets.find(m => m.key === (binaryParams.market || marketKind))?.title || marketKind.toUpperCase();

  return (
    <div className="profile-wrapper">

      {isSelectingPair && (
        <div className="step-container fade-in">
          <h3 className="settings-main-title">{t.selectPair}</h3>
          <div className="market-chip-grid">
            {availableMarkets.map((market) => (
              <button
                key={market.key}
                type="button"
                className={`market-chip-btn ${marketKind === market.key ? 'active' : ''}`}
                onClick={() => handleSelectMarket(market.key)}
              >
                {market.title}
              </button>
            ))}
          </div>
          {loadError && <div className="market-load-error">{loadError}</div>}
          <div className="pairs-grid">
            {pairs.map((p, idx) => (
              <button key={idx} className="pair-item-btn" onClick={() => handleSelectPair(p.pair)}>
                <span className="pair-name">{p.pair}</span>
                {typeof p.payout === 'number' && <span className="pair-payout">{p.payout}%</span>}
              </button>
            ))}
          </div>
        </div>
      )}

      {isSelectingExp && (
        <div className="step-container fade-in">
          <h3 className="settings-main-title">{t.selectExpiration}</h3>
          <div className="exp-grid">
            {expOptions.map((exp, idx) => (
              <button key={exp.value || idx} className="exp-item-btn" onClick={() => handleSelectExp(exp.value)}>
                {exp.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {isShowingSummary && (
        <div className="summary-step fade-in">
          <h3 className="settings-main-title" style={{ marginBottom: '20px', fontSize: '0.95rem' }}>
            {t.summaryTitle}
          </h3>

          <div className="summary-cards-container">
            <div className="summary-row-box" onClick={() => setEditMode('pair')}>
              <div className="summary-info">
                <span className="summary-label">{t.marketLabel || 'Market'}</span>
                <span className="summary-value">{selectedMarketTitle}</span>
              </div>
              <div className="icon-edit-btn">
                <span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span>
              </div>
            </div>

            <div className="summary-row-box" onClick={() => setEditMode('pair')}>
              <div className="summary-info">
                <span className="summary-label">{t.pairLabel}</span>
                <span className="summary-value highlight">{binaryParams.pair}</span>
              </div>
              <div className="icon-edit-btn">
                <span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span>
              </div>
            </div>

            <div className="summary-row-box" onClick={() => setEditMode('exp')}>
              <div className="summary-info">
                <span className="summary-label">{t.expirationLabel}</span>
                <span className="summary-value highlight">{binaryParams.exp}</span>
              </div>
              <div className="icon-edit-btn">
                <span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span>
              </div>
            </div>


            <div className="summary-row-box" style={{ cursor: 'default' }}>
              <div className="summary-info">
                <span className="summary-label">{globalT.analysisSettings?.strategyLabel || 'Strategy'}</span>
                <span className="summary-value" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '1.1em' }}>{selectedStrategy?.icon || '\u26A1'}</span>
                  {selectedStrategy?.name || 'System Strategy'}
                </span>
              </div>

            </div>

          </div>

          {loadError && <div className="market-load-error">{loadError}</div>}
          <button className="conduct-analysis-btn" onClick={handleGetSignal} disabled={isProcessing}>
            {t.getSignalBtn}
          </button>
        </div>
      )}


      <div className="actions-wrapper" style={{ marginTop: '30px' }}>
        <button className="go-back-outline-btn" onClick={onGoHome}>
          {t.goHome}
        </button>
      </div>

      <div className="disclaimer-box">
        <p>{disclaimerText}</p>
      </div>

    </div>
  );
}
