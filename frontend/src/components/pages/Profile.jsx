import React, { useEffect, useRef, useState } from 'react';
import { apiFetchJson } from '../../lib/api';
import './Profile.css';
import iconEdit from '../../assets/icons/edit.svg?url';

const ICON_CHOICES = [
  '\uD83D\uDCC8', '\uD83D\uDCC9', '\uD83D\uDCCA', '\uD83D\uDCB0', '\uD83D\uDCB5', '\uD83E\uDE99', '\uD83C\uDFE6', '\uD83D\uDC8E',
  '\uD83D\uDC02', '\uD83D\uDC3B', '\uD83D\uDC0B', '\uD83E\uDD85', '\uD83D\uDC3A', '\uD83E\uDD81', '\uD83E\uDD80', '\uD83D\uDC0D',
  '\u26A1', '\uD83D\uDD25', '\uD83D\uDE80', '\uD83D\uDCA5', '\uD83C\uDF2A\uFE0F', '\uD83C\uDF0A', '\uD83C\uDF0B', '\u2604\uFE0F',
  '\uD83E\uDD16', '\uD83E\uDDE0', '\u2699\uFE0F', '\uD83D\uDCE1', '\uD83D\uDD0B', '\uD83D\uDCBB', '\uD83E\uDDEC', '\uD83D\uDD2C',
  '\uD83C\uDFAF', '\uD83D\uDEE1\uFE0F', '\u2694\uFE0F', '\uD83D\uDD0C', '\uD83E\uDDED', '\u2696\uFE0F', '\u23F1\uFE0F', '\uD83D\uDD11', '\uD83D\uDCA1', '\uD83E\uDDEF',
  '\uD83D\uDD2E', '\uD83C\uDF93', '\uD83C\uDFC6', '\uD83E\uDD47', '\uD83C\uDF1F', '\u2728', '\uD83D\uDCAB', '\uD83D\uDC41\uFE0F',
  '\uD83D\uDFE2', '\uD83D\uDD34', '\uD83D\uDD35', '\uD83D\uDFE3', '\u267E\uFE0F', '\uD83D\uDCA0', '\uD83D\uDD06', '\u303D\uFE0F'
];

