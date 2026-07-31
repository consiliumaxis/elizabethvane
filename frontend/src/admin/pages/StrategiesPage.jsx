import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';
import { useAdminLocale } from '../useAdminLocale';

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

function StrategyToast({ message, type = 'success', onClose, tr }) {
  if (!message) return null;
  const isError = type === 'error';

  return (
    <div className="admin-toast-viewport" aria-live="polite">
      <div className={`admin-floating-toast ${isError ? 'is-error' : 'is-success'}`} role={isError ? 'alert' : 'status'}>
        <span className="admin-floating-toast-icon" aria-hidden="true">{isError ? '!' : '✓'}</span>
        <span className="admin-floating-toast-copy">
          <strong>{isError ? tr('Action failed', 'Не удалось выполнить действие') : tr('Done', 'Готово')}</strong>
          <span>{message}</span>
        </span>
        <button
          className="admin-floating-toast-close"
          type="button"
          onClick={onClose}
          aria-label={tr('Close notification', 'Закрыть уведомление')}
        >
          ×
        </button>
      </div>
    </div>
  );
}

export default function StrategiesPage() {
  const { tr } = useAdminLocale();
  const [items, setItems] = useState([]);
  const [indicators, setIndicators] = useState([]);
  const [summary, setSummary] = useState(null);
  const [analysisForm, setAnalysisForm] = useState({
    engine: 'backend',
    gpt_model: 'gpt-4o-mini',
    gpt_prompt: '',
    gpt_api_key: '',
    gpt_key_configured: false,
  });
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
        owner_users_count: toInt(item.owner_users_count),
        can_toggle_system: Number(item.can_toggle_system) === 1,
        signals_count: toInt(item.signals_count),
        wins_count: toInt(item.wins_count),
        closed_signals: toInt(item.closed_signals),
        winrate: Number(item.winrate || 0),
        public_winrate: parsePublicWinrate(item.public_winrate),
      }));
      const settings = res.analysis_settings || {};
      setAnalysisForm({
        engine: settings.engine === 'gpt' ? 'gpt' : 'backend',
        gpt_model: settings.gpt_model || 'gpt-4o-mini',
        gpt_prompt: settings.gpt_prompt || '',
        gpt_api_key: '',
        gpt_key_configured: Number(settings.gpt_key_configured) === 1,
      });
      setItems(normalized);
      setIndicators(Array.isArray(res.indicators) ? res.indicators : []);
      setSummary(res.summary || null);
    } catch (e) {
      setError(e.message || tr('Could not load strategies', 'Не удалось загрузить стратегии'));
    } finally {
      setLoading(false);
    }
  }, [tr]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    if (!status) return undefined;
    const timer = window.setTimeout(() => setStatus(''), 4000);
    return () => window.clearTimeout(timer);
  }, [status]);

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
    const timer = window.setTimeout(() => {
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
        can_toggle_system: Boolean(selected.can_toggle_system),
        owner_users_count: toInt(selected.owner_users_count),
        owner_user_id: selected.owner_user_id || null,
        users_count: toInt(selected.users_count),
        signals_count: toInt(selected.signals_count),
        winrate: Number(selected.winrate || 0),
        public_winrate: selected.public_winrate === null ? '' : String(selected.public_winrate),
        indicators: uniqueIndicatorIds,
      });
    }, 0);
    return () => window.clearTimeout(timer);
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
      setError(tr('Strategy name is required', 'Название стратегии обязательно'));
      return;
    }

    const publicWinrate = form.public_winrate === '' ? null : Number(form.public_winrate);
    if (publicWinrate !== null && (!Number.isFinite(publicWinrate) || publicWinrate < 0 || publicWinrate > 100)) {
      setError(tr('Displayed winrate must be a number from 0 to 100', 'Отображаемый winrate должен быть числом от 0 до 100'));
      return;
    }

    setError('');
    setStatus('');
    try {
      const res = await apiAdminFetchJson('/api/admin/strategies/update', {
        method: 'POST',
        body: JSON.stringify({
          id: form.id,
          name: form.name,
          icon: form.icon,
          allowed_timeframes: joinTimeframes(form.timeframes),
          public_winrate: publicWinrate,
          is_system: form.is_system,
          indicators: form.indicators,
        }),
      });
      const savedIndicatorCount = Number(res?.indicator_count);
      if (Number.isFinite(savedIndicatorCount) && savedIndicatorCount !== form.indicators.length) {
        throw new Error(tr(
          `The strategy saved only ${savedIndicatorCount} of ${form.indicators.length} indicators`,
          `В стратегии сохранилось только ${savedIndicatorCount} из ${form.indicators.length} индикаторов`
        ));
      }
      setStatus(tr(
        `Strategy ${form.id} has been saved · ${form.indicators.length} indicators`,
        `Стратегия ${form.id} сохранена · индикаторов: ${form.indicators.length}`
      ));
      await load();
    } catch (e) {
      setError(e.message || tr('Could not save the strategy', 'Не удалось сохранить стратегию'));
    }
  };

  const validateGptKey = async () => {
    if (!analysisForm.gpt_api_key.trim()) {
      setError(tr('Enter a new GPT key to validate it', 'Введите новый GPT ключ для проверки'));
      return;
    }
    setError('');
    setStatus('');
    try {
      const res = await apiAdminFetchJson('/api/admin/strategies/validate-gpt-key', {
        method: 'POST',
        body: JSON.stringify({
          api_key: analysisForm.gpt_api_key,
          model: analysisForm.gpt_model || 'gpt-4o-mini',
        }),
      });
      setStatus(res.warning
        ? tr(`The key works. ${res.warning}`, `Ключ рабочий. ${res.warning}`)
        : tr('GPT key is valid and ready to save', 'Ключ GPT проверен и готов к сохранению'));
    } catch (e) {
      setError(e.message || tr('GPT key validation failed', 'Ключ GPT не прошел проверку'));
    }
  };

  const saveAnalysisSettings = async () => {
    if (analysisForm.engine === 'gpt' && !analysisForm.gpt_key_configured && !analysisForm.gpt_api_key.trim()) {
      setError(tr('Enter and validate a key before enabling GPT analysis', 'Для GPT-анализа нужно сначала указать и проверить ключ'));
      return;
    }
    if (analysisForm.engine === 'gpt' && !analysisForm.gpt_prompt.trim()) {
      setError(tr('The GPT analysis prompt is required', 'Промпт для GPT-анализа обязателен'));
      return;
    }
    setError('');
    setStatus('');
    try {
      await apiAdminFetchJson('/api/admin/analysis-settings', {
        method: 'POST',
        body: JSON.stringify({
          engine: analysisForm.engine,
          gpt_model: analysisForm.gpt_model,
          gpt_prompt: analysisForm.gpt_prompt,
          gpt_api_key: analysisForm.gpt_api_key,
        }),
      });
      setStatus(tr('Global analysis engine settings have been saved', 'Общие настройки движка анализа сохранены'));
      await load();
    } catch (e) {
      setError(e.message || tr('Could not save analysis settings', 'Не удалось сохранить настройки анализа'));
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
      setStatus(tr(`Strategy ${form.id} has been deleted`, `Стратегия ${form.id} удалена`));
      await load();
      closeCard();
    } catch (e) {
      setError(e.message || tr('Could not delete the strategy', 'Не удалось удалить стратегию'));
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
                    <span>{item.name || `${tr('Strategy', 'Стратегия')} ${item.id}`}</span>
                  </div>
                  <span className="admin-entity-gear">⚙️</span>
                </div>

                <div className="admin-entity-meta">ID: {item.id}</div>

                <div className="admin-strategy-meta-line">
                  <span>👥 {tr('Users', 'Пользователи')}: {usersCount}</span>
                  <span>📶 {tr('Signals', 'Сигналы')}: {signalsCount}</span>
                  <span>🎯 {tr('Displayed winrate', 'Отображаемый Winrate')}: {formatPercent(shownWinrate)}</span>
                </div>

                <div className="admin-chip-list">
                  {isSystemStrategy(item) ? (
                    <span className="admin-chip admin-chip-state">{tr('System', 'Системная')}</span>
                  ) : (
                    <span className="admin-chip admin-chip-state user">{tr('Custom', 'Пользовательская')}</span>
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
      <div className="admin-card admin-strategy-editor">
        <StrategyToast
          message={error || status}
          type={error ? 'error' : 'success'}
          tr={tr}
          onClose={() => {
            setError('');
            setStatus('');
          }}
        />
        <div className="admin-row-between admin-strategy-editor-head">
          <h3 className="admin-section-title">{tr('Strategy details', 'Карточка стратегии')}</h3>
          <button className="admin-btn-outline" onClick={closeCard}>
            {tr('← Back to list', '← К списку')}
          </button>
        </div>

        <div className="admin-strategy-metrics-grid">
          <div className="admin-strategy-mini-card">
            <div className="admin-metric-label">{tr('Users', 'Пользователи')}</div>
            <div className="admin-metric-value small">{form.users_count}</div>
          </div>
          <div className="admin-strategy-mini-card">
            <div className="admin-metric-label">{tr('Signals', 'Сигналы')}</div>
            <div className="admin-metric-value small">{form.signals_count}</div>
          </div>
          <div className="admin-strategy-mini-card">
            <div className="admin-metric-label">Winrate</div>
            <div className="admin-metric-value small">{formatPercent(shownWinrate)}</div>
          </div>
        </div>

        <div className="admin-field">
          <label className="admin-label">{tr('Name', 'Название')}</label>
          <input
            className="admin-input"
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
          />
        </div>

        <div className="admin-field">
          <label className="admin-label">{tr('Icon', 'Иконка')}</label>
          <input
            className="admin-input"
            value={form.icon}
            onChange={(e) => setForm((prev) => ({ ...prev, icon: e.target.value }))}
          />
        </div>

        <div className="admin-field">
          <label className="admin-label">{tr('Timeframes', 'Таймфреймы')}</label>
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
          <div className="admin-note admin-timeframe-hint">
            {form.timeframes.length
              ? `${tr('Selected', 'Выбрано')}: ${form.timeframes.join(', ')}`
              : tr('Nothing selected — the strategy is available for all timeframes.', 'Ничего не выбрано — стратегия доступна для всех таймфреймов.')}
          </div>
        </div>

        <div className="admin-field">
          <label className="admin-label">{tr('Displayed winrate (%)', 'Отображаемый Winrate (%)')}</label>
          <input
            className="admin-input"
            type="number"
            min="0"
            max="100"
            step="0.1"
            value={form.public_winrate}
            onChange={(e) => setForm((prev) => ({ ...prev, public_winrate: e.target.value }))}
            placeholder={tr('For example: 62.5', 'Например: 62.5')}
          />
          <div className="admin-note">{tr('This public winrate is shown to users in the frontend.', 'Это публичное значение winrate, которое показывается пользователям во фронте.')}</div>
          <div className="admin-note">{tr('Current calculated winrate from history', 'Текущий расчетный winrate по истории')}: {formatPercent(form.winrate)}.</div>
        </div>

        <div className="admin-strategy-system-row">
          {form.can_toggle_system ? (
            <label className={`admin-system-toggle-card ${form.is_system ? 'is-on' : 'is-off'}`}>
              <input
                className="admin-system-switch-input"
                type="checkbox"
                checked={form.is_system}
                onChange={(e) => setForm((prev) => ({ ...prev, is_system: e.target.checked }))}
                aria-label={tr('Make this a system strategy', 'Сделать стратегию системной')}
              />
              <span className="admin-system-switch-track" aria-hidden="true">
                <span className="admin-system-switch-thumb" />
              </span>
              <span className="admin-system-toggle-copy">
                <strong>{form.is_system ? tr('System strategy', 'Системная стратегия') : tr('Make system-wide', 'Сделать системной')}</strong>
                <small>
                  {form.is_system
                    ? tr('Currently available to all users', 'Сейчас доступна всем пользователям')
                    : tr('Enable to add it to the shared list', 'Включите, чтобы добавить её в общий список')}
                </small>
              </span>
              <span className="admin-system-toggle-status">{form.is_system ? tr('ON', 'ВКЛ') : tr('OFF', 'ВЫКЛ')}</span>
            </label>
          ) : (
            <div className="admin-system-toggle-card is-locked">
              <span className="admin-system-toggle-copy">
                <strong>{tr('Built-in system strategy', 'Встроенная системная стратегия')}</strong>
                <small>{tr('It cannot be converted to a custom strategy', 'Её нельзя перевести в пользовательские')}</small>
              </span>
            </div>
          )}
          <div className="admin-strategy-id-badge">ID: {form.id}</div>
        </div>
        {form.can_toggle_system ? (
          <div className="admin-note">
            {tr(
              'The owner is preserved. When disabled, the strategy disappears for other users and returns to its owner',
              'Владелец сохраняется. После отключения стратегия исчезнет у остальных пользователей и вернётся владельцу'
            )}{form.owner_user_id ? ` (Telegram ID ${form.owner_user_id})` : ''}.
          </div>
        ) : null}

        <div className="admin-field">
          <label className="admin-label">{tr('Connected indicators', 'Подключенные индикаторы')} ({form.indicators.length})</label>
          <div className="admin-chip-list">
            {selectedIndicatorNames.length ? (
              selectedIndicatorNames.map((indicator) => (
                <span key={indicator} className="admin-chip">
                  {indicator}
                </span>
              ))
            ) : (
              <span className="admin-muted">{tr('No indicators selected', 'Индикаторы не выбраны')}</span>
            )}
          </div>
        </div>

        <div className="admin-field">
          <label className="admin-label">{tr('Edit connected indicators', 'Изменить подключенные индикаторы')}</label>
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
          {!indicators.length ? <div className="admin-muted">{tr('The indicator list is empty', 'Список индикаторов пуст')}</div> : null}
        </div>

        <div className="admin-row-actions">
          <button className="admin-btn" onClick={save}>
            {tr('Save', 'Сохранить')}
          </button>
          {Number(form.id) !== 1 ? (
            <button className="admin-btn-outline danger" onClick={remove}>
              {tr('Delete', 'Удалить')}
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <StrategyToast
        message={error || status}
        type={error ? 'error' : 'success'}
        tr={tr}
        onClose={() => {
          setError('');
          setStatus('');
        }}
      />
      <div className="admin-card admin-strategy-summary-card">
        <h3 className="admin-section-title">{tr('Strategies', 'Стратегии')}</h3>
        <div className="admin-strategy-summary-grid">
          <div className="admin-strategy-summary-item">
            <div className="admin-metric-label">{tr('Total', 'Всего')}</div>
            <div className="admin-metric-value small">{computedSummary.total}</div>
          </div>
          <div className="admin-strategy-summary-item system">
            <div className="admin-metric-label">{tr('System', 'Системные')}</div>
            <div className="admin-metric-value small">{computedSummary.system}</div>
          </div>
          <div className="admin-strategy-summary-item user">
            <div className="admin-metric-label">{tr('Custom', 'Пользовательские')}</div>
            <div className="admin-metric-value small">{computedSummary.user}</div>
          </div>
        </div>
      </div>

      <div className="admin-card admin-engine-panel admin-global-engine-panel">
        <div className="admin-row-between">
          <div>
            <h3 className="admin-section-title">{tr('Analysis engine', 'Движок анализа')}</h3>
            <div className="admin-note">
              {tr('Global setting for all strategies. Users cannot see which engine is active.', 'Общая настройка для всех стратегий. Пользователь не видит, какой движок используется.')}
            </div>
          </div>
          <span className={`admin-chip admin-chip-engine ${analysisForm.engine === 'gpt' ? 'gpt' : ''}`}>
            {analysisForm.engine === 'gpt' ? 'GPT' : 'Backend'}
          </span>
        </div>

        <div className="admin-engine-toggle" aria-label={tr('Analysis engine', 'Движок анализа')}>
          <button
            type="button"
            className={analysisForm.engine === 'backend' ? 'active' : ''}
            onClick={() => setAnalysisForm((prev) => ({ ...prev, engine: 'backend' }))}
          >
            Backend
          </button>
          <button
            type="button"
            className={analysisForm.engine === 'gpt' ? 'active' : ''}
            onClick={() => setAnalysisForm((prev) => ({ ...prev, engine: 'gpt' }))}
          >
            GPT
          </button>
        </div>

        <div className="admin-note">
          {tr(
            'Backend keeps the current indicator formula. GPT receives the same raw market data, strategy and indicators, then returns a signal in the standard format.',
            'Backend оставляет текущую формулу индикаторов. GPT получает те же сырые рыночные данные, стратегию и индикаторы, после чего возвращает сигнал в нашем стандартном формате.'
          )}
        </div>

        {analysisForm.engine === 'gpt' ? (
          <div className="admin-gpt-box">
            <div className="admin-field">
              <label className="admin-label">{tr('Model', 'Модель')}</label>
              <input
                className="admin-input"
                value={analysisForm.gpt_model}
                onChange={(e) => setAnalysisForm((prev) => ({ ...prev, gpt_model: e.target.value }))}
                placeholder="gpt-4o-mini"
              />
            </div>

            <div className="admin-field">
              <label className="admin-label">
                GPT {tr('key', 'ключ')} {analysisForm.gpt_key_configured ? <span className="admin-key-state">{tr('key already saved', 'ключ уже сохранён')}</span> : null}
              </label>
              <div className="admin-key-row">
                <input
                  className="admin-input"
                  type="password"
                  value={analysisForm.gpt_api_key}
                  onChange={(e) => setAnalysisForm((prev) => ({ ...prev, gpt_api_key: e.target.value }))}
                  placeholder={analysisForm.gpt_key_configured ? tr('Leave empty to keep the current key', 'Оставьте пустым, если не меняем ключ') : 'sk-...'}
                />
                <button className="admin-btn-outline" type="button" onClick={validateGptKey}>
                  {tr('Validate', 'Проверить')}
                </button>
              </div>
            </div>

            <div className="admin-field">
              <label className="admin-label">{tr('Analysis prompt', 'Промпт анализа')}</label>
              <textarea
                className="admin-textarea admin-gpt-prompt"
                value={analysisForm.gpt_prompt}
                onChange={(e) => setAnalysisForm((prev) => ({ ...prev, gpt_prompt: e.target.value }))}
                rows={12}
              />
              <div className="admin-note">
                {tr(
                  'Describe how GPT should turn raw indicators, price, session and levels into BUY / SELL / NEUTRAL, SL and Take Profit.',
                  'Здесь описываем, как GPT должен превращать сырые индикаторы, цену, сессию и уровни в BUY / SELL / NEUTRAL, SL и Take Profit.'
                )}
              </div>
            </div>
          </div>
        ) : null}

        <div className="admin-row-actions admin-stream-save-row">
          <button className="admin-btn" type="button" onClick={saveAnalysisSettings}>
            {tr('Save engine', 'Сохранить движок')}
          </button>
        </div>
      </div>

      {loading ? <div className="admin-muted">{tr('Loading…', 'Загрузка...')}</div> : null}

      {renderList(tr('System strategies', 'Системные стратегии'), systemStrategies, tr('No system strategies found', 'Системные стратегии не найдены'))}
      {renderList(tr('Custom strategies', 'Пользовательские стратегии'), userStrategies, tr('No custom strategies found', 'Пользовательские стратегии не найдены'), true)}
    </div>
  );
}
