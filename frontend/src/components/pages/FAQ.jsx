import React from 'react';
import './FAQ.css';

const indicatorGroups = [
  {
    title: 'Trend direction',
    icon: '📈',
    items: [
      ['EMA 9 / EMA50 / EMA200', 'Smooth price movement and help identify short, medium, and long trend direction.'],
      ['MACD', 'Compares moving averages to show momentum shifts and possible trend continuation.'],
      ['ADX + DMI', 'Measures trend strength and compares bullish versus bearish pressure.'],
      ['Supertrend', 'Tracks directional bias and potential trend flips.'],
      ['Ichimoku', 'Combines trend, momentum, and support/resistance zones in one structure.'],
      ['Parabolic SAR', 'Highlights possible trend continuation or reversal points.'],
    ],
  },
  {
    title: 'Momentum and exhaustion',
    icon: '⚡',
    items: [
      ['RSI', 'Shows whether momentum is stretched, balanced, or weakening.'],
      ['Stochastic', 'Tracks where price closes inside its recent range.'],
      ['Stochastic RSI', 'A faster momentum view based on RSI behavior.'],
      ['CCI', 'Finds strong deviations from the typical price average.'],
      ['Williams %R', 'Helps detect overbought and oversold pressure.'],
      ['Momentum', 'Compares current price against previous price action.'],
    ],
  },
  {
    title: 'Levels, volatility, and volume',
    icon: '🧭',
    items: [
      ['Bollinger Bands', 'Shows volatility expansion, compression, and price extremes.'],
      ['ATR', 'Measures average movement size and helps build risk levels.'],
      ['Fibonacci Retracement', 'Maps possible pullback and reaction levels.'],
      ['Pivot Points HL', 'Uses recent highs and lows to mark important reaction zones.'],
      ['VWAP', 'Shows the average traded price weighted by volume.'],
      ['OBV / AD / ADOSC / MFI / RVOL', 'Adds volume and money-flow context behind the price move.'],
    ],
  },
];

const strategyCards = [
  ['👑', 'THE CROWN', 'Balanced trend structure for higher timeframes.'],
  ['🗼', 'THE TOWER', 'Shorter-term structure with volatility and VWAP context.'],
  ['⏳', 'THE PENDULUM', 'Mean-reversion logic using oscillators and bands.'],
  ['⚡', 'THE CHARGE', 'Momentum-focused setup for active market movement.'],
  ['🚢', 'THE FLEET', 'Trend and volume blend for steadier conditions.'],
  ['🏛️', 'THE SOVEREIGN', 'Longer-horizon confirmation with cloud and trend tools.'],
  ['🏹', 'THE LONGBOW', 'Higher timeframe precision with trend confirmation.'],
  ['🦅', 'THE PHOENIX', 'Reversal-focused setup for stretched conditions.'],
  ['👁️', 'THE SENTRY', 'Confirmation-first strategy with trend and level filters.'],
  ['🏰', 'THE WESTMINSTER', 'Conservative structure with volatility, trend, and volume filters.'],
];

const faqItems = [
  {
    question: 'What does a BUY, SELL, or NEUTRAL signal mean?',
    answer:
      'BUY means bullish evidence is stronger than bearish evidence. SELL means bearish evidence dominates. NEUTRAL means the market is mixed, weak, too quiet, or the indicators disagree too much for a clean setup.',
  },
  {
    question: 'Why can the final signal be NEUTRAL when some indicators say BUY or SELL?',
    answer:
      'The final signal is not a simple single-indicator result. It weighs trend, momentum, volatility, volume, session quality, news background, and conflicts between indicators. Mixed evidence usually becomes NEUTRAL.',
  },
  {
    question: 'What are Conservative SL and Target?',
    answer:
      'Conservative SL is a nearby risk boundary based on volatility and levels. Target is a calculated take-profit zone. They are reference levels, not a guarantee that price will reach or respect them.',
  },
  {
    question: 'Why does news matter?',
    answer:
      'High-impact economic events can create sudden volatility. Even a good technical setup may become risky around major news, so the app checks the news background before showing the full context.',
  },
  {
    question: 'Which timeframe should I use?',
    answer:
      'Lower timeframes react faster but are noisier. Higher timeframes are slower but usually cleaner. Each system strategy has allowed timeframes selected to match its logic.',
  },
  {
    question: 'Is this financial advice?',
    answer:
      'No. This app is an educational analytics tool. Signals are generated from historical and live market data and cannot guarantee future results. Always manage risk and make your own decisions.',
  },
];

