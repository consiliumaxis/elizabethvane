import './BackgroundCandles.css';

const pseudoRandom = (seed) => {
  const value = Math.sin(seed * 12.9898) * 43758.5453;
  return value - Math.floor(value);
};

const CANDLES = Array.from({ length: 24 }).map((_, index) => {
  const sizeMultiplier = pseudoRandom(index + 1) * 0.8 + 0.4;
  const isDistant = sizeMultiplier < 0.7;

  const baseX = (index / 24) * 90 + 5;
  const leftPos = baseX + (pseudoRandom(index + 2) * 3 - 1.5);

  const baseY = 65 - (baseX * 0.55);
  const topPos = baseY + (pseudoRandom(index + 3) * 10 - 5);

  const isBullCandle = pseudoRandom(index + 4) > 0.3;

  return {
    id: index,
    isBull: isBullCandle,
    left: `${leftPos}%`,
    top: `${topPos}%`,
    height: `${(pseudoRandom(index + 5) * 40 + 20) * sizeMultiplier}px`,
    width: `${6 * sizeMultiplier}px`,
    blur: isDistant ? '3px' : '0px',
    opacityBase: isDistant ? 0.05 : 0.15,
    delay: `${pseudoRandom(index + 6) * 10}s`,
    duration: `${pseudoRandom(index + 7) * 15 + 15}s`
  };
});

export default function BackgroundCandles() {

  return (
    <div className="bg-candles-container">
      {CANDLES.map((candle) => (
        <div
          key={candle.id}
          className={`bg-candle ${candle.isBull ? 'bull' : 'bear'}`}
          style={{
            left: candle.left,
            top: candle.top,
            width: candle.width,
            filter: `blur(${candle.blur})`,
            '--base-opacity': candle.opacityBase,
            animationDelay: candle.delay,
            animationDuration: candle.duration,
          }}
        >
          <div className="wick"></div>
          <div className="body" style={{ height: candle.height }}></div>
        </div>
      ))}
    </div>
  );
}
