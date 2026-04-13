import React, { useState, useEffect } from 'react';
import Loader from '../Loader/Loader';
import Lottie from 'lottie-react';
import animationData from '../../assets/analize.json';
import './ForexAnalysisSettings.css';
import iconEdit from '../../assets/icons/edit.svg?url';
import TradingViewChart from './TradingViewChart';
import NewsModal from './NewsModal';
import { apiFetchJson } from '../../lib/api';

import * as Flags from 'country-flag-icons/react/3x2';

const AssetIcon = ({ asset }) => {
  if (!asset) return null;
  if (asset.country) {
    const Flag = Flags[asset.country === 'EU' ? 'EU' : asset.country];
    return Flag ? <Flag title={asset.country} style={{ width: '22px', borderRadius: '3px', display: 'inline-block' }} /> : null;
  }
  if (asset.icon) {
    return <span style={{ fontSize: '1.2rem' }}>{String(asset.icon)}</span>;
  }
  return null;
};

export default function ForexAnalysisSettings({ 
  user, 
  strategies, 
  t: globalT, 
  forexParams, 
  setForexParams, 
  onGoHome, 
  onGoProfile,
  onUpdateStrategy,
  activeAnalysisPreload = null,
  setBackHandler
}) {
  const t = globalT.analysisSettings;
  
  const [assetsData, setAssetsData] = useState({ Currencies: [], Indices: [], Commodities: [], Stocks: [] });
  const [loadingAssets, setLoadingAssets] = useState(true);

  const [editMode, setEditMode] = useState(null); 
  const [isProcessing, setIsProcessing] = useState(false);
  const [loadingPhraseIndex, setLoadingPhraseIndex] = useState(0);
  const [analysisData, setAnalysisData] = useState(activeAnalysisPreload);
  const [timeStats, setTimeStats] = useState({ passed: 0, remaining: 0, expired: false });
  const [news, setNews] = useState(null);
  const [isNewsModalOpen, setIsNewsModalOpen] = useState(false);
  
  const [assetType, setAssetType] = useState('Currencies');
  const expOptions = ['5m', '15m', '30m', '1h', '4h', '1d'];

  const appliedStrategyId = analysisData?.strategy_id || user.strategy_id;
  const selectedStrategy = strategies.find(s => Number(s.id) === Number(appliedStrategyId)) || {};

  const allowedTfString = selectedStrategy.allowed_timeframes;
  const allowedTimeframes = allowedTfString 
    ? allowedTfString.split(',').map(s => s.trim()) 
    : expOptions;

  const recommendedExp = expOptions.filter(exp => allowedTimeframes.includes(exp));
  const unavailableExp = expOptions.filter(exp => !allowedTimeframes.includes(exp));

  const safeRender = (val, defaultValue = '---') => {
    if (val === null || val === undefined) return defaultValue;
    if (typeof val === 'object') {
      const firstPrimitive = Object.values(val).find(v => typeof v !== 'object');
      return firstPrimitive !== undefined ? String(firstPrimitive) : defaultValue;
    }
    return String(val);
  };

  const formatPrice = (price) => {
    if (typeof price === 'number') return price.toFixed(3);
    return safeRender(price);
  };

  const formatLevelValue = (value) => {
    if (typeof value === 'number') return value.toFixed(3);
    if (typeof value === 'string') {
      const normalized = value.replace(',', '.').trim();
      const matched = normalized.match(/-?\d+(\.\d+)?/);
      const parsed = matched ? Number(matched[0]) : Number(normalized);
      if (Number.isFinite(parsed)) return parsed.toFixed(3);
    }
    return safeRender(value);
  };

  useEffect(() => {
    if (setBackHandler) {
      setBackHandler(() => {
        if (editMode) {
          setEditMode(null);
        } else if (analysisData) {
          if (activeAnalysisPreload) {
            onGoHome();
          } else {
            setAnalysisData(null);
          }
        } else {
          onGoHome();
        }
      });
    }
  }, [editMode, analysisData, onGoHome, setBackHandler, activeAnalysisPreload]);

  useEffect(() => {
    if (activeAnalysisPreload) {
      setAnalysisData(activeAnalysisPreload);
      if (activeAnalysisPreload.news_data) {
        setNews(typeof activeAnalysisPreload.news_data === 'string' 
          ? JSON.parse(activeAnalysisPreload.news_data) 
          : activeAnalysisPreload.news_data);
      } else {
        setNews({ economicCalendar: [] });
      }
    }
  }, [activeAnalysisPreload]);

  const getExpirationMs = (tf) => {
    if (!tf) return 5 * 60 * 1000;
    const val = parseInt(tf);
    if (tf.includes('m')) return val * 60 * 1000;
    if (tf.includes('h')) return val * 60 * 60 * 1000;
    if (tf.includes('d')) return val * 24 * 60 * 60 * 1000;
    return 5 * 60 * 1000;
  };

  useEffect(() => {
    Promise.all([
      apiFetchJson('/api/pairs/forex').catch(() => ({ pairs: [] })),
      apiFetchJson('/api/pairs/indices').catch(() => []),
      apiFetchJson('/api/pairs/commodity').catch(() => []),
      apiFetchJson('/api/pairs/otc/stocks').catch(() => ({ assets: [] }))
    ])
    .then(([forexData, indicesData, commData, stocksData]) => {
      const formatted = {
        Currencies: (forexData?.pairs || []).map(p => ({ apiVal: p.pair, name: p.pair })),
        Indices: (Array.isArray(indicesData) ? indicesData : []).map(p => ({ apiVal: p.apiVal || p.symbol, name: p.name, icon: p.icon, country: p.country, exchange: p.exchange })),
        Commodities: (Array.isArray(commData) ? commData : []).map(p => ({ apiVal: p.symbol || p.apiVal, name: p.name, icon: p.icon, exchange: p.exchange })),
        Stocks: (stocksData?.assets || []).map(p => ({ apiVal: p.asset, name: p.asset }))
      };
      setAssetsData(formatted);
      setLoadingAssets(false);

      if (!activeAnalysisPreload) {
        setForexParams(prev => ({
          pair: prev.pair || formatted.Currencies[0]?.apiVal,
          exp: prev.exp || recommendedExp[0] || expOptions[0]
        }));
      }
    })
    .catch(err => {
      console.error(err);
      setLoadingAssets(false);
    });

    if (!activeAnalysisPreload) {
      apiFetchJson('/api/news')
        .then(data => setNews(data))
        .catch(err => console.error("News fetch error", err));
    }
  }, [activeAnalysisPreload]);

  useEffect(() => {
    let interval;
    if (isProcessing) {
      interval = setInterval(() => {
        setLoadingPhraseIndex(prev => (prev + 1) % globalT.loadingPhrases.length);
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [isProcessing, globalT.loadingPhrases]);

  useEffect(() => {
    let timer;
    if (analysisData) {
      const createdAtStr = analysisData.raw_data?.fetched_at || analysisData.created_at || new Date().toISOString();
      const createdAtMs = new Date(createdAtStr.replace(' ', 'T') + (!createdAtStr.includes('Z') ? 'Z' : '')).getTime();
      const expStr = analysisData.timeframe || forexParams.exp || "5m";
      const expirationMs = getExpirationMs(expStr);

      timer = setInterval(() => {
        const now = Date.now();
        const passedMs = now - createdAtMs;
        const remainingMs = (createdAtMs + expirationMs) - now;
        
        setTimeStats({
          passed: Math.max(0, Math.floor(passedMs / 1000)),
          remaining: Math.max(0, Math.floor(remainingMs / 1000)),
          expired: remainingMs <= 0
        });
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [analysisData, forexParams.exp]);

  const getAssetObject = (apiVal) => {
    const valString = String(apiVal);
    for (const cat in assetsData) {
      const match = assetsData[cat].find(p => String(p.apiVal) === valString);
      if (match) return match;
    }
    return { name: valString, apiVal: valString };
  };

  const formatCountdown = (totalSeconds) => {
    const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const s = (totalSeconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const formatPassedTime = (totalSeconds) => {
    if (totalSeconds < 60) return `${totalSeconds} ${t.timeSec} ${t.timeAgo}`;
    const m = Math.floor(totalSeconds / 60);
    if (m < 60) return `${m} ${t.timeMin} ${t.timeAgo}`;
    const h = Math.floor(m / 60);
    const rm = m % 60;
    if (h < 24) return `${h} ${t.timeH} ${rm} ${t.timeMin} ${t.timeAgo}`;
    const d = Math.floor(h / 24);
    const rh = h % 24;
    return `${d} ${t.timeD} ${rh} ${t.timeH} ${rm} ${t.timeMin} ${t.timeAgo}`;
  };

  const getFilteredNewsStatus = (pairSymbol) => {
    if (!news || !news.economicCalendar) return { isCalm: true, events: [], warningEvents: [], noNews: true };
    const now = Date.now();
    const thirtyMinsMs = 30 * 60 * 1000;
    let baseCurrencies = [];
    if (pairSymbol) {
      const cleanPair = String(pairSymbol).replace(/[^A-Za-z]/g, '').toUpperCase();
      if (cleanPair.length >= 6) {
        baseCurrencies.push(cleanPair.substring(0, 3));
        baseCurrencies.push(cleanPair.substring(3, 6));
      }
    }
    const relevantEvents = news.economicCalendar.filter(item => {
      const timeStr = item.time.includes('Z') ? item.time : item.time.replace(' ', 'T') + 'Z';
      const eventTime = new Date(timeStr).getTime();
      if (now > eventTime + thirtyMinsMs) return false;
      if (baseCurrencies.length > 0) {
        const itemCur = item.currency || 'ALL';
        if (itemCur !== 'ALL' && !baseCurrencies.includes(itemCur)) return false;
      }
      return true;
    }).sort((a, b) => {
       const tA = new Date(a.time.includes('Z') ? a.time : a.time.replace(' ', 'T') + 'Z').getTime();
       const tB = new Date(b.time.includes('Z') ? b.time : b.time.replace(' ', 'T') + 'Z').getTime();
       return tA - tB;
    });
    let hasWarning = false;
    const warningEvents = relevantEvents.filter(item => {
      const timeStr = item.time.includes('Z') ? item.time : item.time.replace(' ', 'T') + 'Z';
      const eventTime = new Date(timeStr).getTime();
      const diff = eventTime - now;
      if (item.impact === 'high' && diff <= thirtyMinsMs && diff >= -thirtyMinsMs) {
        hasWarning = true;
        return true;
      }
      return false;
    });
    return {
      events: relevantEvents,
      warningEvents: warningEvents,
      isWarning: hasWarning,
      noNews: relevantEvents.length === 0
    };
  };

  if (loadingAssets && !analysisData) return <Loader t={globalT} />;

  const handleConductAnalysis = async () => {
    setAnalysisData(null);
    setIsProcessing(true);
    setEditMode(null);
    const uiDelay = Math.floor(Math.random() * 7000) + 3000; 
    const startTime = Date.now();
    const assetObj = getAssetObject(forexParams.pair);
    const stratKeys = selectedStrategy.indicator_keys 
      ? selectedStrategy.indicator_keys.split(',').map(s => s.trim().toUpperCase()) 
      : [];
    try {
      const result = await apiFetchJson('/api/analysis/forex', {
        method: 'POST',
        body: JSON.stringify({
          pair: forexParams.pair,
          exp: forexParams.exp,
          strategy_id: user.strategy_id,
          allowed_indicators: stratKeys,
          exchange: assetObj?.exchange || null
        })
      });
      const elapsedTime = Date.now() - startTime;
      const remainingWait = uiDelay - elapsedTime;
      if (remainingWait > 0) await new Promise(resolve => setTimeout(resolve, remainingWait));
      if (result.status === 'success') {
        setAnalysisData({
          id: result.analysis_id,
          timeframe: forexParams.exp,
          strategy_id: user.strategy_id, 
          raw_data: result.data,
          news_data: result.news_data, 
          created_at: new Date().toISOString()
        });
        if (result.news_data) setNews(result.news_data);
      } else {
        alert(t.noDataError);
      }
    } catch (error) {
      console.error(error);
      alert(t.noDataError);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleMarkStatus = async (status) => {
    if (!analysisData?.id) return;
    await apiFetchJson('/api/analysis/status', {
      method: 'POST',
      body: JSON.stringify({ analysis_id: analysisData.id, status })
    });
    setAnalysisData(null);
    onGoHome();
  };

  if (isProcessing) {
    return (
      <div className="profile-wrapper">
        <div className="loading-screen-container fade-in">
          <Lottie animationData={animationData} loop={true} className="loading-lottie" />
          <div className="loading-text-dynamic">{globalT.loadingPhrases[loadingPhraseIndex]}</div>
        </div>
      </div>
    );
  }

  if (analysisData) {
    const data = analysisData.raw_data;
    const normalizedIndicators = {};
    Object.entries(data.indicators || {}).forEach(([key, ind]) => {
      if (key === 'EMA9_21' && ind.value && typeof ind.value === 'object') {
        normalizedIndicators['EMA9'] = { value: ind.value.e9, signal: ind.signal };
        normalizedIndicators['EMA21'] = { value: ind.value.e21, signal: ind.signal };
      } else {
        normalizedIndicators[key] = ind;
      }
    });
    const filteredInds = Object.entries(normalizedIndicators);
    const customVotes = { BUY: 0, SELL: 0, NEUTRAL: 0 };
    filteredInds.forEach(([_, ind]) => {
      if (ind.signal === 'BUY') customVotes.BUY += 1;
      else if (ind.signal === 'SELL') customVotes.SELL += 1;
      else customVotes.NEUTRAL += 1;
    });
    const totalVotes = customVotes.BUY + customVotes.SELL + customVotes.NEUTRAL;
    const buyPct = totalVotes > 0 ? Math.round((customVotes.BUY / totalVotes) * 100) : 0;
    const sellPct = totalVotes > 0 ? Math.round((customVotes.SELL / totalVotes) * 100) : 0;
    const neutralPct = totalVotes > 0 ? Math.round((customVotes.NEUTRAL / totalVotes) * 100) : 0;
    const pointerPosition = 50 + (buyPct * 0.5) - (sellPct * 0.5);
    const currentPrice = data.price || data.key_levels?.current_price || '---';
    const analysisSymbol = data.symbol || analysisData.pair;
    const analysisInterval = analysisData.timeframe || data.interval;
    const newsStatus = getFilteredNewsStatus(analysisSymbol);
    const assetObj = getAssetObject(analysisSymbol);

    return (
      <div className="profile-wrapper analysis-result-container">
        <div className="analysis-head">
          <h2 className="settings-main-title analysis-asset-title">
            {assetObj.icon || assetObj.country ? <AssetIcon asset={assetObj} /> : null}
            {safeRender(assetObj.name !== assetObj.apiVal ? assetObj.name : analysisSymbol)}
          </h2>
          <div className="analysis-meta-row">
            <span style={{ background: 'rgba(139, 107, 44, 0.14)', color: 'var(--accent)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.8rem', fontWeight: '500' }}>
              {safeRender(analysisInterval)}
            </span>
            <span style={{ color: 'var(--text-main)', fontSize: '1.1rem', fontWeight: '600' }}>
              {formatPrice(currentPrice)}
            </span>
          </div>
          <div className="analysis-strategy-row">
            {t.strategyLabel}: 
            <span className="analysis-strategy-value">
              <span style={{ fontSize: '1.1em' }}>{safeRender(selectedStrategy.icon, '\u26A1')}</span> 
              {safeRender(selectedStrategy.name || analysisData.strategy_name || 'Custom Strategy')}
            </span>
          </div>
        </div>

        <div className="clean-analysis-card">
          <div className="indicator-grid">
            {filteredInds.map(([key, ind]) => (
              <div key={key} className="ind-item">
                <span className="ind-name">{safeRender(key)}</span>
                <span className="ind-val">{typeof ind.value === 'number' ? ind.value.toFixed(3) : safeRender(ind.value)}</span>
                <span className={`ind-sig ${ind.signal === 'BUY' ? 'sig-buy' : ind.signal === 'SELL' ? 'sig-sell' : 'sig-neutral'}`}>{safeRender(ind.signal)}</span>
              </div>
            ))}
          </div>

          <div className="recommendation-gauge-container" style={{ borderTop: '1px dashed rgba(139, 107, 44, 0.3)', marginTop: '12px', paddingTop: '12px' }}>
            <div className="gauge-title">{t.overallForecast}</div>
            <div className="gauge-bar-bg">
              <div className="gauge-pointer" style={{ left: `${pointerPosition}%` }}></div>
            </div>
            <div className="gauge-labels">
              <span className="gl-sell">SELL ({customVotes.SELL}) {sellPct}%</span>
              <span className="gl-neutral">NEUTRAL ({customVotes.NEUTRAL}) {neutralPct}%</span>
              <span className="gl-buy">BUY ({customVotes.BUY}) {buyPct}%</span>
            </div>
          </div>

          {data.key_levels && (
            <div className="levels-list" style={{ borderTop: '1px dashed rgba(139, 107, 44, 0.3)', marginTop: '10px', paddingTop: '10px' }}>
              <div className="level-row" style={{ borderBottom: 'none', paddingBottom: '0' }}>
                <span className="level-label">{t.conservativeSl}</span>
                <span className="level-val">{formatLevelValue(data.key_levels.conservative_sl)}</span>
              </div>
              <div className="level-row" style={{ borderBottom: 'none', paddingBottom: '0' }}>
                <span className="level-label">{t.targetLabel}</span>
                <span className="level-val">{formatLevelValue(data.key_levels.rr_2_1_target)}</span>
              </div>
            </div>
          )}
          
          <div className="news-filter-block">
            {newsStatus.noNews ? (
              <div className="nf-safe-box" style={{ marginBottom: '10px' }}>{t.noNewsExpected}</div>
            ) : newsStatus.isWarning ? (
              <div className="nf-caution-box" style={{ marginBottom: '10px' }}>
                <div className="nf-caution-title">{'\u26A0\uFE0F'} {t.cautionTrade}</div>
                <div className="nf-events-list" style={{ marginTop: '10px' }}>
                  {newsStatus.warningEvents.slice(0, 3).map((ev, i) => (
                    <div key={i} className="nf-event-item impact-high">
                      {'\uD83D\uDD34'} {ev.time ? ev.time.split(' ')[1]?.substring(0, 5) : ''} {safeRender(ev.currency)} - {safeRender(ev.event)}
                    </div>
                  ))}
                </div>
                <button className="add-strategy-outline-btn" style={{ marginTop: '10px' }} onClick={() => setIsNewsModalOpen(true)}>{t.showNewsBtn}</button>
              </div>
            ) : (
              <div className="nf-safe-box" style={{ marginBottom: '10px' }}>
                {'\u2705'} {t.calmMarket}
                <button className="add-strategy-outline-btn" style={{ marginTop: '10px', borderColor: 'var(--success)', color: 'var(--success)' }} onClick={() => setIsNewsModalOpen(true)}>{t.showNewsBtn}</button>
              </div>
            )}
          </div>
        </div>

        <TradingViewChart symbol={analysisSymbol} interval={analysisInterval} t={globalT} />

        <div className="timer-box" style={{ borderColor: timeStats.expired ? 'var(--danger)' : 'var(--accent)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 5px', alignItems: 'center' }}>
            <div style={{ textAlign: 'left' }}>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{t.analysisTimeAgo}</div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-main)' }}>{formatPassedTime(timeStats.passed)}</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              {!timeStats.expired && <div style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{t.timeRemaining}</div>}
              <div style={{ fontSize: '1.1rem', color: timeStats.expired ? 'var(--danger)' : 'var(--success)', fontWeight: '600' }}>
                {timeStats.expired ? t.expired : formatCountdown(timeStats.remaining)}
              </div>
            </div>
          </div>
        </div>

        <div className="action-buttons-grid">
          <button className="btn-success-mark" onClick={() => handleMarkStatus('success')}>{t.successBtn}</button>
          <button className="btn-skip-mark" onClick={() => handleMarkStatus('skipped')}>{t.skipBtn || 'Skip'}</button>
          <button className="btn-fail-mark" onClick={() => handleMarkStatus('fail')}>{t.failBtn}</button>
        </div>

        <button className="conduct-analysis-btn" style={{ marginTop: '10px', marginBottom: '20px' }} onClick={() => activeAnalysisPreload ? onGoHome() : setAnalysisData(null)}>
          {t.getNewAnalysis || 'Get new analysis'}
        </button>
        
        <NewsModal isOpen={isNewsModalOpen} onClose={() => setIsNewsModalOpen(false)} events={newsStatus.events} t={t} />
      </div>
    );
  }

  const isSelectingAsset = editMode === 'asset';
  const isSelectingPair = editMode === 'pair';
  const isSelectingExp = editMode === 'exp';
  const isSelectingStrategy = editMode === 'strategy';
  const isShowingSummary = !editMode && forexParams.pair && forexParams.exp;

  return (
    <div className="profile-wrapper">
      {isSelectingAsset && (
        <div className="step-container fade-in">
          <h3 className="settings-main-title">{t.selectAsset}</h3>
          <div className="assets-grid">
            {['Currencies', 'Indices', 'Commodities', 'Stocks'].map((type) => {
              if (!assetsData[type] || assetsData[type].length === 0) return null;
              return (
              <button key={type} className={`asset-item-btn ${assetType === type ? 'active' : ''}`} onClick={() => { 
                setAssetType(type); 
                if (assetsData[type] && assetsData[type].length > 0) {
                  setForexParams(p => ({ ...p, pair: assetsData[type][0].apiVal }));
                }
                setEditMode(null); 
              }}>
                {t.assets ? safeRender(t.assets[type.toLowerCase()], type) : type}
              </button>
            )})}
          </div>
        </div>
      )}

      {isSelectingPair && (
        <div className="step-container fade-in">
          <h3 className="settings-main-title">{t.selectPair}</h3>
          <div className="pairs-grid" style={{ gridTemplateColumns: assetType === 'Currencies' ? '' : '1fr' }}>
            {assetsData[assetType]?.map((p) => (
              <button 
                key={String(p.apiVal)} 
                className={`pair-item-btn ${String(forexParams.pair) === String(p.apiVal) ? 'active' : ''}`} 
                onClick={() => { setForexParams({ ...forexParams, pair: p.apiVal }); setEditMode(null); }}
              >
                <AssetIcon asset={p} />
                <span className="pair-name">{safeRender(p.name)}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {isSelectingExp && (
        <div className="step-container fade-in">
          <h3 className="settings-main-title">{t.selectExpiration}</h3>
          <div className="exp-section-title">{'\u2705'}</div>
          <div className="exp-grid">
            {recommendedExp.map((exp) => (
              <button key={exp} className={`exp-item-btn ${forexParams.exp === exp ? 'active' : ''}`} onClick={() => { setForexParams({ ...forexParams, exp }); setEditMode(null); }}>
                {safeRender(exp)}
              </button>
            ))}
          </div>

          {unavailableExp.length > 0 && (
            <>
              <div className="exp-section-title">{'\u274C'}</div>
              <div className="exp-grid">
                {unavailableExp.map((exp) => (
                  <button key={exp} className={`exp-item-btn ${forexParams.exp === exp ? 'active' : ''}`} onClick={() => { setForexParams({ ...forexParams, exp }); setEditMode(null); }}>
                    {safeRender(exp)}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {isSelectingStrategy && (
        <div className="step-container fade-in">
          <h3 className="settings-main-title">{t.selectStrategy}</h3>
          <div className="strategies-grid">
            {strategies.map((strat) => (
              <button key={strat.id} className={`strategy-item-btn ${Number(user.strategy_id) === Number(strat.id) ? 'active' : ''}`} onClick={() => { onUpdateStrategy(strat.id); setEditMode(null); }}>
                <span style={{ fontSize: '1.2rem' }}>{safeRender(strat.icon || '\u26A1')}</span>
                <span>{safeRender(strat.name)}</span>
              </button>
            ))}
          </div>
          <button className="add-strategy-outline-btn" style={{ marginTop: '15px' }} onClick={onGoProfile}>{t.createStrategyBtn}</button>
        </div>
      )}

      {isShowingSummary && (
        <div className="summary-step fade-in">
          <h3 className="settings-main-title" style={{ marginBottom: '20px', fontSize: '0.95rem' }}>{t.summaryTitle}</h3>
          <div className="summary-cards-container">
            <div className="summary-row-box" onClick={() => setEditMode('asset')}>
              <div className="summary-info">
                <span className="summary-label">{t.assetLabel}</span>
                <span className="summary-value highlight">{t.assets ? safeRender(t.assets[assetType.toLowerCase()], assetType) : assetType}</span>
              </div>
              <div className="icon-edit-btn"><span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span></div>
            </div>
            <div className="summary-row-box" onClick={() => setEditMode('pair')}>
              <div className="summary-info">
                <span className="summary-label">{t.pairLabel}</span>
                <span className="summary-value highlight" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {getAssetObject(forexParams.pair).icon || getAssetObject(forexParams.pair).country ? <AssetIcon asset={getAssetObject(forexParams.pair)} /> : null}
                  {safeRender(getAssetObject(forexParams.pair).name)}
                </span>
              </div>
              <div className="icon-edit-btn"><span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span></div>
            </div>
            <div className="summary-row-box" onClick={() => setEditMode('exp')}>
              <div className="summary-info"><span className="summary-label">{t.expirationLabel}</span><span className="summary-value highlight">{safeRender(forexParams.exp)}</span></div>
              <div className="icon-edit-btn"><span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span></div>
            </div>
            <div className="summary-row-box" onClick={() => setEditMode('strategy')}>
              <div className="summary-info">
                <span className="summary-label">{t.strategyLabel}</span>
                <span className="summary-value" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '1.1em' }}>{safeRender(selectedStrategy.icon, '\u26A1')}</span>
                  {safeRender(selectedStrategy.name || '...')}
                </span>
              </div>
              <div className="icon-edit-btn"><span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span></div>
            </div>
          </div>
          <button className="conduct-analysis-btn" onClick={handleConductAnalysis}>{t.conductAnalysisBtn}</button>
        </div>
      )}
    </div>
  );
}


