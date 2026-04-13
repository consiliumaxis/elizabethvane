import React from 'react';

export default function OpenViaBot({ botUsername }) {
  const botLink = botUsername ? `https://t.me/${botUsername}` : 'https://t.me';

  return (
    <div className="open-via-bot-page">
      <div className="open-via-bot-card">
        <div className="open-via-bot-badge">Telegram Web App</div>
        <h1 className="open-via-bot-title">Open the app via our bot</h1>
        <p className="open-via-bot-text">
          For secure authorization and proper operation, this application must be launched only inside Telegram.
        </p>
        <a className="open-via-bot-button" href={botLink} target="_blank" rel="noreferrer">
          Open bot
        </a>
        {botUsername ? <div className="open-via-bot-note">@{botUsername}</div> : null}
      </div>
    </div>
  );
}
