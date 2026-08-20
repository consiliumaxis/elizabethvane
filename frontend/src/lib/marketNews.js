const NEWS_WINDOW_MS = 30 * 60 * 1000;

const parseEventTime = (value) => {
  const raw = String(value || '');
  if (!raw) return Number.NaN;
  const normalized = raw.includes('Z') ? raw : `${raw.replace(' ', 'T')}Z`;
  return new Date(normalized).getTime();
};

export function getFilteredNewsStatus(news, pairSymbol, now = Date.now()) {
  const calendar = Array.isArray(news?.economicCalendar) ? news.economicCalendar : [];
  if (!calendar.length) {
    return {
      events: [],
      warningEvents: [],
      isCalm: true,
      isWarning: false,
      noNews: true,
    };
  }

  const cleanPair = String(pairSymbol || '').replace(/[^A-Za-z]/g, '').toUpperCase();
  const currencies = cleanPair.length >= 6
    ? [cleanPair.slice(0, 3), cleanPair.slice(3, 6)]
    : [];

  const events = calendar
    .filter((item) => {
      const eventTime = parseEventTime(item?.time);
      if (!Number.isFinite(eventTime) || now > eventTime + NEWS_WINDOW_MS) return false;
      const currency = item?.currency || 'ALL';
      return !currencies.length || currency === 'ALL' || currencies.includes(currency);
    })
    .sort((left, right) => parseEventTime(left?.time) - parseEventTime(right?.time));

  const warningEvents = events.filter((item) => {
    const eventTime = parseEventTime(item?.time);
    const difference = eventTime - now;
    return item?.impact === 'high'
      && difference <= NEWS_WINDOW_MS
      && difference >= -NEWS_WINDOW_MS;
  });

  return {
    events,
    warningEvents,
    isCalm: warningEvents.length === 0,
    isWarning: warningEvents.length > 0,
    noNews: events.length === 0,
  };
}
