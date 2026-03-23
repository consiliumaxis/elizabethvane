import React, { useEffect, useState } from 'react';
import './BackgroundCandles.css';

export default function BackgroundCandles() {
  const [candles, setCandles] = useState([]);

  useEffect(() => {
    const numCandles = 24;
    
    const generatedCandles = Array.from({ length: numCandles }).map((_, i) => {
      const sizeMultiplier = Math.random() * 0.8 + 0.4;
      const isDistant = sizeMultiplier < 0.7;

      const baseX = (i / numCandles) * 90 + 5;
      const leftPos = baseX + (Math.random() * 3 - 1.5);

      const baseY = 65 - (baseX * 0.55);
      const topPos = baseY + (Math.random() * 10 - 5);

      const isBullCandle = Math.random() > 0.3;

      return {
        id: i,
        isBull: isBullCandle,
        left: `${leftPos}%`,
        top: `${topPos}%`,
        height: `${(Math.random() * 40 + 20) * sizeMultiplier}px`,
        width: `${6 * sizeMultiplier}px`,
        blur: isDistant ? '3px' : '0px',
        opacityBase: isDistant ? 0.05 : 0.15,
        delay: `${Math.random() * 10}s`,
        duration: `${Math.random() * 15 + 15}s`
      };
    });
    
    setCandles(generatedCandles);
  }, []);

  return (
    <div className="bg-candles-container">
      {candles.map((candle) => (
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