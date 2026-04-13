import React, { useEffect, useState } from 'react';
import Lottie from 'lottie-react';
import './Support.css';
import { texts } from '../../locales/texts';
import supportLottie from '../../assets/support-lottie.json';
import { apiFetchJson } from '../../lib/api';

export default function Support({ onOpenFaq }) {
  const t = texts.en.supportPage;

  const [links, setLinks] = useState({
    channel_url: '',
    support_url: ''
  });

  useEffect(() => {
    const loadLinks = async () => {
      try {
        const data = await apiFetchJson('/api/support/links');
        setLinks({
          channel_url: data?.channel_url || '',
          support_url: data?.support_url || ''
        });
      } catch (error) {}
    };

    loadLinks();
  }, []);

  const openExternalLink = (url) => {
    if (!url) return;

    const tg = window.Telegram?.WebApp;

    try {
      if (tg?.openTelegramLink && url.includes('t.me/')) {
        tg.openTelegramLink(url);
        return;
      }

      if (tg?.openLink) {
        tg.openLink(url);
        return;
      }
    } catch (error) {}

    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="support-page">
      <h2 className="support-title">{t.title}</h2>

      <section className="support-hero">
        <Lottie animationData={supportLottie} loop={true} className="support-hero-lottie" />
      </section>

      <section className="support-quick">
        <h3 className="support-panel-title">{t.quickTitle}</h3>
        <p className="support-text">{t.quickText}</p>

        <div className="support-actions support-actions-double">
          <button
            type="button"
            className="support-btn support-btn-faq"
            onClick={() => typeof onOpenFaq === 'function' && onOpenFaq()}
          >
            {t.openFaq}
          </button>

          <button
            type="button"
            className="support-btn support-btn-channel"
            onClick={() => openExternalLink(links.channel_url)}
            disabled={!links.channel_url}
          >
            {t.openChannel}
          </button>
        </div>
      </section>

      <section className="support-panel support-panel-contact">
        <h3 className="support-panel-title">{t.contactTitle}</h3>
        <p className="support-text">{t.contactText}</p>

        <div className="support-actions">
          <button
            type="button"
            className="support-btn support-btn-support"
            onClick={() => openExternalLink(links.support_url)}
            disabled={!links.support_url}
          >
            {t.writeSupport}
          </button>
        </div>
      </section>

      {(!links.channel_url || !links.support_url) && (
        <p className="support-hint">{t.envHint}</p>
      )}
    </div>
  );
}
