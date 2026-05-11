import React, { useState, useEffect } from 'react';
import Loader from '../Loader/Loader';
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

  const [editMode, setEditMode] = useState(null);

  const appliedStrategyId = user?.strategy_id;
  const selectedStrategy = strategies?.find(s => Number(s.id) === Number(appliedStrategyId)) || strategies?.find(s => s.is_system) || {};

  useEffect(() => {
    if (setBackHandler) {
      setBackHandler(() => {
        if (editMode) {

          setEditMode(null);
        } else {

          onGoHome();
        }
      });
    }
  }, [editMode, onGoHome, setBackHandler]);

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

  if (loading) {
    return <Loader t={globalT} />;
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

          <button className="get-signal-btn">{t.getSignalBtn}</button>
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

