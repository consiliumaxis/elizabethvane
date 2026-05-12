import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import './Header.css';
import { texts } from '../../locales/texts';

import iconProfile from '../../assets/icons/profile.svg?url';
import iconSignals from '../../assets/icons/signals.svg?url';
import iconHistory from '../../assets/icons/history.svg?url';
import iconChatAI from '../../assets/icons/chat.svg?url';
import iconFAQ from '../../assets/icons/faq.svg?url';
import iconSupport from '../../assets/icons/support.svg?url';
import iconAnalysis from '../../assets/icons/analysis.svg?url';
import iconLog from '../../assets/icons/log.svg?url';

export default function Header({
  mode,
  activePage,
  onPageChange,
  safeAreaTop = 0,
  contentAreaTop = 55,
  isDesktop = false
}) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const bottomBarRef = useRef(null);
  const t = texts.en;

  const toggleMenu = () => setIsMenuOpen((prev) => !prev);
  const closeMenu = () => setIsMenuOpen(false);

  const handleMenuItemClick = (id) => {
    onPageChange(id);
    closeMenu();
  };

  const binaryMenu = useMemo(
    () => [
      { id: 'signals', label: t.menu.signals, icon: iconSignals },
      { id: 'profile', label: t.menu.profile, icon: iconProfile },
      { id: 'history', label: t.menu.history, icon: iconHistory },
      { id: 'chatAI', label: t.menu.chatAI, icon: iconChatAI },
      { id: 'faq', label: t.menu.faq, icon: iconFAQ },
      { id: 'support', label: t.menu.support, icon: iconSupport }
    ],
    [t.menu]
  );

  const forexMenu = useMemo(
    () => [
      { id: 'analysis', label: t.menu.analysis, icon: iconAnalysis },
      { id: 'profile', label: t.menu.profile, icon: iconProfile },
      { id: 'logAnalysis', label: t.menu.logAnalysis, icon: iconLog },
      { id: 'faq', label: t.menu.faq, icon: iconFAQ },
      { id: 'chatAI', label: t.menu.chatAI, icon: iconChatAI },
      { id: 'support', label: t.menu.support, icon: iconSupport }
    ],
    [t.menu]
  );

  const currentMenu = mode === 'binary' ? binaryMenu : forexMenu;
  const currentDisclaimer = mode === 'binary' ? t.binaryAnalytics.disclaimer : t.forexAnalytics.disclaimer;

  const mobileBandTop = safeAreaTop;
  const mobileBandBottom = contentAreaTop > safeAreaTop ? contentAreaTop : safeAreaTop + 54;
  const mobileBandHeight = Math.max(mobileBandBottom - mobileBandTop, 54);
  const mobileButtonHeight = 42;
  const mobileButtonTop = Math.round(mobileBandTop + (mobileBandHeight - mobileButtonHeight) / 2) - 4;

  const desktopHeaderHeight = 64;
  const desktopButtonTop = 11;

  const headerTop = isDesktop ? 0 : mobileButtonTop;
  const headerHeight = isDesktop ? desktopHeaderHeight : mobileButtonHeight;

  const dropdownTop = isDesktop
    ? desktopHeaderHeight + 10
    : Math.max(contentAreaTop + 16, mobileButtonTop + mobileButtonHeight + 12);

  useEffect(() => {
    const root = document.documentElement;

    const updateBottomOverlay = () => {
      if (!bottomBarRef.current) return;

      const rect = bottomBarRef.current.getBoundingClientRect();
      const viewportHeight = window.visualViewport?.height || window.innerHeight;
      const overlayHeight = Math.max(0, viewportHeight - rect.top);

      root.style.setProperty('--app-bottom-overlay-height', `${Math.ceil(overlayHeight)}px`);
    };

    updateBottomOverlay();

    const observer = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(updateBottomOverlay)
      : null;

    if (observer && bottomBarRef.current) {
      observer.observe(bottomBarRef.current);
    }

    window.addEventListener('resize', updateBottomOverlay);
    window.visualViewport?.addEventListener('resize', updateBottomOverlay);
    window.visualViewport?.addEventListener('scroll', updateBottomOverlay);

    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', updateBottomOverlay);
      window.visualViewport?.removeEventListener('resize', updateBottomOverlay);
      window.visualViewport?.removeEventListener('scroll', updateBottomOverlay);
    };
  }, []);

  return (
    <>
      {isDesktop && <div className="tg-desktop-header-fill"></div>}

      <div
        className={`tg-header-center-slot ${isDesktop ? 'desktop' : 'mobile'}`}
        style={{
          top: `${headerTop}px`,
          height: `${headerHeight}px`
        }}
      >
        <button
          type="button"
          className={`tg-native-menu-pill ${isMenuOpen ? 'open' : ''}`}
          onClick={toggleMenu}
          aria-expanded={isMenuOpen}
          aria-label={t.menuBtn}
        >
          <span className="tg-native-menu-icon">☰</span>
          <span className="tg-native-menu-label">{t.menuBtn}</span>
        </button>
      </div>

      <div className="premium-bottom-bar" ref={bottomBarRef}>
        <div className="micro-disclaimer">
          {mode === 'demo' && (
            <div className="demo-watermark-global">
              {t.demoSettings?.watermark || 'DEMONSTRATION MODE'}
            </div>
          )}
          <p className="micro-disclaimer-text">{currentDisclaimer}</p>
        </div>
      </div>

      {isMenuOpen && (
        <>
          {createPortal(<div className="menu-backdrop" onClick={closeMenu}></div>, document.body)}

          <div className="telegram-dropdown telegram-dropdown-centered" style={{ top: `${dropdownTop}px` }}>
            <nav className="t-menu-nav">
              {currentMenu.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className={`t-menu-item ${activePage === item.id ? 'active' : ''}`}
                  onClick={() => handleMenuItemClick(item.id)}
                >
                  <span
                    className="t-menu-icon"
                    style={{
                      maskImage: `url("${item.icon}")`,
                      WebkitMaskImage: `url("${item.icon}")`,
                      backgroundColor: activePage === item.id ? '#D4AF37' : '#8f98a4'
                    }}
                  ></span>
                  <span className="t-menu-text">{item.label}</span>
                </button>
              ))}
            </nav>

            <div className="t-language-section">
              <span className="t-lang-label">{t.languageLabel}</span>
              <div className="t-lang-buttons">
                <button type="button" className="t-lang-btn active">
                  {t.langEn}
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
