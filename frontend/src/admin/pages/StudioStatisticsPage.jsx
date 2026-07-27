import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';
import { useAdminLocale } from '../useAdminLocale';

const isoDate = (value = new Date()) => {
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60 * 1000).toISOString().slice(0, 10);
};

const dateDaysAgo = (days) => {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return isoDate(date);
};

const PERIODS = ['today', '7days', '30days', 'custom'];

const emptyEditor = (date = isoDate()) => ({
  date,
  new_users: '',
  total_users: '',
  deals: '',
  volume: '',
  strategy_winrates: [],
});

const normalizeEditor = (day, strategies, date) => {
  const saved = new Map(
    (day?.strategy_winrates || []).map((item) => [
      String(item.strategy_id || item.strategy_name || ''),
      String(item.winrate ?? ''),
    ])
  );
  return {
    date: day?.date || date || isoDate(),
    new_users: String(day?.new_users ?? ''),
    total_users: String(day?.total_users ?? ''),
    deals: String(day?.deals ?? ''),
    volume: String(day?.volume ?? ''),
    strategy_winrates: (strategies || []).map((strategy) => ({
      strategy_id: strategy.id,
      strategy_name: strategy.name,
      winrate: saved.get(String(strategy.id)) ?? saved.get(String(strategy.name)) ?? '',
    })),
  };
};

