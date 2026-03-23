import React, { useEffect, useState, memo } from 'react';

const TradingViewChart = memo(({ symbol, interval, t, isDemo }) => {
  const [containerId] = useState('tv_chart_' + Math.random().toString(36).substring(7));
  const [viewMode, setViewMode] = useState('collapsed'); 

  const chartT = t?.tvChart || {
    title: "Live Market Chart",
    chart: "Chart",
    collapse: "Collapse",
    expand: "Expand"
  };

  const mapInterval = (inv) => {
    if (!inv) return '5';
    const num = parseInt(inv);
    if (inv.includes('m')) return num.toString();
    if (inv.includes('h')) return (num * 60).toString();
    if (inv.includes('d')) return 'D';
    return '5';
  };

  const getTVSymbol = (sym) => {
    if (!sym) return 'OANDA:EURUSD';
    if (sym.includes(':')) return sym;

    const DEMO_SYMBOLS = {
      'XAUUSD': 'OANDA:XAUUSD',
      'XAGUSD': 'OANDA:XAGUSD',
      'XPTUSD': 'OANDA:XPTUSD',
      'XPDUSD': 'OANDA:XPDUSD',
      
      'WTIUSD': 'TVC:USOIL',   
      'XBRUSD': 'TVC:UKOIL',   
      'NGUSD':  'TVC:NATGAS',  
      
      'HG1': 'COMEX:HG1!',     
      
      'W_1': 'CBOT:ZW1!',      
      'C_1': 'CBOT:ZC1!',      
      'S_1': 'CBOT:ZS1!',      
      'KC1': 'ICEUS:KC1!',     
      'CC1': 'ICEUS:CC1!',     
      'SB1': 'ICEUS:SB1!',     
      'CT1': 'ICEUS:CT1!',     
      
      'SPX': 'TVC:SPX',
      'NDX': 'TVC:NDX',
      'DJI': 'TVC:DJI',
      'DAX': 'TVC:DAX',
      'UK100': 'TVC:UKX',
      'NI225': 'TVC:NI225'
    };

    const cleanSym = sym.replace(/[\/-]/g, '');
    return DEMO_SYMBOLS[cleanSym] || `OANDA:${cleanSym}`;
  };

  const tvInterval = mapInterval(interval);
  const tvSymbol = getTVSymbol(symbol);

  const getInitialRange = (tvInv) => {
    if (tvInv === '1' || tvInv === '5') return '1D';
    if (tvInv === '15' || tvInv === '30') return '5D';
    if (tvInv === '60') return '1M';
    if (tvInv === 'D') return '3M';
    return '1D';
  };

  useEffect(() => {
    const container = document.getElementById(containerId);

    const initWidget = () => {
      if (window.TradingView && container) {
        container.innerHTML = '';
        
        new window.TradingView.widget({
          autosize: true,
          symbol: tvSymbol,
          interval: tvInterval,
          range: getInitialRange(tvInterval),
          timezone: "Etc/UTC",
          theme: "dark",
          style: "1",
          locale: "en",
          enable_publishing: false,
          backgroundColor: "#060a14",
          gridColor: "transparent",
          hide_top_toolbar: false,
          hide_legend: true, 
          save_image: false,
          container_id: containerId,
          allow_symbol_change: false,
          hide_volume: false,
          toolbar_bg: "#09101F",
          disabled_features: [
            "header_symbol_search",
            "header_compare"
          ],
          overrides: {
            "paneProperties.background": "#060a14",
            "paneProperties.vertGridProperties.color": "rgba(255, 255, 255, 0.02)",
            "paneProperties.horzGridProperties.color": "rgba(255, 255, 255, 0.02)",
            "scalesProperties.textColor": "#888888",
            "mainSeriesProperties.candleStyle.upColor": "#2ecc71",
            "mainSeriesProperties.candleStyle.downColor": "#e74c3c",
            "mainSeriesProperties.candleStyle.borderUpColor": "#2ecc71",
            "mainSeriesProperties.candleStyle.borderDownColor": "#e74c3c",
            "mainSeriesProperties.candleStyle.wickUpColor": "#2ecc71",
            "mainSeriesProperties.candleStyle.wickDownColor": "#e74c3c",
          }
        });
      }
    };

    let tvScript = document.getElementById('tv-script');
    
    if (!tvScript) {
      tvScript = document.createElement('script');
      tvScript.id = 'tv-script';
      tvScript.src = 'https://s3.tradingview.com/tv.js';
      tvScript.async = true;
      document.body.appendChild(tvScript);
      tvScript.addEventListener('load', initWidget);
    } else {
      initWidget();
    }

    return () => {
      if (tvScript) {
        tvScript.removeEventListener('load', initWidget);
      }
    };
  }, [tvSymbol, tvInterval, containerId]);

  useEffect(() => {
    if (viewMode !== 'collapsed') {
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 100);
    }
  }, [viewMode]);

  return (
    <div className={
      viewMode === 'fullscreen' ? "tv-fullscreen-wrapper" : 
      viewMode === 'inline' ? "tv-inline-wrapper" : 
      "tv-collapsed-wrapper"
    }>
      {viewMode === 'fullscreen' && <div className="tv-backdrop" onClick={() => setViewMode('inline')}></div>}
      
      <div className="tv-content">
        <div className="tv-header" style={{ borderBottom: viewMode === 'collapsed' ? 'none' : '' }}>
          <div style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
            <span className="tv-pulse-dot"></span>
            <span className="tv-title">{chartT.title}</span>
          </div>
          <div style={{display: 'flex', gap: '8px'}}>
            
            {viewMode === 'collapsed' && (
              <button className="tv-toggle-btn" onClick={() => setViewMode('inline')}>
                <span style={{marginRight: '5px'}}>▼</span> {chartT.chart}
              </button>
            )}

            {viewMode === 'inline' && (
              <>
                <button className="tv-toggle-btn" onClick={() => setViewMode('collapsed')}>
                  <span style={{marginRight: '5px'}}>▲</span> {chartT.collapse}
                </button>
                <button className="tv-toggle-btn" onClick={() => setViewMode('fullscreen')}>
                  <span style={{marginRight: '5px'}}>⛶</span> {chartT.expand}
                </button>
              </>
            )}

            {viewMode === 'fullscreen' && (
              <button className="tv-toggle-btn" onClick={() => setViewMode('inline')}>
                <span style={{marginRight: '5px'}}>✕</span> {chartT.collapse}
              </button>
            )}

          </div>
        </div>
        
        <div style={{ display: viewMode === 'collapsed' ? 'none' : 'block', flex: 1, width: '100%', height: '100%', position: 'relative' }}>
          <div id={containerId} className="tv-chart-container" style={{ width: '100%', height: '100%' }} />
          
          {isDemo && (
            <div style={{ position: 'absolute', bottom: 0, left: 0, width: '85px', height: '32px', background: '#060a14', zIndex: 100, pointerEvents: 'none' }}></div>
          )}
        </div>

      </div>
    </div>
  );
});

export default TradingViewChart;