import React, { useEffect, useMemo, useRef, useState } from 'react';
import Loader from '../Loader/Loader';
import { apiFetchJson } from '../../lib/api';
import { texts } from '../../locales/texts';
import './LogAnalysis.css';

const toNumberOrNull = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const formatPercent = (value) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return '0%';
  const rounded = Math.max(0, Math.min(100, parsed));
  return Math.abs(rounded - Math.round(rounded)) < 0.01 ? `${Math.round(rounded)}%` : `${rounded.toFixed(1)}%`;
};

const resolveStrategyWinrate = (strategy) =>
  toNumberOrNull(strategy?.display_winrate) ??
  toNumberOrNull(strategy?.actual_winrate) ??
  toNumberOrNull(strategy?.public_winrate);

export default function LogAnalysis({ user, t, strategies = [] }) {
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState({ success: 0, fail: 0, skipped: 0, total: 0, closed_total: 0, winrate: 0 });
  const [loading, setLoading] = useState(true);
  const [selectedStrategyId, setSelectedStrategyId] = useState('all');
  const [isStrategyMenuOpen, setIsStrategyMenuOpen] = useState(false);
  const dropdownRef = useRef(null);

  const i18n = t || texts.en;
  const logT = i18n.logAnalysis || texts.en.logAnalysis;

  const strategiesMap = useMemo(() => {
    const map = new Map();
    (strategies || []).forEach((strategy) => {
      map.set(Number(strategy.id), strategy);
    });
    return map;
  }, [strategies]);

  const selectedStrategy = useMemo(() => {
    if (selectedStrategyId === 'all') return null;
    return strategiesMap.get(Number(selectedStrategyId)) || null;
  }, [selectedStrategyId, strategiesMap]);

  useEffect(() => {
    const onClickOutside = (event) => {
      if (!dropdownRef.current) return;
      if (!dropdownRef.current.contains(event.target)) {
        setIsStrategyMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onClickOutside);
    document.addEventListener('touchstart', onClickOutside);
    return () => {
      document.removeEventListener('mousedown', onClickOutside);
      document.removeEventListener('touchstart', onClickOutside);
    };
  }, []);

  useEffect(() => {
    if (!user) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    const loadHistory = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (selectedStrategyId !== 'all') {
          params.set('strategy_id', selectedStrategyId);
        }
        const suffix = params.toString() ? `?${params.toString()}` : '';
        const data = await apiFetchJson(`/api/analysis/history${suffix}`);
        if (cancelled) return;
        setHistory(data.history || []);
        setStats(data.stats || { success: 0, fail: 0, skipped: 0, total: 0, closed_total: 0, winrate: 0 });
      } catch {
        if (!cancelled) {
          setHistory([]);
          setStats({ success: 0, fail: 0, skipped: 0, total: 0, closed_total: 0, winrate: 0 });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadHistory();
    return () => {
      cancelled = true;
    };
  }, [user, selectedStrategyId]);

  if (loading) return <Loader t={i18n} />;

  const closedTotal = Number(stats.closed_total || (Number(stats.success || 0) + Number(stats.fail || 0)));
  const winrateValue = Math.max(0, Math.min(100, Number(stats.winrate || 0)));
  const gaugeArcLength = 157;
  const gaugeFill = (gaugeArcLength * winrateValue) / 100;

  const selectedStrategyWinrate = resolveStrategyWinrate(selectedStrategy);
  const allStrategiesLabel = logT.allStrategies || 'All strategies';
  const selectedStrategyTitle = selectedStrategy ? `${selectedStrategy.icon || '\u26A1'} ${selectedStrategy.name}` : allStrategiesLabel;

  return (
    <div className="profile-wrapper">
      <h2 className="settings-main-title" style={{ marginBottom: '14px' }}>{logT.title}</h2>

      <div className="log-filter-card" ref={dropdownRef}>
        <label className="log-filter-label">{logT.selectStrategy || 'Strategy filter'}</label>
        <button
          type="button"
          className={`log-filter-select ${isStrategyMenuOpen ? 'open' : ''}`}
          onClick={() => setIsStrategyMenuOpen((prev) => !prev)}
        >
          <span className="log-filter-selected-text">{selectedStrategyTitle}</span>
          <span className={`log-filter-caret ${isStrategyMenuOpen ? 'open' : ''}`}>▾</span>
        </button>

        {isStrategyMenuOpen ? (
          <div className="log-filter-menu">
            <button
              type="button"
              className={`log-filter-option ${selectedStrategyId === 'all' ? 'active' : ''}`}
              onClick={() => {
                setSelectedStrategyId('all');
                setIsStrategyMenuOpen(false);
              }}
            >
              <span className="log-filter-option-title">{allStrategiesLabel}</span>
              <span className="log-filter-radio" />
            </button>

            {(strategies || []).map((strategy) => {
              const optionValue = String(strategy.id);
              const isActive = selectedStrategyId === optionValue;
              return (
                <button
                  key={strategy.id}
                  type="button"
                  className={`log-filter-option ${isActive ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedStrategyId(optionValue);
                    setIsStrategyMenuOpen(false);
                  }}
                >
                  <span className="log-filter-option-title">
                    {(strategy.icon || '\u26A1') + ' ' + strategy.name}
                  </span>
                  <span className="log-filter-radio" />
                </button>
              );
            })}
          </div>
        ) : null}
      </div>

      <div className="log-winrate-card">
        <div className="log-winrate-head">
          <span>{logT.winrate || 'Winrate'}</span>
          <span>{formatPercent(winrateValue)}</span>
        </div>

        <div className="log-mini-gauge">
          <svg viewBox="0 0 120 70" className="log-mini-gauge-svg" aria-hidden="true">
            <path d="M10 60 A50 50 0 0 1 110 60" className="log-gauge-track" />
            <path
              d="M10 60 A50 50 0 0 1 110 60"
              className="log-gauge-fill"
              style={{ strokeDasharray: `${gaugeFill} ${gaugeArcLength}` }}
            />
          </svg>
          <div className="log-mini-gauge-value">{formatPercent(winrateValue)}</div>
        </div>

        <div className="log-winrate-meta">
          <span className="log-gl-fail">{logT.fail} ({stats.fail || 0})</span>
          <span className="log-gl-total">{logT.total}: {stats.total || 0}</span>
          <span className="log-gl-success">{logT.success} ({stats.success || 0})</span>
        </div>

        <div className="log-winrate-subline">
          {logT.closedLabel || 'Closed'}: {closedTotal}
          {selectedStrategy ? ` | ${selectedStrategy.name}` : ''}
          {selectedStrategyWinrate !== null ? ` | ${logT.strategyWinrate || 'Strategy winrate'}: ${formatPercent(selectedStrategyWinrate)}` : ''}
        </div>
      </div>

      {history.length === 0 ? (
        <div className="empty-market-card"><p>{logT.empty}</p></div>
      ) : (
        <div className="log-list">
          {history.map((item) => {
            const mappedStrategy = strategiesMap.get(Number(item.strategy_id));
            const strategyWinrate = resolveStrategyWinrate(mappedStrategy) ?? toNumberOrNull(item.public_winrate);
            return (
              <div
                key={item.id}
                className="log-card"
                style={{ borderLeft: item.status === 'success' ? '4px solid var(--success)' : '4px solid var(--danger)' }}
              >
                <div className="log-card-top">
                  <strong className="log-card-pair">{item.pair}</strong>
                  <span className="log-card-date">
                    {new Date(item.created_at).toLocaleDateString()} {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                <div className="log-card-meta">
                  <span>{logT.interval} <span style={{ color: 'var(--accent)' }}>{item.timeframe}</span></span>
                  <span>{item.strategy_name || logT.customStrategy}</span>
                </div>

                <div className="log-card-bottom">
                  <span
                    className="log-card-status"
                    style={{ color: item.status === 'success' ? 'var(--success)' : 'var(--danger)' }}
                  >
                    {item.status === 'success' ? logT.success : logT.fail}
                  </span>
                  {strategyWinrate !== null ? (
                    <span className="log-card-winrate">Winrate {formatPercent(strategyWinrate)}</span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
