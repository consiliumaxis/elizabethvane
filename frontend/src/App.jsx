import { useEffect, useMemo, useState, useRef } from 'react';
import { initTelegramApp } from './lib/tgSetup';

import Loader from './components/Loader/Loader';
import BinaryHome from './components/binary/BinaryHome';
import BinarySignalSettings from './components/binary/BinarySignalSettings';
import ForexHome from './components/forex/ForexHome';
import ForexAnalysisSettings from './components/forex/ForexAnalysisSettings';

import DemoHome from './components/demo/DemoHome';
import DemoAnalysisSettings from './components/demo/DemoAnalysisSettings';

import Profile from './components/pages/Profile';
import History from './components/pages/History';
import ChatAI from './components/pages/ChatAI';
import FAQ from './components/pages/FAQ';
import Support from './components/pages/Support';
import LogAnalysis from './components/pages/LogAnalysis';

import Header from './components/Header/Header.jsx';
import BackgroundCandles from './components/BackgroundCandles/BackgroundCandles.jsx';
import { texts } from './locales/texts';

function App() {
  const [user, setUser] = useState(null);
  const [currentPage, setCurrentPage] = useState('');
  const [toastMessage, setToastMessage] = useState(null);
  const [strategies, setStrategies] = useState([]);
  const [allIndicators, setAllIndicators] = useState([]);

  const [forexParams, setForexParams] = useState({ pair: null, exp: null });
  const [binaryParams, setBinaryParams] = useState({ pair: null, exp: null });
  const [profileScrollTarget, setProfileScrollTarget] = useState(null);

  const [activeAnalysisPreload, setActiveAnalysisPreload] = useState(null);
  const [faqSourcePage, setFaqSourcePage] = useState(null);

  const [safeAreaTop, setSafeAreaTop] = useState(0);
  const [contentAreaTop, setContentAreaTop] = useState(55);

  const activeBackHandler = useRef(null); 

  const t = texts.en;

  useEffect(() => {
    const syncUser = async () => {
      try {
        const tg = await initTelegramApp();
        if (!tg) return;

        const tgUser = tg.initDataUnsafe?.user;
        if (!tgUser) return;

        await fetch('/api/user/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: tgUser.id,
            username: tgUser.username || '',
            first_name: tgUser.first_name || '',
            avatar_url: tgUser.photo_url || ''
          })
        });

        const resProfile = fetch('/api/user/profile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: tgUser.id })
        });

        const resStrats = fetch(`/api/strategies?user_id=${tgUser.id}`);
        const resInd = fetch('/api/indicators');

        const [res, stratRes, indRes] = await Promise.all([resProfile, resStrats, resInd]);

        if (indRes.ok) {
          const indData = await indRes.json();
          setAllIndicators(indData.indicators || []);
        }

        if (stratRes.ok) {
          const stratData = await stratRes.json();
          setStrategies(stratData.strategies || []);
        }

        if (res.ok) {
          const userData = await res.json();
          if (!userData.user_id) userData.user_id = tgUser.id;
          setUser(userData);
          
          if (userData.mode === 'demo') {
            setCurrentPage('demoHome');
          } else {
            setCurrentPage(userData.mode === 'binary' ? 'signals' : 'analysis');
          }
        }
      } catch (error) {
        const fallbackUser = { mode: 'binary', strategy_id: 1, lang: 'en' };
        setUser(fallbackUser);
        setCurrentPage('signals');
      }
    };

    syncUser();
  }, []);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg?.expand) tg.expand();

    const updateSafeArea = () => {
      const platform = (tg?.platform || '').toLowerCase();

      const isDesktopPlatform =
        platform === 'tdesktop' ||
        platform === 'web' ||
        platform === 'macos';

      let sTop = Number(tg?.safeAreaInset?.top || 0);
      let cTop = Number(tg?.contentSafeAreaInset?.top || 0);

      if (isDesktopPlatform) {
        if (!sTop) sTop = 0;
        if (!cTop) cTop = 0;
      } else {
        if (!cTop || cTop <= sTop) {
          cTop = Math.max(sTop + 52, 56);
        }
      }

      setSafeAreaTop(sTop);
      setContentAreaTop(cTop);
    };

    updateSafeArea();
    const timer = setTimeout(updateSafeArea, 300);

    if (tg?.onEvent) {
      tg.onEvent('contentSafeAreaChanged', updateSafeArea);
      tg.onEvent('safeAreaChanged', updateSafeArea);
    }

    return () => {
      clearTimeout(timer);
      if (tg?.offEvent) {
        tg.offEvent('contentSafeAreaChanged', updateSafeArea);
        tg.offEvent('safeAreaChanged', updateSafeArea);
      }
    };
  }, []);

  const handleGoHome = () => {
    activeBackHandler.current = null; 
    setFaqSourcePage(null);
    setForexParams({ pair: null, exp: null });
    setBinaryParams({ pair: null, exp: null });
    setProfileScrollTarget(null);
    setActiveAnalysisPreload(null);
    
    if (user?.mode === 'demo') {
      setCurrentPage('demoHome');
    } else {
      setCurrentPage(user?.mode === 'binary' ? 'signals' : 'analysis');
    }
  };

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg || !tg.BackButton) return;

    const isHome = currentPage === 'signals' || currentPage === 'analysis' || currentPage === 'demoHome' || currentPage === '';

    if (isHome) {
      tg.BackButton.hide();
    } else {
      tg.BackButton.show();
    }

    const handleBackBtnClick = () => {
      if (currentPage === 'faq' && faqSourcePage === 'support') {
        setFaqSourcePage(null);
        setCurrentPage('support');
        return;
      }

      if (activeBackHandler.current) {
        activeBackHandler.current();
      } else {
        handleGoHome();
      }
    };

    tg.onEvent('backButtonClicked', handleBackBtnClick);

    return () => {
      tg.offEvent('backButtonClicked', handleBackBtnClick);
    };
  }, [currentPage, user, faqSourcePage]); 

  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => {
        setToastMessage(null);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [toastMessage]);

  const isDesktop = useMemo(() => {
    const tg = window.Telegram?.WebApp;
    const platform = (tg?.platform || '').toLowerCase();

    return (
      platform === 'tdesktop' ||
      platform === 'web' ||
      platform === 'macos'
    );
  }, []);

  const desktopHeaderHeight = 60;
  const mobileTopSpacing = 16;

  const mainPaddingTop = isDesktop
    ? desktopHeaderHeight + 28
    : Math.max(contentAreaTop + mobileTopSpacing, safeAreaTop + 82);

  
  const bottomPadding = user?.mode === 'demo' ? 140 : 100;

  if (!user) return <Loader t={t} />;

  const handlePageChange = (newPage) => {
    activeBackHandler.current = null; 
    if (newPage !== 'faq') setFaqSourcePage(null);
    if (newPage !== 'profile') {
      setProfileScrollTarget(null);
    }

    if (user.mode === 'demo' && (newPage === 'analysis' || newPage === 'signals')) {
      setCurrentPage('demoHome');
      return;
    }

    setCurrentPage(newPage);
  };

  const handleToggleMode = async (newMode) => {
    if (user.mode === newMode) return;

    setUser({ ...user, mode: newMode });

    let modeName = newMode;
    if (newMode === 'binary') modeName = t.profile.binaryMode;
    if (newMode === 'forex') modeName = t.profile.forexMode;
    if (newMode === 'demo') modeName = "Demonstration";

    setToastMessage(`${t.profile.modeChangedSuccess} ${modeName}`);

    if (user.user_id) {
      try {
        await fetch('/api/user/mode', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: user.user_id, mode: newMode })
        });
      } catch (error) {}
    }
    
    if (newMode === 'demo') setCurrentPage('demoHome');
    else if (newMode === 'binary') setCurrentPage('signals');
    else setCurrentPage('analysis');
  };

  const handleUpdateStrategy = async (strategyId) => {
    if (user.strategy_id === strategyId) return;

    setUser({ ...user, strategy_id: strategyId });
    setToastMessage(t.profile.strategyChangedSuccess);

    try {
      await fetch('/api/user/strategy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.user_id, strategy_id: strategyId })
      });
    } catch (error) {}
  };

  const refreshStrategies = async () => {
    if (!user || !user.user_id) return;

    try {
      const stratRes = await fetch(`/api/strategies?user_id=${user.user_id}`);
      const stratData = await stratRes.json();
      setStrategies(stratData.strategies || []);

      const userRes = await fetch('/api/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.user_id })
      });

      if (userRes.ok) {
        const updatedUser = await userRes.json();
        setUser((prev) => ({ ...prev, strategy_id: updatedUser.strategy_id }));
      }
    } catch (e) {}
  };

  const handleOpenActiveAnalysis = (analysisData) => {
    setActiveAnalysisPreload(analysisData);
    setCurrentPage('forexSettings');
  };

  const setBackHandler = (handler) => {
    activeBackHandler.current = handler;
  };

  const renderContent = () => {
    switch (currentPage) {
      case 'signals':
        if (user.mode === 'demo') return <DemoHome t={t} onStartStudy={() => setCurrentPage('demoSettings')} />;
        return <BinaryHome t={t} onStartSignal={() => setCurrentPage('binarySettings')} />;

      case 'binarySettings':
        return (
          <BinarySignalSettings
            t={t}
            binaryParams={binaryParams}
            setBinaryParams={setBinaryParams}
            onGoHome={handleGoHome}
            setBackHandler={setBackHandler}
            user={user}
            strategies={strategies}
          />
        );

      case 'analysis':
        if (user.mode === 'demo') return <DemoHome t={t} onStartStudy={() => setCurrentPage('demoSettings')} />;
        return (
          <ForexHome
            t={t}
            user={user}
            onStartAnalysis={() => {
              setActiveAnalysisPreload(null);
              setCurrentPage('forexSettings');
            }}
            onOpenActiveAnalysis={handleOpenActiveAnalysis}
          />
        );

      case 'forexSettings':
        return (
          <ForexAnalysisSettings
            user={user}
            strategies={strategies}
            t={t}
            forexParams={forexParams}
            setForexParams={setForexParams}
            onGoHome={handleGoHome}
            onGoProfile={() => {
              setProfileScrollTarget('strategies');
              setCurrentPage('profile');
            }}
            onUpdateStrategy={handleUpdateStrategy}
            activeAnalysisPreload={activeAnalysisPreload}
            setBackHandler={setBackHandler}
          />
        );

      case 'demoHome':
        return <DemoHome t={t} onStartStudy={() => setCurrentPage('demoSettings')} />;

      case 'demoSettings':
        return (
          <DemoAnalysisSettings
            user={user}
            strategies={strategies}
            t={t}
            forexParams={forexParams}
            setForexParams={setForexParams}
            onGoHome={handleGoHome}
            onGoProfile={() => setCurrentPage('profile')}
            onUpdateStrategy={handleUpdateStrategy}
            setBackHandler={setBackHandler}
          />
        );

      case 'profile':
        return (
          <Profile
            user={user}
            onToggleMode={handleToggleMode}
            t={t}
            strategies={strategies}
            onUpdateStrategy={handleUpdateStrategy}
            scrollTarget={profileScrollTarget}
            onRefreshStrategies={refreshStrategies}
            setToastMessage={setToastMessage}
            allIndicators={allIndicators}
            onStartAnalysis={() => {
              if (user.mode === 'demo') setCurrentPage('demoSettings');
              else setCurrentPage(user.mode === 'binary' ? 'binarySettings' : 'forexSettings');
            }}
          />
        );

      case 'history':
        return <History />;

      case 'chatAI':
        return <ChatAI user={user} t={t} />;
        
      case 'faq':
        return <FAQ />;

      case 'support':
        return (
          <Support
            onOpenFaq={() => {
              setFaqSourcePage('support');
              setCurrentPage('faq');
            }}
          />
        );

      case 'logAnalysis':
        return <LogAnalysis user={user} />;

      default:
        if (user.mode === 'demo') {
          return <DemoHome t={t} onStartStudy={() => setCurrentPage('demoSettings')} />;
        }
        return user.mode === 'binary' ? (
          <BinaryHome t={t} onStartSignal={() => setCurrentPage('binarySettings')} />
        ) : (
          <ForexHome
            t={t}
            user={user}
            onStartAnalysis={() => {
              setActiveAnalysisPreload(null);
              setCurrentPage('forexSettings');
            }}
            onOpenActiveAnalysis={handleOpenActiveAnalysis}
          />
        );
    }
  };

  return (
    <div className="app-container">
      <BackgroundCandles />

      <Header
        mode={user.mode}
        activePage={currentPage}
        onPageChange={handlePageChange}
        safeAreaTop={safeAreaTop}
        contentAreaTop={contentAreaTop}
        isDesktop={isDesktop}
      />

      <main
        className="main-content"
        style={{
          paddingTop: `${mainPaddingTop}px`,
          paddingBottom: `calc(${bottomPadding}px + env(safe-area-inset-bottom))`
        }}
      >
        {renderContent()}
      </main>

      {toastMessage && <div className="toast-notification">{toastMessage}</div>}
    </div>
  );
}

export default App;
