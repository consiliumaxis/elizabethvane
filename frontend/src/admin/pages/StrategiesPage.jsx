import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';

const toInt = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const isSystemStrategy = (item) => Number(item?.is_system) === 1;

const parseIndicatorNames = (item) =>
  String(item?.indicators_list || '')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);

const parseIndicatorIds = (item) =>
  String(item?.indicator_ids || '')
    .split(',')
    .map((x) => Number(x.trim()))
    .filter((x) => Number.isFinite(x) && x > 0);

const formatPercent = (value) => {
  const num = Number(value || 0);
  if (!Number.isFinite(num)) return '0%';
  if (Math.abs(num - Math.round(num)) < 0.01) {
    return `${Math.round(num)}%`;
  }
  return `${num.toFixed(1)}%`;
};

const TIMEFRAME_OPTIONS = ['1m', '3m', '5m', '10m', '15m', '30m', '1h', '4h', '1d'];

const parseTimeframes = (value) => {
  const raw = Array.isArray(value) ? value : String(value || '').split(',');
  const seen = new Set();
  const result = [];
  raw.forEach((item) => {
    const timeframe = String(item || '').trim();
    if (!TIMEFRAME_OPTIONS.includes(timeframe) || seen.has(timeframe)) return;
    seen.add(timeframe);
    result.push(timeframe);
  });
  return result;
};

const joinTimeframes = (value) => parseTimeframes(value).join(',');

