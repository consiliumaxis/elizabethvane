import React, { useState, useEffect } from 'react';
import Loader from '../Loader/Loader';
import { apiFetchJson } from '../../lib/api';
import './BinarySignalSettings.css';
import iconEdit from '../../assets/icons/edit.svg?url';

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
  const [loading, setLoading] = useState(true);
  
  const [editMode, setEditMode] = useState(null); 

  const expOptions = ['1m', '3m', '5m', '10m', '15m', '30m'];

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
    apiFetchJson('/api/pairs/forex')
      .then(data => {
        if (data && data.pairs && data.pairs.length > 0) {
          setPairs(data.pairs);

          setBinaryParams(prev => ({
            pair: prev.pair || data.pairs[0].pair,
            exp: prev.exp || expOptions[0]
          }));
        } else {
          setPairs([]);
        }
        setLoading(false);
      })
      .catch(() => {
        setPairs([]);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <Loader t={globalT} />;
  }
  
  if (pairs.length === 0) {
    return (
      <div className="profile-wrapper">
        <div className="empty-market-card">
          <p>{t.marketClosed}</p>
          <button className="binary-cta-btn" style={{ marginTop: '20px' }} onClick={onGoHome}>
            {t.goHome}
          </button>
        </div>
      </div>
    );
  }

  const handleSelectPair = (pairStr) => {
    setBinaryParams({ ...binaryParams, pair: pairStr });
    setEditMode(null);
  };

  const handleSelectExp = (expStr) => {
    setBinaryParams({ ...binaryParams, exp: expStr });
    setEditMode(null);
  };

  const isSelectingPair = editMode === 'pair';
  const isSelectingExp = editMode === 'exp';
  const isShowingSummary = !editMode && binaryParams.pair && binaryParams.exp;

  return (
    <div className="profile-wrapper">
      
      {isSelectingPair && (
        <div className="step-container fade-in">
          <h3 className="settings-main-title">{t.selectPair}</h3>
          <div className="pairs-grid">
            {pairs.map((p, idx) => (
              <button key={idx} className="pair-item-btn" onClick={() => handleSelectPair(p.pair)}>
                <span className="pair-name">{p.pair}</span>
                <span className="pair-payout">{p.payout}%</span>
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
              <button key={idx} className="exp-item-btn" onClick={() => handleSelectExp(exp)}>
                {exp}
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

