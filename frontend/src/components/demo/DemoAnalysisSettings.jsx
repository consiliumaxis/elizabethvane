import React, { useState, useEffect } from 'react';
import Lottie from 'lottie-react';
import animationData from '../../assets/analize.json';
import '../forex/ForexAnalysisSettings.css';
import './Demo.css';
import iconEdit from '../../assets/icons/edit.svg?url';
import TradingViewChart from '../forex/TradingViewChart';
import NewsModal from '../forex/NewsModal';
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

export default function DemoAnalysisSettings({ 
  user, strategies, t: globalT, forexParams, setForexParams, onGoHome, setBackHandler, onUpdateStrategy, onGoProfile
}) {
  const t = globalT.analysisSettings;
  const loadingPhrases = globalT.demoLoadingPhrases || globalT.loadingPhrases;
  
  const [editMode, setEditMode] = useState(null); 
  const [isProcessing, setIsProcessing] = useState(false);
  const [loadingPhraseIndex, setLoadingPhraseIndex] = useState(0);
  const [analysisData, setAnalysisData] = useState(null);
  const [news, setNews] = useState(null);
  const [isNewsModalOpen, setIsNewsModalOpen] = useState(false);
  const [assetType, setAssetType] = useState('Commodities');
  
  const [assetsData, setAssetsData] = useState({ Commodities: [], Indices: [] });
  const [loadingAssets, setLoadingAssets] = useState(true);

  const expOptions = ['5m', '15m', '30m', '1h', '4h', '1d'];
  const appliedStrategyId = user.strategy_id;
  const selectedStrategy = strategies.find(s => Number(s.id) === Number(appliedStrategyId)) || strategies.find(s => s.is_system) || {};

  const allowedTfString = selectedStrategy.allowed_timeframes;
  const allowedTimeframes = allowedTfString 
    ? allowedTfString.split(',').map(s => s.trim()) 
    : expOptions;

  const recommendedExp = expOptions.filter(exp => allowedTimeframes.includes(exp));
  const unavailableExp = expOptions.filter(exp => !allowedTimeframes.includes(exp));

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
    Promise.all([
      apiFetchJson('/api/pairs/commodity').catch(() => []),
      apiFetchJson('/api/pairs/indices').catch(() => [])
    ])
    .then(([commData, indicesData]) => {
      const formatted = {
        Commodities: (Array.isArray(commData) ? commData : []).map(p => ({ apiVal: p.symbol || p.apiVal, name: p.name, icon: p.icon, exchange: p.exchange })),
        Indices: (Array.isArray(indicesData) ? indicesData : []).map(p => ({ apiVal: p.apiVal || p.symbol, name: p.name, icon: p.icon, country: p.country, exchange: p.exchange }))
      };
      setAssetsData(formatted);
      setLoadingAssets(false);

      const isPairValid = formatted.Commodities.some(p => String(p.apiVal) === String(forexParams.pair)) || 
                          formatted.Indices.some(p => String(p.apiVal) === String(forexParams.pair));
      
      if (!isPairValid && formatted.Commodities.length > 0) {
        setForexParams(prev => ({ ...prev, pair: formatted.Commodities[0].apiVal, exp: prev.exp || expOptions[0] }));
      } else if (isPairValid) {
        setAssetType(formatted.Indices.some(p => String(p.apiVal) === String(forexParams.pair)) ? 'Indices' : 'Commodities');
      }
    })
    .catch(err => {
      console.error(err);
      setLoadingAssets(false);
    });

    apiFetchJson('/api/news')
      .then(data => setNews(data))
      .catch(console.error);
  }, []);

  useEffect(() => {
    let interval;
    if (isProcessing || loadingAssets) {
      interval = setInterval(() => {
        setLoadingPhraseIndex(prev => (prev + 1) % loadingPhrases.length);
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [isProcessing, loadingAssets, loadingPhrases]);

  const getAssetObject = (apiVal) => {
    const valStr = String(apiVal);
    for (const cat in assetsData) {
      const match = assetsData[cat].find(p => String(p.apiVal) === valStr);
      if (match) return match;
    }
    return { name: valStr, apiVal: valStr };
  };

  const handleConductAnalysis = async () => {
    setAnalysisData(null);
    setIsProcessing(true);
    setEditMode(null);
    const uiDelay = Math.floor(Math.random() * 5000) + 3000; 

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
          strategy_id: selectedStrategy.id || 1,
          allowed_indicators: stratKeys,
          exchange: assetObj?.exchange || null
        })
      });
      
      await new Promise(resolve => setTimeout(resolve, uiDelay));

      if (result.status === 'success') {
        setAnalysisData({
          raw_data: result.data,
          timeframe: forexParams.exp,
          pair: forexParams.pair
        });
      } else {
        alert(t.noDataError);
      }
    } catch (error) {
      alert(t.noDataError);
    } finally {
      setIsProcessing(false);
    }
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
      warningEvents, 
      isWarning: hasWarning, 
      noNews: relevantEvents.length === 0 
    };
  };

  const formatIndValue = (val) => {
    if (val === null || val === undefined) return '...';
    let num = (typeof val === 'object') ? (val.macd ?? val.k ?? val.e9 ?? val.lb ?? Object.values(val).find(v => typeof v === 'number')) : val;
    if (typeof num === 'number') return num.toFixed(3);
    return String(val);
  };

  if (loadingAssets || isProcessing) {
    return (
      <div className="profile-wrapper">
        <div className="loading-screen-container fade-in">
          <Lottie animationData={animationData} loop={true} className="loading-lottie" />
          <div className="loading-text-dynamic">{loadingPhrases[loadingPhraseIndex]}</div>
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

    const getDemoSignalChar = (sig) => sig === 'BUY' ? '\u25B2' : sig === 'SELL' ? '\u25BC' : '\u25CF';
    const getDemoSignalColor = (sig) => sig === 'BUY' ? '#00FF00' : sig === 'SELL' ? '#FF4444' : '#FFD700';
    const currentPrice = data.price || data.key_levels?.current_price || '---';
    const assetObj = getAssetObject(analysisData.pair);
    const newsStatus = getFilteredNewsStatus(analysisData.pair);

    return (
      <div className="profile-wrapper analysis-result-container">
        <div className="analysis-head">
          <h2 className="settings-main-title analysis-asset-title">
            <AssetIcon asset={assetObj} /> {assetObj.name}
          </h2>
          <div className="analysis-meta-row">
            <span style={{ background: 'rgba(139, 107, 44, 0.14)', color: 'var(--accent)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.8rem', fontWeight: '500' }}>
              {analysisData.timeframe}
            </span>
            <span style={{ color: 'var(--text-main)', fontSize: '1.1rem', fontWeight: '600' }}>
              {typeof currentPrice === 'number' ? currentPrice.toFixed(3) : currentPrice}
            </span>
          </div>
        </div>

        <div className="clean-analysis-card">
          <div className="indicator-grid">
            {filteredInds.map(([key, ind]) => (
              <div key={key} className="ind-item">
                <span className="ind-name">{key}</span>
                <span className="ind-val">{formatIndValue(ind.value)}</span>
                <span style={{ color: getDemoSignalColor(ind.signal), fontSize: '1.2rem', marginTop: '3px', fontWeight: '600' }}>
                  {getDemoSignalChar(ind.signal)}
                </span>
              </div>
            ))}
          </div>
          <div className="demo-indicator-summary">
            <div className="demo-summary-title">{globalT.demoSettings?.indicatorSummary || 'Indicator Summary'}</div>
            <span style={{ color: '#00FF00' }}>{'\u25B2'} {customVotes.BUY}</span>{' / '}
            <span style={{ color: '#FFD700' }}>{'\u25CF'} {customVotes.NEUTRAL}</span>{' / '}
            <span style={{ color: '#FF4444' }}>{'\u25BC'} {customVotes.SELL}</span>
          </div>

          <div className="news-filter-block">
            {newsStatus.noNews ? (
              <div className="nf-safe-box" style={{ marginBottom: '10px' }}>
                {t.noNewsExpected}
              </div>
            ) : newsStatus.isWarning ? (
              <div className="nf-caution-box" style={{ marginBottom: '10px' }}>
                <div className="nf-caution-title">{'\u26A0\uFE0F'} {t.cautionTrade}</div>
                <div className="nf-events-list" style={{ marginTop: '10px' }}>
                  {newsStatus.warningEvents.slice(0, 3).map((ev, i) => (
                    <div key={i} className="nf-event-item impact-high">
                      {'\uD83D\uDD34'} {ev.time ? ev.time.split(' ')[1]?.substring(0, 5) : ''} {ev.currency} - {ev.event}
                    </div>
                  ))}
                </div>
                <button className="add-strategy-outline-btn" style={{ marginTop: '10px' }} onClick={() => setIsNewsModalOpen(true)}>
                  {t.showNewsBtn}
                </button>
              </div>
            ) : (
              <div className="nf-safe-box" style={{ marginBottom: '10px' }}>
                {'\u2705'} {t.calmMarket}
                <button className="add-strategy-outline-btn" style={{ marginTop: '10px', borderColor: 'var(--success)', color: 'var(--success)' }} onClick={() => setIsNewsModalOpen(true)}>
                  {t.showNewsBtn}
                </button>
              </div>
            )}
          </div>
        </div>

        <TradingViewChart symbol={analysisData.pair} interval={analysisData.timeframe} t={globalT} isDemo={true} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '20px', marginBottom: '40px' }}>
          <button className="conduct-analysis-btn" onClick={() => setAnalysisData(null)}>
            {globalT.demoSettings?.getNewAnalysis || 'Get new analysis'}
          </button>
        </div>
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
            {['Commodities', 'Indices'].map((type) => {
              if (!assetsData[type] || assetsData[type].length === 0) return null;
              return (
              <button key={type} className={`asset-item-btn ${assetType === type ? 'active' : ''}`} onClick={() => { 
                setAssetType(type); 
                if (assetsData[type] && assetsData[type].length > 0) {
                  setForexParams(p => ({ ...p, pair: assetsData[type][0].apiVal }));
                }
                setEditMode(null); 
              }}>
                {type}
              </button>
            )})}
          </div>
        </div>
      )}

      {isSelectingPair && (
        <div className="step-container fade-in">
          <h3 className="settings-main-title">{globalT.demoSettings?.selectInstrument || 'Select an instrument'}</h3>
          <div className="pairs-grid" style={{ gridTemplateColumns: '1fr' }}>
            {assetsData[assetType]?.map((p) => (
              <button 
                key={String(p.apiVal)} 
                className={`pair-item-btn ${String(forexParams.pair) === String(p.apiVal) ? 'active' : ''}`} 
                style={{ justifyContent: 'center', gap: '10px' }} 
                onClick={() => { setForexParams({ ...forexParams, pair: p.apiVal }); setEditMode(null); }}
              >
                <AssetIcon asset={p} />
                <span className="pair-name" style={{ textAlign: 'center', fontSize: '1.1rem' }}>{p.name}</span>
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
              <button 
                key={exp} 
                className={`exp-item-btn ${forexParams.exp === exp ? 'active' : ''}`} 
                onClick={() => { setForexParams({ ...forexParams, exp }); setEditMode(null); }}
              >
                {exp}
              </button>
            ))}
          </div>

          {unavailableExp.length > 0 && (
            <>
              <div className="exp-section-title disabled-title">{'\u274C'}</div>
              <div className="exp-grid disabled-grid">
                {unavailableExp.map((exp) => (
                  <button 
                    key={exp} 
                    className={`exp-item-btn ${forexParams.exp === exp ? 'active' : ''}`} 
                    onClick={() => { setForexParams({ ...forexParams, exp }); setEditMode(null); }}
                  >
                    {exp}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {editMode === 'strategy' && (
        <div className="step-container fade-in">
          <h3 className="settings-main-title">{t.selectStrategy}</h3>
          <div className="strategies-grid">
            {strategies.filter(s => s.is_system).map((strat) => (
              <button 
                key={strat.id} 
                className={`strategy-item-btn ${Number(selectedStrategy.id) === Number(strat.id) ? 'active' : ''}`} 
                onClick={() => { if (onUpdateStrategy) onUpdateStrategy(strat.id); setEditMode(null); }} 
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
              >
                <span style={{ fontSize: '1.2rem' }}>{strat.icon || '\u26A1'}</span>
                <span>{strat.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {!editMode && (
        <div className="summary-step fade-in">
          <h3 className="settings-main-title" style={{ marginBottom: '20px', fontSize: '0.95rem' }}>{t.summaryTitle}</h3>
          <div className="summary-cards-container">
            <div className="summary-row-box" onClick={() => setEditMode('asset')}>
              <div className="summary-info"><span className="summary-label">{t.assetLabel}</span><span className="summary-value highlight">{assetType}</span></div>
              <div className="icon-edit-btn"><span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span></div>
            </div>
            <div className="summary-row-box" onClick={() => setEditMode('pair')}>
              <div className="summary-info">
                <span className="summary-label">Instrument</span>
                <span className="summary-value highlight" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <AssetIcon asset={getAssetObject(forexParams.pair)} />
                  {getAssetObject(forexParams.pair).name}
                </span>
              </div>
              <div className="icon-edit-btn"><span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span></div>
            </div>
            <div className="summary-row-box" onClick={() => setEditMode('exp')}>
              <div className="summary-info"><span className="summary-label">{t.expirationLabel}</span><span className="summary-value highlight">{forexParams.exp}</span></div>
              <div className="icon-edit-btn"><span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span></div>
            </div>
            <div className="summary-row-box" onClick={() => setEditMode('strategy')}>
              <div className="summary-info">
                <span className="summary-label">{t.strategyLabel}</span>
                <span className="summary-value" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '1.1em' }}>{selectedStrategy.icon || '\u26A1'}</span>
                  {selectedStrategy.name || 'System Strategy'}
                </span>
              </div>
              <div className="icon-edit-btn"><span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span></div>
            </div>
          </div>
          <button className="conduct-analysis-btn" onClick={handleConductAnalysis}>{globalT.demoSettings?.startStudy || 'Start Study'}</button>
        </div>
      )}
    </div>
  );
}