const parsePublicWinrate = (value) => {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

export default function StrategiesPage() {
  const [items, setItems] = useState([]);
  const [indicators, setIndicators] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiAdminFetchJson('/api/admin/strategies');
      const rows = Array.isArray(res.strategies) ? res.strategies : [];
      const normalized = rows.map((item) => ({
        ...item,
        users_count: toInt(item.users_count),
        usage_count: toInt(item.usage_count ?? item.users_count),
        signals_count: toInt(item.signals_count),
        wins_count: toInt(item.wins_count),
        closed_signals: toInt(item.closed_signals),
        winrate: Number(item.winrate || 0),
        public_winrate: parsePublicWinrate(item.public_winrate),
      }));
      setItems(normalized);
      setIndicators(Array.isArray(res.indicators) ? res.indicators : []);
      setSummary(res.summary || null);
    } catch (e) {
      setError(e.message || 'Не удалось загрузить стратегии');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const selected = useMemo(
    () => items.find((item) => String(item.id) === String(selectedId)) || null,
    [items, selectedId]
  );

  const indicatorNameById = useMemo(() => {
    const map = new Map();
    indicators.forEach((indicator) => {
      map.set(Number(indicator.id), indicator.name || `ID ${indicator.id}`);
    });
    return map;
  }, [indicators]);

  useEffect(() => {
    if (!selected) {
      setForm(null);
      return;
    }

    const parsedIds = parseIndicatorIds(selected);
    const uniqueIndicatorIds = [];
    const seen = new Set();
    parsedIds.forEach((id) => {
      if (!seen.has(id)) {
        seen.add(id);
        uniqueIndicatorIds.push(id);
      }
    });

    setForm({
      id: selected.id,
      name: selected.name || '',
      icon: selected.icon || '⚡',
      timeframes: parseTimeframes(selected.allowed_timeframes),
      is_system: isSystemStrategy(selected),
      initial_is_system: isSystemStrategy(selected),
      users_count: toInt(selected.users_count),
      signals_count: toInt(selected.signals_count),
      winrate: Number(selected.winrate || 0),
      public_winrate: selected.public_winrate === null ? '' : String(selected.public_winrate),
      indicators: uniqueIndicatorIds,
    });
  }, [selected]);

  const computedSummary = useMemo(() => {
    const systemCount = items.filter((item) => isSystemStrategy(item)).length;
    const userCount = items.length - systemCount;
    return {
      total: toInt(summary?.total_count || items.length),
      system: toInt(summary?.system_count ?? systemCount),
      user: toInt(summary?.user_count ?? userCount),
    };
  }, [items, summary]);

  const systemStrategies = useMemo(
    () => items.filter((item) => isSystemStrategy(item)),
    [items]
  );

  const userStrategies = useMemo(
    () => items.filter((item) => !isSystemStrategy(item)),
    [items]
  );

  const openCard = (id) => {
    setSelectedId(id);
    setError('');
    setStatus('');
  };

  const closeCard = () => {
    setSelectedId(null);
    setForm(null);
    setError('');
    setStatus('');
  };

  const toggleIndicator = (id) => {
    setForm((prev) => {
      if (!prev) return prev;
      const exists = prev.indicators.includes(id);
      return {
        ...prev,
        indicators: exists ? prev.indicators.filter((item) => item !== id) : [...prev.indicators, id],
      };
    });
  };

  const toggleTimeframe = (timeframe) => {
    setForm((prev) => {
      if (!prev) return prev;
      const exists = prev.timeframes.includes(timeframe);
      const next = exists ? prev.timeframes.filter((item) => item !== timeframe) : [...prev.timeframes, timeframe];
      return {
        ...prev,
        timeframes: parseTimeframes(next),
      };
    });
  };

  const save = async () => {
    if (!form) return;
    if (!form.name.trim()) {
      setError('Название стратегии обязательно');
      return;
    }
    if (!form.timeframes.length) {
      setError('Выберите хотя бы один таймфрейм');
      return;
    }

    const publicWinrate = form.public_winrate === '' ? null : Number(form.public_winrate);
    if (publicWinrate !== null && (!Number.isFinite(publicWinrate) || publicWinrate < 0 || publicWinrate > 100)) {
      setError('Отображаемый winrate должен быть числом от 0 до 100');
      return;
    }

    setError('');
    setStatus('');
    try {
      await apiAdminFetchJson('/api/admin/strategies/update', {
        method: 'POST',
        body: JSON.stringify({
          id: form.id,
          name: form.name,
          icon: form.icon,
          allowed_timeframes: joinTimeframes(form.timeframes),
          public_winrate: publicWinrate,
          is_system: form.initial_is_system ? form.is_system : false,
          indicators: form.indicators,
        }),
      });
      setStatus(`Стратегия ${form.id} сохранена`);
      await load();
    } catch (e) {
      setError(e.message || 'Не удалось сохранить стратегию');
    }
  };

  const remove = async () => {
    if (!form || Number(form.id) === 1) return;
    setError('');
    setStatus('');
    try {
      await apiAdminFetchJson('/api/admin/strategies/delete', {
        method: 'POST',
        body: JSON.stringify({ id: form.id }),
      });
      setStatus(`Стратегия ${form.id} удалена`);
      await load();
      closeCard();
    } catch (e) {
      setError(e.message || 'Не удалось удалить стратегию');
    }
  };

  const renderList = (title, rows, emptyText, customBlock = false) => (
    <div className={`admin-card admin-strategy-block ${customBlock ? 'custom-block' : ''}`}>
      <div className="admin-row-between">
        <h3 className="admin-section-title">{title}</h3>
        <div className="admin-muted">{rows.length}</div>
      </div>

      {rows.length ? (
        <div className="admin-entity-list">
          {rows.map((item) => {
            const indicatorNames = parseIndicatorNames(item);
            const timeframes = parseTimeframes(item.allowed_timeframes);
            const usersCount = toInt(item.users_count);
            const signalsCount = toInt(item.signals_count);
            const shownWinrate = item.public_winrate ?? item.winrate;
            return (
              <button
                key={item.id}
                className={`admin-entity-card admin-strategy-card ${customBlock ? 'is-custom' : ''}`}
                type="button"
                onClick={() => openCard(item.id)}
              >
                <div className="admin-entity-head">
                  <div className="admin-entity-title">
                    <span className="admin-state-icon">{item.icon || '📊'}</span>
                    <span>{item.name || `Стратегия ${item.id}`}</span>
                  </div>
                  <span className="admin-entity-gear">⚙️</span>
                </div>

                <div className="admin-entity-meta">ID: {item.id}</div>

                <div className="admin-strategy-meta-line">
                  <span>👥 Пользователи: {usersCount}</span>
                  <span>📶 Сигналы: {signalsCount}</span>
                  <span>🎯 Отображаемый Winrate: {formatPercent(shownWinrate)}</span>
                </div>

                <div className="admin-chip-list">
                  {isSystemStrategy(item) ? (
                    <span className="admin-chip admin-chip-state">Системная</span>
                  ) : (
                    <span className="admin-chip admin-chip-state user">Пользовательская</span>
                  )}
                  {timeframes.map((timeframe) => (
                    <span key={`${item.id}-tf-${timeframe}`} className="admin-chip admin-chip-timeframe">
                      {timeframe}
                    </span>
                  ))}
                  {indicatorNames.map((indicator) => (
                    <span key={`${item.id}-${indicator}`} className="admin-chip">
                      {indicator}
                    </span>
                  ))}
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="admin-muted">{emptyText}</div>
      )}
    </div>
  );

  if (selected && form) {
    const selectedIndicatorNames = form.indicators.map((id) => indicatorNameById.get(id) || `ID ${id}`);
    const shownWinrate = form.public_winrate === '' ? form.winrate : Number(form.public_winrate);

    return (
      <div className="admin-card">
        <div className="admin-row-between">
          <h3 className="admin-section-title">Карточка стратегии</h3>
          <button className="admin-btn-outline" onClick={closeCard}>
            ← К списку
          </button>
        </div>

        {error ? <div className="admin-error">{error}</div> : null}
        {status ? <div className="admin-success">{status}</div> : null}

        <div className="admin-strategy-metrics-grid">
          <div className="admin-strategy-mini-card">
            <div className="admin-metric-label">Пользователей выбрало</div>
            <div className="admin-metric-value small">{form.users_count}</div>
          </div>
          <div className="admin-strategy-mini-card">
            <div className="admin-metric-label">Сигналов выдано</div>
            <div className="admin-metric-value small">{form.signals_count}</div>
          </div>
          <div className="admin-strategy-mini-card">
            <div className="admin-metric-label">Отображаемый Winrate</div>
            <div className="admin-metric-value small">{formatPercent(shownWinrate)}</div>
          </div>
        </div>

        <div className="admin-field">
          <label className="admin-label">Название</label>
          <input
            className="admin-input"
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
          />
        </div>

        <div className="admin-field">
          <label className="admin-label">Иконка</label>
          <input
            className="admin-input"
            value={form.icon}
            onChange={(e) => setForm((prev) => ({ ...prev, icon: e.target.value }))}
          />
        </div>

        <div className="admin-field">
          <label className="admin-label">Таймфреймы</label>
          <div className="admin-indicator-grid">
            {TIMEFRAME_OPTIONS.map((timeframe) => {
              const isSelected = form.timeframes.includes(timeframe);
              return (
                <button
                  key={timeframe}
                  type="button"
                  className={`admin-indicator-toggle ${isSelected ? 'selected' : ''}`}
                  onClick={() => toggleTimeframe(timeframe)}
                >
                  {timeframe}
                </button>
              );
            })}
          </div>
        </div>

        <div className="admin-field">
          <label className="admin-label">Отображаемый Winrate (%)</label>
          <input
            className="admin-input"
            type="number"
            min="0"
            max="100"
            step="0.1"
            value={form.public_winrate}
            onChange={(e) => setForm((prev) => ({ ...prev, public_winrate: e.target.value }))}
            placeholder="Например: 62.5"
          />
          <div className="admin-note">Это публичное значение winrate, которое показывается пользователям во фронте.</div>
          <div className="admin-note">Текущий расчетный winrate по истории: {formatPercent(form.winrate)}.</div>
        </div>

        <div className="admin-row-between">
          {form.initial_is_system ? (
            <label className="admin-muted">
              <input
                type="checkbox"
                checked={form.is_system}
                onChange={(e) => setForm((prev) => ({ ...prev, is_system: e.target.checked }))}
              />{' '}
              Системная стратегия
            </label>
          ) : (
            <div className="admin-note">Пользовательская стратегия не может быть включена как системная.</div>
          )}
          <div className="admin-muted">ID: {form.id}</div>
        </div>

        <div className="admin-field">
          <label className="admin-label">Подключенные индикаторы ({form.indicators.length})</label>
          <div className="admin-chip-list">
            {selectedIndicatorNames.length ? (
              selectedIndicatorNames.map((indicator) => (
                <span key={indicator} className="admin-chip">
                  {indicator}
                </span>
              ))
            ) : (
              <span className="admin-muted">Индикаторы не выбраны</span>
            )}
          </div>
        </div>

        <div className="admin-field">
          <label className="admin-label">Изменить подключенные индикаторы</label>
          <div className="admin-indicator-grid">
            {indicators.map((indicator) => {
              const indicatorId = Number(indicator.id);
              const isSelected = form.indicators.includes(indicatorId);
              return (
                <button
                  key={indicator.id}
                  type="button"
                  className={`admin-indicator-toggle ${isSelected ? 'selected' : ''}`}
                  onClick={() => toggleIndicator(indicatorId)}
                >
                  {indicator.name}
                </button>
              );
            })}
          </div>
          {!indicators.length ? <div className="admin-muted">Список индикаторов пуст</div> : null}
        </div>

        <div className="admin-row-actions">
          <button className="admin-btn" onClick={save}>
            Сохранить
          </button>
          {Number(form.id) !== 1 ? (
            <button className="admin-btn-outline danger" onClick={remove}>
              Удалить
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <div className="admin-card admin-strategy-summary-card">
        <h3 className="admin-section-title">Стратегии</h3>
        <div className="admin-strategy-summary-grid">
          <div className="admin-strategy-summary-item">
            <div className="admin-metric-label">Всего стратегий</div>
            <div className="admin-metric-value small">{computedSummary.total}</div>
          </div>
          <div className="admin-strategy-summary-item system">
            <div className="admin-metric-label">Системные</div>
            <div className="admin-metric-value small">{computedSummary.system}</div>
          </div>
          <div className="admin-strategy-summary-item user">
            <div className="admin-metric-label">Пользовательские</div>
            <div className="admin-metric-value small">{computedSummary.user}</div>
          </div>
        </div>
      </div>

      {error ? <div className="admin-error">{error}</div> : null}
      {status ? <div className="admin-success">{status}</div> : null}
      {loading ? <div className="admin-muted">Загрузка...</div> : null}

      {renderList('Системные стратегии', systemStrategies, 'Системные стратегии не найдены')}
      {renderList('Пользовательские стратегии', userStrategies, 'Пользовательские стратегии не найдены', true)}
    </div>
  );
}
