import { useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';

export default function BroadcastPage() {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleSend = async () => {
    const message = text.trim();
    if (!message) return;

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const res = await apiAdminFetchJson('/api/admin/broadcast', {
        method: 'POST',
        body: JSON.stringify({ text: message }),
      });
      setResult(res.result || null);
      setText('');
    } catch (e) {
      setError(e.message || 'Не удалось отправить рассылку');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="admin-card">
      <h3 className="admin-section-title">Рассылка</h3>
      <textarea
        className="admin-textarea"
        rows={8}
        placeholder="Напишите сообщение для всех пользователей..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="admin-row-between">
        <div className="admin-muted">Сообщение отправится всем пользователям из таблицы users.</div>
        <button className="admin-btn" onClick={handleSend} disabled={loading || !text.trim()}>
          {loading ? 'Отправка...' : 'Запустить рассылку'}
        </button>
      </div>

      {error ? <div className="admin-error">{error}</div> : null}
      {result ? (
        <div className="admin-result">
          <div>Всего: <strong>{result.total}</strong></div>
          <div>Отправлено: <strong>{result.sent}</strong></div>
          <div>Ошибок: <strong>{result.failed}</strong></div>
        </div>
      ) : null}
    </div>
  );
}
