import React, { useEffect, useState } from 'react';
import Lottie from 'lottie-react';
import animationData from '../../assets/animation.json';
import { apiFetchJson } from '../../lib/api';
import './Forex.css';

export default function ForexHome({ t: globalT, onStartAnalysis, user, onOpenActiveAnalysis, strategies = [] }) {
  const t = globalT.forexAnalytics;
  const tSettings = globalT.analysisSettings;
  const [activeAnalyses, setActiveAnalyses] = useState([]);
  const [showList, setShowList] = useState(false);

  useEffect(() => {
    if (user) {
      apiFetchJson('/api/analysis/active')
        .then(data => {
          if (data.analyses && data.analyses.length > 0) {
            setActiveAnalyses(data.analyses);
          }
        })
        .catch(console.error);
    }
  }, [user]);

  const handleOpenActive = () => {
    if (activeAnalyses.length === 1) {
      onOpenActiveAnalysis(activeAnalyses[0]);
    } else if (activeAnalyses.length > 1) {
      setShowList(true);
    }
  };

  const formatTime = (dateString) => {
    const d = new Date(dateString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (showList) {
    return (
      <div className="profile-wrapper">
        <h2 className="settings-main-title" style={{ marginBottom: '20px' }}>{t.activeAnalysesTitle}</h2>
        <div className="active-analyses-list">
          {activeAnalyses.map(item => {
            const stratName = item.strategy_name || strategies.find(s => Number(s.id) === Number(item.strategy_id))?.name || 'Custom Strategy';
            
            return (
              <div key={item.id} className="active-analysis-card" onClick={() => onOpenActiveAnalysis(item)}>
                <div className="aac-left">
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span className="live-dot"></span>
                    <span className="aac-pair">{item.pair}</span>
                  </div>
                  <div className="aac-details" style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '4px' }}>
                    <span>{t.expirationPrefix} {item.timeframe}</span>
                    <span style={{ color: 'var(--accent)' }}>{t.strategyPrefix} {stratName}</span>
                  </div>
                </div>
                <div className="aac-right">
                  {formatTime(item.created_at)}
                </div>
              </div>
            );
          })}
        </div>
        <button className="go-back-outline-btn" style={{ marginTop: '20px' }} onClick={() => setShowList(false)}>
          {t.backBtn}
        </button>
      </div>
    );
  }

  return (
    <div className="profile-wrapper">
      
      <div className="analytics-hero">
        <h1 className="settings-main-title">{t.title}</h1>
        <p className="subtitle">{t.subtitle}</p>
        <p className="description">{t.description}</p>
      </div>

      <div className="lottie-animation-wrapper">
        <Lottie animationData={animationData} loop={true} className="hero-lottie" />
      </div>

      <div className="actions-wrapper" style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        {activeAnalyses.length > 0 && (
          <button className="forex-cta-btn" onClick={handleOpenActive}>
            {tSettings.currentAnalysisBtn} ({activeAnalyses.length})
          </button>
        )}
        <button className="forex-cta-btn" onClick={onStartAnalysis}>
          {t.cta}
        </button>
      </div>
    </div>
  );
}