export default function Profile({
  user, onToggleMode, t, strategies, onUpdateStrategy, scrollTarget, onRefreshStrategies, setToastMessage, allIndicators, onStartAnalysis
}) {
  const strategyRef = useRef(null);
  const clickTimeout = useRef(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isIconDropdownOpen, setIsIconDropdownOpen] = useState(false);
  const [editPresetId, setEditPresetId] = useState(null);
  const [formData, setFormData] = useState({ name: '', indicators: [], icon: '\u26A1' });
  const [clickCount, setClickCount] = useState(0);
  const [avatarBroken, setAvatarBroken] = useState(false);

  useEffect(() => {
    if (scrollTarget === 'strategies' && strategyRef.current) {
      setTimeout(() => {
        strategyRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  }, [scrollTarget]);

  useEffect(() => {
    setAvatarBroken(false);
  }, [user?.avatar_url]);

  if (!user) return null;

  const avatarUrl = String(user.avatar_url || '').trim();
  const profileDisplayName = String(user.first_name || user.username || 'Elizabeth Vane')
    .trim()
    .replace(/^@+/, '');
  const profileInitials = String(user.first_name || user.username || 'EV')
    .trim()
    .slice(0, 2)
    .toUpperCase();
  const currentMode = (user.mode || 'binary').toLowerCase();
  const isDemo = currentMode === 'demo';
  const forexAvailable = Number(user.forex_access ?? 1) === 1;
  const binaryAvailable = Number(user.binary_access ?? 1) === 1;
  const isAdmin = Number(user.is_admin || 0) === 1 && Boolean(user.admin_url);
  const selectedStrategy = strategies.find(s => s.id === user.strategy_id) || {};

  const systemStrategies = strategies.filter(s => s.is_system === 1);
  const myStrategies = strategies.filter(s => s.is_system === 0);

  const formatWinrate = (value) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return null;
    return `${Math.abs(parsed - Math.round(parsed)) < 0.01 ? Math.round(parsed) : parsed.toFixed(1)}%`;
  };

  const getStrategyWinrate = (strategy) => (
    formatWinrate(strategy?.display_winrate) ||
    formatWinrate(strategy?.actual_winrate) ||
    formatWinrate(strategy?.public_winrate)
  );

  const formatBalance = (value) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return '$0.00';
    return `$${parsed.toFixed(2)}`;
  };

  const openCreateModal = () => {
    setEditPresetId(null);
    setFormData({ name: '', indicators: [], icon: '\u26A1' });
    setIsIconDropdownOpen(false);
    setIsModalOpen(true);
  };

  const openEditModal = (strat) => {
    setEditPresetId(strat.id);
    const selectedIds = strat.indicator_ids ? strat.indicator_ids.split(',').map(Number) : [];
    setFormData({ name: strat.name, indicators: selectedIds, icon: strat.icon || '\u26A1' });
    setIsIconDropdownOpen(false);
    setIsModalOpen(true);
  };

  const closeAndResetModal = () => {
    setIsModalOpen(false);
    setIsIconDropdownOpen(false);
    setFormData({ name: '', indicators: [], icon: '\u26A1' });
    setEditPresetId(null);
  };

  const toggleIndicator = (id) => {
    setFormData(prev => {
      const isSelected = prev.indicators.includes(id);
      if (isSelected) {
        return { ...prev, indicators: prev.indicators.filter(i => i !== id) };
      }
      return { ...prev, indicators: [...prev.indicators, id] };
    });
  };

  const handleSaveStrategy = async () => {
    if (!formData.name.trim()) return setToastMessage(t.profile.emptyNameWarning);
    if (formData.indicators.length < 3) return setToastMessage(t.profile.minIndicatorsWarning);

    const action = editPresetId ? 'update' : 'create';
    const payload = {
      action,
      name: formData.name,
      icon: formData.icon,
      indicators: formData.indicators
    };

    if (editPresetId) payload.preset_id = editPresetId;

    try {
      await apiFetchJson('/api/user/strategy/manage', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      setToastMessage(t.profile.actionSuccess);
      closeAndResetModal();
      onRefreshStrategies();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteStrategy = async () => {
    if (!editPresetId) return;

    try {
      await apiFetchJson('/api/user/strategy/manage', {
        method: 'POST',
        body: JSON.stringify({ action: 'delete', preset_id: editPresetId })
      });
      setToastMessage(t.profile.actionSuccess);
      closeAndResetModal();
      onRefreshStrategies();
    } catch (e) {
      console.error(e);
    }
  };

  const handleAvatarClick = () => {
    const newCount = clickCount + 1;
    setClickCount(newCount);

    if (newCount >= 5) {
      onToggleMode(isDemo ? 'forex' : 'demo');
      setClickCount(0);
    }

    if (clickTimeout.current) clearTimeout(clickTimeout.current);
    clickTimeout.current = setTimeout(() => {
      setClickCount(0);
    }, 1500);
  };

  const openAdminCenter = () => {
    if (!user.admin_url) return;
    window.location.href = user.admin_url;
  };

  return (
    <div className="page-container">
      <div className="profile-wrapper">


        <div className="profile-header-container">
          <div className="profile-user-section">
            <div className="profile-avatar-container" onClick={handleAvatarClick} style={{ cursor: 'pointer' }}>
              {avatarUrl && !avatarBroken ? (
                <img
                  src={avatarUrl}
                  alt="Avatar"
                  className="profile-avatar"
                  onError={() => setAvatarBroken(true)}
                />
              ) : (
                <div className="profile-avatar-placeholder">{profileInitials}</div>
              )}
            </div>
            <h2 className="profile-name">{profileDisplayName}</h2>
          </div>

          <div className="profile-stats-card">
            {!isDemo ? (
              <>
                <div className="stats-row">
                  <div className="stat-box">
                    <span className="stat-label">{t.profile.idLabel}</span>
                    <span className="stat-value">{user.trader_id || t.profile.notSpecified || 'Not specified'}</span>
                  </div>
                  <div className="stat-box right">
                    <span className="stat-label">{t.profile.balanceLabel}</span>
                    <span className="stat-value gold">{formatBalance(user.balance)}</span>
                  </div>
                </div>

                <div className="stats-divider"></div>

                <div className="stats-row">
                  <div className="stat-box">
                    <span className="stat-label">{t.profile.modeLabel.replace(':', '')}</span>
                    <span className="stat-value">{currentMode === 'binary' ? t.profile.binaryMode : t.profile.forexMode}</span>
                  </div>
                  <div className="stat-box right">
                    <span className="stat-label">{t.profile.strategyLabel.replace(':', '')}</span>
                    <span className="stat-value">{selectedStrategy.name || '...'}</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="stats-row" style={{ justifyContent: 'center', height: '100%' }}>
                <div className="stat-box" style={{ alignItems: 'center', gap: '8px' }}>
                  <span className="stat-label" style={{ color: 'var(--accent)', fontSize: '0.85rem' }}>{t.profile.modeLabel.replace(':', '')}</span>
                  <span className="stat-value" style={{ fontSize: '1.1rem', fontWeight: '600', letterSpacing: 'normal' }}>Demo</span>
                </div>
              </div>
            )}
          </div>
        </div>


        {!isDemo && (
          <div className="profile-settings-row">
            <div className="mode-toggle-label">{t.profile.chooseMode}</div>
            <div className="mode-toggle-container">
              <div className={`mode-slider ${currentMode === 'forex' ? 'right' : ''}`}></div>
              <div
                className={`mode-toggle-btn ${currentMode === 'binary' ? 'active' : ''}`}
                onClick={() => binaryAvailable && onToggleMode('binary')}
                style={!binaryAvailable ? { opacity: 0.45, pointerEvents: 'none' } : undefined}
              >
                {t.profile.binaryMode}
              </div>
              <div
                className={`mode-toggle-btn ${currentMode === 'forex' ? 'active' : ''}`}
                onClick={() => forexAvailable && onToggleMode('forex')}
                style={!forexAvailable ? { opacity: 0.45, pointerEvents: 'none' } : undefined}
              >
                {t.profile.forexMode}
              </div>
            </div>
          </div>
        )}

        {isAdmin ? (
          <button className="admin-center-profile-btn" onClick={openAdminCenter}>
            Admin Center
          </button>
        ) : null}

        <div className="strategies-section" ref={strategyRef}>
          <button className="start-analysis-btn" onClick={onStartAnalysis}>
            {isDemo ? (t.demoSettings?.startStudy || 'Start Study') : (currentMode === 'binary' ? t.binaryAnalytics.cta : t.forexAnalytics.cta)}
          </button>


          <h3 className="settings-main-title">{t.profile.strategyTitle}</h3>

          <div className="strategy-details">
            <p><strong>{t.profile.indicatorsLabel}</strong> {selectedStrategy.indicators_list || t.profile.noData}</p>
            <p><strong>Winrate:</strong> {getStrategyWinrate(selectedStrategy) || t.profile.noData}</p>
          </div>

          <div className="strategies-grid" style={{ marginTop: '15px' }}>
            {systemStrategies.map((strat) => {
              const winrateLabel = getStrategyWinrate(strat);
              return (
                <div
                  key={strat.id}
                  className={`strategy-card ${user.strategy_id === strat.id ? 'active' : ''}`}
                  onClick={() => onUpdateStrategy(strat.id)}
                >
                  <div className="strategy-icon">{strat.icon || '\u26A1'}</div>
                  <div className="strategy-name-text">{strat.name}</div>
                  {winrateLabel ? <div className="strategy-winrate-badge">Winrate {winrateLabel}</div> : null}
                </div>
              );
            })}
          </div>

          <div className="profile-divider" style={{ margin: '25px 0 20px 0' }}></div>

          <h3 className="settings-main-title">{t.profile.myStrategyTitle}</h3>
          <button className="add-strategy-btn" onClick={openCreateModal}>
            {t.profile.addStrategyBtn}
          </button>

          {myStrategies.length > 0 && (
            <div className="custom-strategies-list">
              {myStrategies.map((strat) => {
                const winrateLabel = getStrategyWinrate(strat);
                return (
                  <div key={strat.id} className={`custom-strategy-item ${user.strategy_id === strat.id ? 'active' : ''}`}>
                    <div className="custom-strat-icon-wrapper">{strat.icon || '\uD83D\uDCDD'}</div>
                    <div className="custom-strat-info" onClick={() => onUpdateStrategy(strat.id)}>
                      <span className="strat-name">{strat.name}</span>
                      <span className="strat-indicators">{strat.indicators_list}</span>
                      {winrateLabel ? <span className="strat-winrate">Winrate {winrateLabel}</span> : null}
                    </div>
                    <button className="strat-edit-icon" onClick={() => openEditModal(strat)}>
                      <span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span>
                    </button>
                  </div>
                );
              })}
            </div>
          )}

        </div>
      </div>

      {isModalOpen && (
        <div className="strategy-modal-overlay">
          <div className="strategy-modal-content fade-in">
            <h3 className="modal-title">
              {editPresetId ? t.profile.editStrategyModalTitle : t.profile.createStrategyModalTitle}
            </h3>

            <div className="modal-form-group" style={{ position: 'relative' }}>
              <label>Icon</label>
              <div
                className="icon-dropdown-trigger"
                onClick={() => setIsIconDropdownOpen(!isIconDropdownOpen)}
              >
                <span className="selected-icon-display">{formData.icon}</span>
                <span className={`dropdown-arrow ${isIconDropdownOpen ? 'open' : ''}`}>{'\u25BE'}</span>
              </div>

              {isIconDropdownOpen && (
                <div className="icon-dropdown-menu fade-in">
                  {ICON_CHOICES.map(icon => (
                    <div
                      key={icon}
                      className={`icon-choice-item ${formData.icon === icon ? 'selected' : ''}`}
                      onClick={() => {
                        setFormData({...formData, icon});
                        setIsIconDropdownOpen(false);
                      }}
                    >
                      {icon}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="modal-form-group">
              <label>{t.profile.strategyNameLabel}</label>
              <input
                type="text"
                className="modal-input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder={t.profile.strategyNamePlaceholder}
              />
            </div>

            <div className="modal-form-group">
              <label>{t.profile.selectIndicatorsLabel}</label>
              <div className="indicators-select-grid">
                {allIndicators.map((ind) => (
                  <div
                    key={ind.id}
                    className={`indicator-toggle-btn ${formData.indicators.includes(ind.id) ? 'selected' : ''}`}
                    onClick={() => toggleIndicator(ind.id)}
                  >
                    {ind.name}
                  </div>
                ))}
              </div>
            </div>

            <div className="modal-actions">
              <button className="modal-save-btn" onClick={handleSaveStrategy}>{t.profile.saveBtn}</button>
              {editPresetId && (
                <button className="modal-delete-btn" onClick={handleDeleteStrategy}>{t.profile.deleteBtn}</button>
              )}
              <button className="modal-cancel-btn" onClick={closeAndResetModal}>{t.profile.cancelBtn}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}