const quickRules = [
  'Avoid trading during unclear NEUTRAL conditions.',
  'Do not treat one indicator as the full signal.',
  'Check volatility and news before entering.',
  'Use risk limits before thinking about profit.',
];

export default function FAQ({ onAskAI }) {
  const handleAskAI = () => {
    if (typeof onAskAI === 'function') onAskAI();
  };

  return (
    <div className="faq-page">
      <section className="faq-hero">
        <div className="faq-hero-glow" />
        <div className="faq-kicker">Elizabeth Vane knowledge base</div>
        <h1>FAQ</h1>
        <p>
          A practical guide to signals, indicators, strategies, risk levels, and the logic behind the analytics tool.
        </p>
        <button className="faq-ask-btn" type="button" onClick={handleAskAI}>
          <span>💬</span>
          Ask AI
        </button>
      </section>

      <section className="faq-grid faq-stats">
        <div className="faq-mini-card">
          <span className="faq-mini-icon">🧠</span>
          <strong>28</strong>
          <small>available indicators</small>
        </div>
        <div className="faq-mini-card">
          <span className="faq-mini-icon">🏛️</span>
          <strong>10</strong>
          <small>system strategies</small>
        </div>
        <div className="faq-mini-card">
          <span className="faq-mini-icon">🛡️</span>
          <strong>Risk first</strong>
          <small>signals are not guarantees</small>
        </div>
      </section>

      <section className="faq-panel">
        <div className="faq-section-head">
          <span>01</span>
          <h2>How the signal is formed</h2>
        </div>
        <div className="faq-signal-flow">
          <div>
            <b>Market data</b>
            <p>Price, timeframe, volatility, trend, volume, and news context are collected first.</p>
          </div>
          <div>
            <b>Indicator votes</b>
            <p>Each active strategy reads only its connected indicators and turns them into BUY, SELL, or NEUTRAL clues.</p>
          </div>
          <div>
            <b>Final verdict</b>
            <p>The app compares conflicts, confidence, session quality, and levels before showing the final recommendation.</p>
          </div>
        </div>
      </section>

      <section className="faq-panel">
        <div className="faq-section-head">
          <span>02</span>
          <h2>Indicators in this system</h2>
        </div>
        <div className="faq-indicator-groups">
          {indicatorGroups.map((group) => (
            <article className="faq-indicator-card" key={group.title}>
              <div className="faq-card-title">
                <span>{group.icon}</span>
                <h3>{group.title}</h3>
              </div>
              <div className="faq-chip-list">
                {group.items.map(([name, description]) => (
                  <details className="faq-chip-details" key={name}>
                    <summary>{name}</summary>
                    <p>{description}</p>
                  </details>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="faq-panel">
        <div className="faq-section-head">
          <span>03</span>
          <h2>System strategies</h2>
        </div>
        <p className="faq-muted">
          Strategies are not random presets. Each one is a curated mix of indicators and timeframes for a specific market behavior.
        </p>
        <div className="faq-strategy-grid">
          {strategyCards.map(([icon, name, text]) => (
            <article className="faq-strategy-card" key={name}>
              <span>{icon}</span>
              <div>
                <b>{name}</b>
                <p>{text}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="faq-panel">
        <div className="faq-section-head">
          <span>04</span>
          <h2>Practical rules</h2>
        </div>
        <div className="faq-rule-list">
          {quickRules.map((rule) => (
            <div className="faq-rule" key={rule}>
              <span>✓</span>
              <p>{rule}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="faq-panel">
        <div className="faq-section-head">
          <span>05</span>
          <h2>Questions and answers</h2>
        </div>
        <div className="faq-accordion">
          {faqItems.map((item, index) => (
            <details className="faq-item" key={item.question} open={index === 0}>
              <summary>{item.question}</summary>
              <p>{item.answer}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="faq-ai-card">
        <div>
          <span className="faq-ai-icon">💬</span>
          <h2>Need a personal explanation?</h2>
          <p>
            Open AI chat and ask about a signal, indicator, strategy, or risk level in plain language.
          </p>
        </div>
        <button className="faq-ask-btn faq-ask-btn-wide" type="button" onClick={handleAskAI}>
          Ask in AI chat
        </button>
      </section>
    </div>
  );
}
