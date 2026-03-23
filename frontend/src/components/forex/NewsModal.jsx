import React from 'react';
import './ForexAnalysisSettings.css'; 

export default function NewsModal({ isOpen, onClose, events, t }) {
  if (!isOpen) return null;

  const formatEventTime = (timeStr) => {
    if (!timeStr) return '';
    return timeStr.split(' ')[1]?.substring(0, 5) || '';
  };

  const getImpactIcon = (impact) => {
    if (impact === 'high') return '🔴';
    if (impact === 'medium') return '🟠';
    return '🟢';
  };

  const getImpactClass = (impact) => {
    if (impact === 'high') return 'impact-high';
    if (impact === 'medium') return 'impact-medium';
    return 'impact-low';
  };

  return (
    <div className="news-modal-overlay" onClick={onClose}>
      <div className="news-modal-content fade-in" onClick={(e) => e.stopPropagation()}>
        <h3 className="news-modal-title">{t.newsModalTitle}</h3>
        
        <div className="nf-events-list modal-events-list">
          {events.length > 0 ? (
            events.map((ev, i) => (
              <div key={i} className={`nf-event-item ${getImpactClass(ev.impact)}`}>
                <span className="ev-icon">{getImpactIcon(ev.impact)}</span>
                <span className="ev-time">{formatEventTime(ev.time)}</span>
                <span className="ev-currency">{ev.currency || ev.unit || ev.country}</span>
                <span className="ev-desc">- {ev.event}</span>
              </div>
            ))
          ) : (
            <div className="nf-safe-box" style={{ padding: '20px', textAlign: 'center' }}>
                {t.noNewsExpected}
            </div>
          )}
        </div>

        <button className="go-back-outline-btn" style={{ marginTop: '20px' }} onClick={onClose}>
          {t.closeBtn || 'Закрыть'}
        </button>
      </div>
    </div>
  );
}