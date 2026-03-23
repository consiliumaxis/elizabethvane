import React, { useEffect, useRef, useState } from 'react';
import './Profile.css';
import iconEdit from '../../assets/icons/edit.svg?url';
import avatarImg from '../../assets/elizabeth-avatar.jpg'; 

const ICON_CHOICES = [
  '📈', '📉', '📊', '💰', '💵', '🪙', '🏦', '💎',
  '🐂', '🐻', '🐋', '🦅', '🐺', '🦁', '🦈', '🐍',
  '⚡', '🔥', '🚀', '💥', '🌪️', '🌊', '🌋', '☄️',
  '🤖', '🧠', '⚙️', '📡', '🔋', '💻', '🧬', '🔬',
  '🎯', '🛡️', '⚔️', '🔍', '🧭', '⚖️', '⏱️', '🔑', '💡', '🧿',
  '🔮', '👑', '🏆', '🥇', '🌟', '✨', '💫', '👁️',
  '🟢', '🔴', '🔵', '🟣', '♾️', '💠', '🔆', '〽️'
];

export default function Profile({
  user, onToggleMode, t, strategies, onUpdateStrategy, scrollTarget, onRefreshStrategies, setToastMessage, allIndicators, onStartAnalysis
}) {
  const strategyRef = useRef(null);
  const clickTimeout = useRef(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isIconDropdownOpen, setIsIconDropdownOpen] = useState(false); 
  const [editPresetId, setEditPresetId] = useState(null);
  const [formData, setFormData] = useState({ name: '', indicators: [], icon: '⚡' });
  const [clickCount, setClickCount] = useState(0);

  useEffect(() => {
    if (scrollTarget === 'strategies' && strategyRef.current) {
      setTimeout(() => {
        strategyRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  }, [scrollTarget]);

  if (!user) return null;

  const currentMode = (user.mode || 'binary').toLowerCase();
  const isDemo = currentMode === 'demo';
  const selectedStrategy = strategies.find(s => s.id === user.strategy_id) || {};

  const systemStrategies = strategies.filter(s => s.is_system === 1);
  const myStrategies = strategies.filter(s => s.is_system === 0);

  const openCreateModal = () => {
    setEditPresetId(null);
    setFormData({ name: '', indicators: [], icon: '⚡' });
    setIsIconDropdownOpen(false);
    setIsModalOpen(true);
  };

  const openEditModal = (strat) => {
    setEditPresetId(strat.id);
    const selectedIds = strat.indicator_ids ? strat.indicator_ids.split(',').map(Number) : [];
    setFormData({ name: strat.name, indicators: selectedIds, icon: strat.icon || '⚡' });
    setIsIconDropdownOpen(false);
    setIsModalOpen(true);
  };

  const closeAndResetModal = () => {
    setIsModalOpen(false);
    setIsIconDropdownOpen(false);
    setFormData({ name: '', indicators: [], icon: '⚡' });
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
      user_id: user.user_id,
      name: formData.name,
      icon: formData.icon, 
      indicators: formData.indicators
    };

    if (editPresetId) payload.preset_id = editPresetId;

    try {
      const res = await fetch('/api/user/strategy/manage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        setToastMessage(t.profile.actionSuccess);
        closeAndResetModal();
        onRefreshStrategies();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteStrategy = async () => {
    if (!editPresetId) return;

    try {
      const res = await fetch('/api/user/strategy/manage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete', user_id: user.user_id, preset_id: editPresetId })
      });

      if (res.ok) {
        setToastMessage(t.profile.actionSuccess);
        closeAndResetModal();
        onRefreshStrategies();
      }
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

  return (
    <div className="page-container">
      <div className="profile-wrapper">
        
        
        <div className="profile-header-container">
          <div className="profile-user-section">
            <div className="profile-avatar-container" onClick={handleAvatarClick} style={{ cursor: 'pointer' }}>
              <img src={avatarImg} alt="Avatar" className="profile-avatar" />
            </div>
            <h2 className="profile-name">Elizabeth</h2>
          </div>

          <div className="profile-stats-card">
            {!isDemo ? (
              <>
                <div className="stats-row">
                  <div className="stat-box">
                    <span className="stat-label">{t.profile.idLabel}</span>
                    <span className="stat-value">*****</span>
                  </div>
                  <div className="stat-box right">
                    <span className="stat-label">{t.profile.balanceLabel}</span>
                    <span className="stat-value gold">*****</span>
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
                  <span className="stat-label" style={{ color: '#D4AF37', fontSize: '0.85rem' }}>{t.profile.modeLabel.replace(':', '')}</span>
                  <span className="stat-value" style={{ fontSize: '1.2rem', fontWeight: '700', letterSpacing: '2px' }}>DEMO</span>
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
                onClick={() => onToggleMode('binary')}
              >
                {t.profile.binaryMode}
              </div>
              <div 
                className={`mode-toggle-btn ${currentMode === 'forex' ? 'active' : ''}`} 
                onClick={() => onToggleMode('forex')}
              >
                {t.profile.forexMode}
              </div>
            </div>
          </div>
        )}

        <div className="strategies-section" ref={strategyRef}>
          <button className="start-analysis-btn" onClick={onStartAnalysis}>
            {isDemo ? (t.demoSettings?.startStudy || 'Start Study') : (currentMode === 'binary' ? t.binaryAnalytics.cta : t.forexAnalytics.cta)}
          </button>

          
          <h3 className="settings-main-title">{t.profile.strategyTitle}</h3>

          <div className="strategy-details">
            <p><strong>{t.profile.indicatorsLabel}</strong> {selectedStrategy.indicators_list || t.profile.noData}</p>
          </div>

          <div className="strategies-grid" style={{ marginTop: '15px' }}>
            {systemStrategies.map((strat) => (
              <div
                key={strat.id}
                className={`strategy-card ${user.strategy_id === strat.id ? 'active' : ''}`}
                onClick={() => onUpdateStrategy(strat.id)}
              >
                <div className="strategy-icon">{strat.icon || '⚡'}</div>
                <div className="strategy-name-text">{strat.name}</div>
              </div>
            ))}
          </div>

          <div className="profile-divider" style={{ margin: '25px 0 20px 0' }}></div>

          <h3 className="settings-main-title">{t.profile.myStrategyTitle}</h3>
          <button className="add-strategy-btn" onClick={openCreateModal}>
            {t.profile.addStrategyBtn}
          </button>

          {myStrategies.length > 0 && (
            <div className="custom-strategies-list">
              {myStrategies.map((strat) => (
                <div key={strat.id} className={`custom-strategy-item ${user.strategy_id === strat.id ? 'active' : ''}`}>
                  <div className="custom-strat-icon-wrapper">{strat.icon || '📝'}</div>
                  <div className="custom-strat-info" onClick={() => onUpdateStrategy(strat.id)}>
                    <span className="strat-name">{strat.name}</span>
                    <span className="strat-indicators">{strat.indicators_list}</span>
                  </div>
                  <button className="strat-edit-icon" onClick={() => openEditModal(strat)}>
                    <span className="edit-icon-mask" style={{ maskImage: `url("${iconEdit}")`, WebkitMaskImage: `url("${iconEdit}")` }}></span>
                  </button>
                </div>
              ))}
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
                <span className={`dropdown-arrow ${isIconDropdownOpen ? 'open' : ''}`}>▼</span>
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