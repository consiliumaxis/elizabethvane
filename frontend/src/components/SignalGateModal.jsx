import React, { useEffect, useState } from 'react';
import { apiFetchJson } from '../lib/api';

export default function SignalGateModal({ onClose }) {
  const [links, setLinks] = useState({
    channel_url: '',
    support_url: ''
  });

  useEffect(() => {
    let isActive = true;

    apiFetchJson('/api/support/links')
      .then((data) => {
        if (!isActive) return;
        setLinks({
          channel_url: data?.channel_url || '',
          support_url: data?.support_url || ''
        });
      })
      .catch(() => {});

    return () => {
      isActive = false;
    };
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
    <div className="signal-gate-overlay" onClick={onClose}>
      <div className="signal-gate-modal" onClick={(event) => event.stopPropagation()}>
        <div className="signal-gate-badge">Access required</div>
        <h3>Full signal access is not enabled yet</h3>
        <p>
          Unfortunately, your account does not have full access to trading signals at the moment.
        </p>
        <p className="signal-gate-note">
          You can open our channel for updates or message our manager to get access.
        </p>

        <div className="signal-gate-actions">
          <button
            className="signal-gate-primary"
            type="button"
            onClick={() => openExternalLink(links.channel_url)}
            disabled={!links.channel_url}
          >
            Open Channel
          </button>
          <button
            className="signal-gate-secondary"
            type="button"
            onClick={() => openExternalLink(links.support_url)}
            disabled={!links.support_url}
          >
            Message Manager
          </button>
        </div>

        <button className="signal-gate-close" type="button" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
