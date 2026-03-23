import React, { useEffect, useState } from 'react';
import Loader from '../Loader/Loader';
import { texts } from '../../locales/texts';
import './LogAnalysis.css';

export default function LogAnalysis({ user }) {
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState({ success: 0, fail: 0, total: 0 });
  const [loading, setLoading] = useState(true);
  const t = texts.en.logAnalysis;

  useEffect(() => {
    if (user?.user_id) {
      fetch(`/api/analysis/history?user_id=${user.user_id}`)
        .then(res => res.json())
        .then(data => {
          setHistory(data.history || []);
          setStats(data.stats || { success: 0, fail: 0, total: 0 });
          setLoading(false);
        })
        .catch(() => setLoading(false));
    }
  }, [user]);

  if (loading) return <Loader t={texts.en} />;

  const pointerPosition = stats.total > 0 ? (stats.success / stats.total) * 100 : 50;

  return (
    <div className="profile-wrapper">
      <h2 className="settings-main-title" style={{ marginBottom: '20px' }}>{t.title}</h2>
      
      <div className="log-gauge-container">
        <div className="log-gauge-bg">
          <div className="log-gauge-pointer" style={{ left: `${pointerPosition}%` }}></div>
        </div>
        
        <div className="log-gauge-labels">
          <span className="log-gl-sell">{t.fail} ({stats.fail})</span>
          <span className="log-gl-total">{t.total}: {stats.total}</span>
          <span className="log-gl-buy">{t.success} ({stats.success})</span>
        </div>
      </div>

      
      {history.length === 0 ? (
        <div className="empty-market-card"><p>{t.empty}</p></div>
      ) : (
        <div className="log-list">
          {history.map((item) => (
            <div 
              key={item.id} 
              className="log-card" 
              style={{ borderLeft: item.status === 'success' ? '4px solid #2ecc71' : '4px solid #e74c3c' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                <strong style={{ fontSize: '1.1rem', color: '#fff' }}>{item.pair}</strong>
                <span style={{ fontSize: '0.85rem', color: '#888' }}>
                  {new Date(item.created_at).toLocaleDateString()} {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', fontSize: '0.85rem', color: '#aaa' }}>
                <span>{t.interval} <span style={{ color: '#D4AF37' }}>{item.timeframe}</span></span>
                <span>{item.strategy_name || t.customStrategy}</span>
              </div>
              
              <div style={{ 
                marginTop: '4px', 
                fontSize: '0.8rem', 
                fontWeight: 'bold', 
                color: item.status === 'success' ? '#2ecc71' : '#e74c3c', 
                textTransform: 'uppercase', 
                letterSpacing: '1px' 
              }}>
                {item.status === 'success' ? t.success : t.fail}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}