export default function StudioStatisticsPage({ studioMode, onStudioModeChange }) {
  const { locale, tr } = useAdminLocale();
  const [period, setPeriod] = useState('7days');
  const [dateFrom, setDateFrom] = useState(dateDaysAgo(6));
  const [dateTo, setDateTo] = useState(isoDate());
  const [summary, setSummary] = useState(null);
  const [strategies, setStrategies] = useState([]);
  const [days, setDays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editorOpen, setEditorOpen] = useState(false);
  const [editor, setEditor] = useState(emptyEditor);
  const [editorExists, setEditorExists] = useState(false);
  const [editorLoading, setEditorLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const numberFormatter = useMemo(
    () => new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }),
    [locale]
  );
  const volumeFormatter = useMemo(
    () => new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 2,
    }),
    [locale]
  );

  const applyPeriod = useCallback((nextPeriod) => {
    setPeriod(nextPeriod);
    if (nextPeriod === 'today') {
      setDateFrom(isoDate());
      setDateTo(isoDate());
    } else if (nextPeriod === '7days') {
      setDateFrom(dateDaysAgo(6));
      setDateTo(isoDate());
    } else if (nextPeriod === '30days') {
      setDateFrom(dateDaysAgo(29));
      setDateTo(isoDate());
    }
  }, []);

  const loadStatistics = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await apiAdminFetchJson(
        `/api/admin/studio-statistics?date_from=${encodeURIComponent(dateFrom)}&date_to=${encodeURIComponent(dateTo)}`
      );
      setSummary(result?.summary || null);
      setStrategies(Array.isArray(result?.strategies) ? result.strategies : []);
      setDays(Array.isArray(result?.days) ? result.days.slice().reverse() : []);
    } catch (requestError) {
      setError(
        requestError?.message
        || tr('Could not load presentation statistics.', 'Не удалось загрузить презентационную статистику.')
      );
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, tr]);

  useEffect(() => {
    const timer = window.setTimeout(loadStatistics, 0);
    return () => window.clearTimeout(timer);
  }, [loadStatistics]);

  const openEditor = useCallback(async (date = isoDate()) => {
    setEditorOpen(true);
    setEditorLoading(true);
    setError('');
    setNotice('');
    try {
      const result = await apiAdminFetchJson(
        `/api/admin/studio-statistics/day/${encodeURIComponent(date)}`
      );
      const options = Array.isArray(result?.strategies) ? result.strategies : strategies;
      setStrategies(options);
      setEditorExists(Boolean(result?.day));
      setEditor(normalizeEditor(result?.day, options, date));
    } catch (requestError) {
      setEditor(emptyEditor(date));
      setEditorExists(false);
      setError(requestError?.message || tr('Could not load this day.', 'Не удалось загрузить данные за день.'));
    } finally {
      setEditorLoading(false);
    }
  }, [strategies, tr]);

  const updateEditorField = (field, value) => {
    setEditor((current) => ({ ...current, [field]: value }));
  };

  const updateWinrate = (strategyId, value) => {
    setEditor((current) => ({
      ...current,
      strategy_winrates: current.strategy_winrates.map((item) => (
        String(item.strategy_id) === String(strategyId)
          ? { ...item, winrate: value }
          : item
      )),
    }));
  };

  const saveDay = async () => {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await apiAdminFetchJson('/api/admin/studio-statistics/day', {
        method: 'POST',
        body: JSON.stringify({
          ...editor,
          strategy_winrates: editor.strategy_winrates.filter(
            (item) => String(item.winrate).trim() !== ''
          ),
        }),
      });
      setNotice(tr(`Data for ${editor.date} has been saved.`, `Данные за ${editor.date} сохранены.`));
      setEditorOpen(false);
      await loadStatistics();
    } catch (requestError) {
      setError(requestError?.message || tr('Could not save the day.', 'Не удалось сохранить данные за день.'));
    } finally {
      setSaving(false);
    }
  };

  const deleteDay = async () => {
    const confirmed = window.confirm(
      tr(
        `Delete all presentation data for ${editor.date}?`,
        `Удалить все презентационные данные за ${editor.date}?`
      )
    );
    if (!confirmed) return;

    setSaving(true);
    setError('');
    try {
      await apiAdminFetchJson(
        `/api/admin/studio-statistics/day/${encodeURIComponent(editor.date)}`,
        { method: 'DELETE' }
      );
      setEditorOpen(false);
      setNotice(tr(`Data for ${editor.date} has been deleted.`, `Данные за ${editor.date} удалены.`));
      await loadStatistics();
    } catch (requestError) {
      setError(requestError?.message || tr('Could not delete the day.', 'Не удалось удалить данные за день.'));
    } finally {
      setSaving(false);
    }
  };

  const returnToAdminMenu = useCallback(() => {
    onStudioModeChange(false);
    window.setTimeout(() => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }, 0);
  }, [onStudioModeChange]);

  const periodTitle = useMemo(() => {
    if (dateFrom === dateTo) {
      return new Intl.DateTimeFormat(locale, {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      }).format(new Date(`${dateFrom}T12:00:00`));
    }
    const format = new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short' });
    return `${format.format(new Date(`${dateFrom}T12:00:00`))} — ${format.format(new Date(`${dateTo}T12:00:00`))}`;
  }, [dateFrom, dateTo, locale]);

  const metrics = [
    {
      id: 'new-users',
      label: tr('New users', 'Новые пользователи'),
      value: numberFormatter.format(summary?.new_users || 0),
      icon: '↗',
      tone: 'blue',
    },
    {
      id: 'total-users',
      label: tr('Total users', 'Всего пользователей'),
      value: numberFormatter.format(summary?.total_users || 0),
      icon: '◎',
      tone: 'violet',
    },
    {
      id: 'deals',
      label: tr('Deals', 'Сделки'),
      value: numberFormatter.format(summary?.deals || 0),
      icon: '⇄',
      tone: 'green',
    },
    {
      id: 'volume',
      label: tr('Volume', 'Объём'),
      value: volumeFormatter.format(Number(summary?.volume || 0)),
      icon: '$',
      tone: 'gold',
    },
  ];

  return (
    <div className={`studio-statistics-page ${studioMode ? 'is-studio' : ''}`}>
      {!studioMode ? (
        <section className="admin-card studio-control-card">
          <div className="studio-control-head">
            <div>
              <div className="admin-badge">{tr('Presentation data', 'Презентационные данные')}</div>
              <h2 className="admin-section-title">{tr('Statistics', 'Статистика')}</h2>
              <p className="admin-muted studio-intro">
                {tr(
                  'A separate, manually maintained dataset for demos and screen recordings. Real product analytics remain unchanged in Dashboard.',
                  'Отдельный набор ручных данных для демонстраций и записи экрана. Реальная аналитика продукта остаётся без изменений в разделе «Дашборд».'
                )}
              </p>
            </div>
            <div className="studio-head-actions">
              <button type="button" className="admin-btn-outline" onClick={() => onStudioModeChange(true)}>
                <span aria-hidden="true">◫</span> {tr('Studio mode', 'Режим студии')}
              </button>
              <button type="button" className="admin-btn" onClick={() => openEditor()}>
                <span aria-hidden="true">＋</span> {tr('Add / edit day', 'Добавить / изменить день')}
              </button>
            </div>
          </div>

          <div className="studio-period-toolbar" aria-label={tr('Statistics period', 'Период статистики')}>
            <div className="studio-period-tabs">
              {PERIODS.map((item) => {
                const label = {
                  today: tr('Today', 'Сегодня'),
                  '7days': tr('7 days', '7 дней'),
                  '30days': tr('30 days', '30 дней'),
                  custom: tr('Custom', 'Произвольный'),
                }[item];
                return (
                  <button
                    key={item}
                    type="button"
                    className={period === item ? 'active' : ''}
                    onClick={() => applyPeriod(item)}
                  >
                    {label}
                  </button>
                );
              })}
            </div>

            {period === 'custom' ? (
              <div className="studio-custom-range">
                <label>
                  <span>{tr('From', 'С')}</span>
                  <input
                    className="admin-input"
                    type="date"
                    value={dateFrom}
                    onChange={(event) => setDateFrom(event.target.value)}
                  />
                </label>
                <label>
                  <span>{tr('To', 'По')}</span>
                  <input
                    className="admin-input"
                    type="date"
                    value={dateTo}
                    onChange={(event) => setDateTo(event.target.value)}
                  />
                </label>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {error ? <div className="admin-error studio-floating-message">{error}</div> : null}
      {notice && !studioMode ? <div className="admin-success studio-floating-message">{notice}</div> : null}

      <section className={`studio-dashboard ${loading ? 'is-loading' : ''}`}>
        <div className="studio-dashboard-glow studio-dashboard-glow-one" />
        <div className="studio-dashboard-glow studio-dashboard-glow-two" />
        <header className="studio-dashboard-header">
          <div>
            <button
              type="button"
              className="studio-brand-mark studio-admin-return"
              onClick={returnToAdminMenu}
              aria-label={tr('Back to Admin Center', 'Вернуться в админ-центр')}
              title={tr('Back to Admin Center', 'Вернуться в админ-центр')}
            >
              <span className="studio-brand-monogram">EV</span>
              <span className="studio-brand-return-icon" aria-hidden="true">←</span>
            </button>
            <div>
              <div className="studio-eyebrow">ELIZABETH VANE</div>
              <h2>{tr('Performance overview', 'Обзор показателей')}</h2>
            </div>
          </div>
          <div className="studio-period-caption">
            <span>{tr('Selected period', 'Выбранный период')}</span>
            <strong>{periodTitle}</strong>
          </div>
        </header>

        <div className="studio-metric-grid">
          {metrics.map((metric) => (
            <article key={metric.id} className={`studio-metric studio-tone-${metric.tone}`}>
              <div className="studio-metric-top">
                <span className="studio-metric-icon">{metric.icon}</span>
                <span className="studio-metric-trend">{metric.id === 'volume' ? 'USD' : 'LIVE'}</span>
              </div>
              <div className="studio-metric-value">{metric.value}</div>
              <div className="studio-metric-label">{metric.label}</div>
            </article>
          ))}
        </div>

        <div className="studio-winrate-panel">
          <div className="studio-panel-title">
            <div>
              <span>{tr('Strategy performance', 'Эффективность стратегий')}</span>
              <small>{tr('Average winrate for the selected period', 'Средний винрейт за выбранный период')}</small>
            </div>
            <div className="studio-days-badge">
              {numberFormatter.format(summary?.days_with_data || 0)} {tr('days with data', 'дней с данными')}
            </div>
          </div>

          {(summary?.strategy_winrates || []).length ? (
            <div className="studio-winrate-list">
              {summary.strategy_winrates.map((strategy, index) => (
                <div className="studio-winrate-row" key={`${strategy.strategy_id || strategy.strategy_name}-${index}`}>
                  <div className="studio-strategy-identity">
                    <span className="studio-strategy-rank">{String(index + 1).padStart(2, '0')}</span>
                    <span>{strategy.strategy_name}</span>
                  </div>
                  <div className="studio-winrate-track" aria-hidden="true">
                    <span style={{ width: `${Math.max(0, Math.min(100, strategy.winrate))}%` }} />
                  </div>
                  <strong>{Number(strategy.winrate).toFixed(1)}%</strong>
                </div>
              ))}
            </div>
          ) : (
            <div className="studio-empty-state">
              <span>⌁</span>
              <strong>{tr('No strategy data for this period', 'Нет данных по стратегиям за этот период')}</strong>
              {!studioMode ? (
                <small>{tr('Add winrates in “Add / edit day”.', 'Добавьте винрейты через «Добавить / изменить день».')}</small>
              ) : null}
            </div>
          )}
        </div>

        <footer className="studio-dashboard-footer">
          <span>PRIVATE TRADING ANALYTICS</span>
          <span>{tr('Updated from Admin Center', 'Обновлено из админ-центра')}</span>
        </footer>

        {studioMode ? (
          <button
            type="button"
            className="studio-exit-button"
            onClick={() => onStudioModeChange(false)}
            title={tr('Exit studio mode', 'Выйти из режима студии')}
          >
            <span>×</span>
            {tr('Exit studio', 'Выйти')}
          </button>
        ) : null}
      </section>

      {!studioMode && days.length ? (
        <section className="admin-card studio-days-card">
          <h3 className="admin-section-title">{tr('Days in this period', 'Дни в этом периоде')}</h3>
          <div className="admin-muted">
            {tr('Select a day to review or edit it.', 'Выберите день, чтобы посмотреть или изменить его.')}
          </div>
          <div className="studio-days-list">
            {days.map((day) => (
              <button type="button" key={day.date} onClick={() => openEditor(day.date)}>
                <span>
                  <strong>{new Intl.DateTimeFormat(locale, {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                  }).format(new Date(`${day.date}T12:00:00`))}</strong>
                  <small>
                    {numberFormatter.format(day.deals)} {tr('deals', 'сделок')} · {volumeFormatter.format(Number(day.volume || 0))}
                  </small>
                </span>
                <span className="studio-day-edit">{tr('Edit', 'Изменить')} →</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {editorOpen ? (
        <div className="studio-modal-backdrop" role="presentation" onMouseDown={() => !saving && setEditorOpen(false)}>
          <div
            className="studio-editor-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="studio-editor-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="studio-editor-head">
              <div>
                <div className="admin-badge">{tr('Daily entry', 'Данные за день')}</div>
                <h3 id="studio-editor-title">{tr('Add / edit day', 'Добавить / изменить день')}</h3>
              </div>
              <button
                type="button"
                className="studio-modal-close"
                onClick={() => setEditorOpen(false)}
                disabled={saving}
                aria-label={tr('Close', 'Закрыть')}
              >
                ×
              </button>
            </div>

            {editorLoading ? (
              <div className="studio-editor-loading">{tr('Loading day…', 'Загрузка дня…')}</div>
            ) : (
              <>
                <div className="studio-editor-grid">
                  <label className="admin-field studio-date-field">
                    <span className="admin-label">{tr('Date', 'Дата')}</span>
                    <input
                      className="admin-input"
                      type="date"
                      value={editor.date}
                      onChange={(event) => openEditor(event.target.value)}
                    />
                  </label>
                  <label className="admin-field">
                    <span className="admin-label">{tr('New users', 'Новые пользователи')}</span>
                    <input
                      className="admin-input"
                      type="number"
                      min="0"
                      step="1"
                      value={editor.new_users}
                      onChange={(event) => updateEditorField('new_users', event.target.value)}
                      placeholder="0"
                    />
                    <small>{tr('Added to period totals', 'Суммируется за период')}</small>
                  </label>
                  <label className="admin-field">
                    <span className="admin-label">{tr('Total users', 'Всего пользователей')}</span>
                    <input
                      className="admin-input"
                      type="number"
                      min="0"
                      step="1"
                      value={editor.total_users}
                      onChange={(event) => updateEditorField('total_users', event.target.value)}
                      placeholder={tr('End-of-day total', 'Итого на конец дня')}
                    />
                    <small>{tr('Latest value in the period is shown', 'Показывается последнее значение в периоде')}</small>
                  </label>
                  <label className="admin-field">
                    <span className="admin-label">{tr('Deals', 'Сделки')}</span>
                    <input
                      className="admin-input"
                      type="number"
                      min="0"
                      step="1"
                      value={editor.deals}
                      onChange={(event) => updateEditorField('deals', event.target.value)}
                      placeholder="0"
                    />
                    <small>{tr('Added to period totals', 'Суммируется за период')}</small>
                  </label>
                  <label className="admin-field">
                    <span className="admin-label">{tr('Volume, USD', 'Объём, USD')}</span>
                    <input
                      className="admin-input"
                      type="number"
                      min="0"
                      step="0.01"
                      value={editor.volume}
                      onChange={(event) => updateEditorField('volume', event.target.value)}
                      placeholder="0.00"
                    />
                    <small>{tr('Added to period totals', 'Суммируется за период')}</small>
                  </label>
                </div>

                <div className="studio-strategy-editor">
                  <div>
                    <h4>{tr('Winrate by strategy', 'Винрейт по стратегиям')}</h4>
                    <p>{tr(
                      'Fill only the strategies you want to display. The period shows the average of completed days.',
                      'Заполняйте только нужные стратегии. За период показывается среднее по заполненным дням.'
                    )}</p>
                  </div>
                  <div className="studio-strategy-inputs">
                    {editor.strategy_winrates.length ? editor.strategy_winrates.map((strategy) => (
                      <label key={strategy.strategy_id}>
                        <span>{strategy.strategy_name}</span>
                        <span className="studio-percent-input">
                          <input
                            type="number"
                            min="0"
                            max="100"
                            step="0.1"
                            value={strategy.winrate}
                            onChange={(event) => updateWinrate(strategy.strategy_id, event.target.value)}
                            placeholder="—"
                          />
                          <b>%</b>
                        </span>
                      </label>
                    )) : (
                      <div className="admin-muted">
                        {tr('No strategies are configured yet.', 'Стратегии пока не настроены.')}
                      </div>
                    )}
                  </div>
                </div>

                <div className="studio-editor-actions">
                  {editorExists ? (
                    <button type="button" className="admin-btn-danger" onClick={deleteDay} disabled={saving}>
                      {tr('Delete day', 'Удалить день')}
                    </button>
                  ) : <span />}
                  <div>
                    <button
                      type="button"
                      className="admin-btn-outline"
                      onClick={() => setEditorOpen(false)}
                      disabled={saving}
                    >
                      {tr('Cancel', 'Отмена')}
                    </button>
                    <button type="button" className="admin-btn" onClick={saveDay} disabled={saving}>
                      {saving ? tr('Saving…', 'Сохранение…') : tr('Save day', 'Сохранить день')}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
