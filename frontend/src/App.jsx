import { useEffect, useMemo, useState, useRef } from 'react';
import { initTelegramApp } from './lib/tgSetup';
import { apiFetchJson, apiAdminFetchJson, isAdminRoute, isTelegramWebAppAvailable } from './lib/api';

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
import OpenViaBot from './components/pages/OpenViaBot';
import AdminApp from './admin/AdminApp';

import Header from './components/Header/Header.jsx';
import BackgroundCandles from './components/BackgroundCandles/BackgroundCandles.jsx';
import { texts } from './locales/texts';
import './theme.css';
import './openViaBot.css';

function App() {
  const [user, setUser] = useState(null);
  const [isTgWebApp, setIsTgWebApp] = useState(true);
  const [botUsername, setBotUsername] = useState('');
  const [currentPage, setCurrentPage] = useState('');
  const [toastMessage, setToastMessage] = useState(null);
  const [strategies, setStrategies] = useState([]);
  const [allIndicators, setAllIndicators] = useState([]);
  const [adminInitDone, setAdminInitDone] = useState(false);
  const [adminAuthError, setAdminAuthError] = useState('');
  const [adminUser, setAdminUser] = useState(null);

  const [forexParams, setForexParams] = useState({ pair: null, exp: null });
  const [binaryParams, setBinaryParams] = useState({ pair: null, exp: null });
  const [profileScrollTarget, setProfileScrollTarget] = useState(null);

  const [activeAnalysisPreload, setActiveAnalysisPreload] = useState(null);

  const [safeAreaTop, setSafeAreaTop] = useState(0);
  const [contentAreaTop, setContentAreaTop] = useState(55);

  const activeBackHandler = useRef(null); 

  const t = texts.en;
  const adminMode = useMemo(() => isAdminRoute(), []);

  useEffect(() => {
    const syncUser = async () => {
      const available = isTelegramWebAppAvailable();
      if (!available) {
        setIsTgWebApp(false);
        try {
          const info = await apiFetchJson('/api/webapp/bot-info');
          setBotUsername(info?.bot_username || '');
        } catch (error) {
          setBotUsername('');
        }
        return;
      }

      try {
        const tg = await initTelegramApp();
        if (!tg) return;

        setIsTgWebApp(true);

        if (adminMode) {
          try {
            const me = await apiAdminFetchJson('/api/admin/me');
            setAdminUser(me?.user || null);
            setAdminAuthError('');
          } catch (error) {
            setAdminUser(null);
            setAdminAuthError(error.message || 'Admin auth failed');
          } finally {
            setAdminInitDone(true);
          }
          return;
        }

        await apiFetchJson('/api/user/sync', {
          method: 'POST',
        });

        const [userData, stratData, indData] = await Promise.all([
          apiFetchJson('/api/user/profile', {
            method: 'POST',
          }),
          apiFetchJson('/api/strategies'),
          apiFetchJson('/api/indicators')
        ]);

        setAllIndicators(indData.indicators || []);
        setStrategies(stratData.strategies || []);
        setUser(userData);
        
        if (userData.mode === 'demo') {
          setCurrentPage('demoHome');
        } else {
          setCurrentPage(userData.mode === 'binary' ? 'signals' : 'analysis');
        }
      } catch (error) {
        if (adminMode) {
          setAdminAuthError(error.message || 'Admin init failed');
          setAdminInitDone(true);
        } else {
          const fallbackUser = { mode: 'binary', strategy_id: 1, lang: 'en' };
          setUser(fallbackUser);
          setCurrentPage('signals');
        }
      }
    };

    syncUser();
  }, [adminMode]);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg?.expand) tg.expand();

    const updateSafeArea = () => {
      const docStyle = window.getComputedStyle(document.documentElement);
      const cssSafeTop = parseFloat(docStyle.getPropertyValue('--tg-safe-area-inset-top')) || 0;
      const cssContentTop = parseFloat(docStyle.getPropertyValue('--tg-content-safe-area-inset-top')) || 0;

      const platform = (tg?.platform || '').toLowerCase();

      const isDesktopPlatform =
        platform === 'tdesktop' ||
        platform === 'web' ||
        platform === 'macos';

      let sTop = Number(tg?.safeAreaInset?.top ?? cssSafeTop ?? 0);
      let cTop = Number(tg?.contentSafeAreaInset?.top ?? cssContentTop ?? 0);

      if (isDesktopPlatform) {
        if (!sTop) sTop = 0;
        if (!cTop) cTop = 0;
      } else {
        if (!cTop || cTop <= sTop) {
          cTop = Math.max(sTop + 56, 60);
        }
      }

      setSafeAreaTop(sTop);
      setContentAreaTop(cTop);
    };

    if (typeof tg?.requestSafeArea === 'function') tg.requestSafeArea();
    if (typeof tg?.requestContentSafeArea === 'function') tg.requestContentSafeArea();

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

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, [currentPage]);

  const handleGoHome = () => {
    activeBackHandler.current = null; 
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
  }, [currentPage, user]); 

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

  const mainPaddingTop = isDesktop
    ? 106
    : Math.max(contentAreaTop + 56, safeAreaTop + 98);

  const isChatPage = currentPage === 'chatAI';
  const bottomPadding = isChatPage ? 86 : 106;

  if (!isTgWebApp) return <OpenViaBot botUsername={botUsername} />;
  if (adminMode) {
    if (!adminInitDone) return <Loader t={t} />;
    return <AdminApp adminUser={adminUser} authError={adminAuthError} />;
  }
  if (!user) return <Loader t={t} />;

  const handlePageChange = (newPage) => {
    activeBackHandler.current = null; 
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

    if (user) {
      try {
        await apiFetchJson('/api/user/mode', {
          method: 'POST',
          body: JSON.stringify({ mode: newMode })
        });
      } catch (error) {}
    }

    if (currentPage !== 'profile') {
      if (newMode === 'demo') setCurrentPage('demoHome');
      else if (newMode === 'binary') setCurrentPage('signals');
      else setCurrentPage('analysis');
    }
  };

  const handleUpdateStrategy = async (strategyId) => {
    if (user.strategy_id === strategyId) return;

    setUser({ ...user, strategy_id: strategyId });
    setToastMessage(t.profile.strategyChangedSuccess);

    try {
      await apiFetchJson('/api/user/strategy', {
        method: 'POST',
        body: JSON.stringify({ strategy_id: strategyId })
      });
    } catch (error) {}
  };

  const refreshStrategies = async () => {
    if (!user) return;

    try {
      const stratData = await apiFetchJson('/api/strategies');
      setStrategies(stratData.strategies || []);

      const updatedUser = await apiFetchJson('/api/user/profile', {
        method: 'POST',
      });
      setUser((prev) => ({ ...prev, strategy_id: updatedUser.strategy_id }));
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
        return <Support />;

      case 'logAnalysis':
        return <LogAnalysis user={user} t={t} strategies={strategies} />;

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
    <div className="app-container" style={{ '--app-main-top': `${mainPaddingTop}px` }}>
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






