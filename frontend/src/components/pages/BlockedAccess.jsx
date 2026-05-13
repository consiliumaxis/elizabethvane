export default function BlockedAccess() {
  return (
    <div className="open-via-bot-page">
      <div className="open-via-bot-card">
        <span className="open-via-bot-badge">Access restricted</span>
        <h1 className="open-via-bot-title">Application unavailable</h1>
        <p className="open-via-bot-text">
          At the moment, you cannot launch this application.
        </p>
        <p className="open-via-bot-note">
          Please contact support if you believe this is a mistake.
        </p>
      </div>
    </div>
  );
}
