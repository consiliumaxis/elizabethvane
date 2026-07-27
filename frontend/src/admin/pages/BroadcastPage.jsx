import { useState } from 'react';
import { apiAdminFetchJson } from '../../lib/api';
import { useAdminLocale } from '../useAdminLocale';

export default function BroadcastPage() {
  const { tr } = useAdminLocale();
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
      setError(e.message || tr('Could not send the broadcast', 'Не удалось отправить рассылку'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="admin-card">
      <h3 className="admin-section-title">{tr('Broadcast', 'Рассылка')}</h3>
      <textarea
        className="admin-textarea"
        rows={8}
        placeholder={tr('Write a message for all users…', 'Напишите сообщение для всех пользователей...')}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="admin-row-between">
        <div className="admin-muted">
          {tr('The message will be sent to every user in the users table.', 'Сообщение отправится всем пользователям из таблицы users.')}
        </div>
        <button className="admin-btn" onClick={handleSend} disabled={loading || !text.trim()}>
          {loading ? tr('Sending…', 'Отправка...') : tr('Send broadcast', 'Запустить рассылку')}
        </button>
      </div>

      {error ? <div className="admin-error">{error}</div> : null}
      {result ? (
        <div className="admin-result">
          <div>{tr('Total', 'Всего')}: <strong>{result.total}</strong></div>
          <div>{tr('Sent', 'Отправлено')}: <strong>{result.sent}</strong></div>
          <div>{tr('Failed', 'Ошибок')}: <strong>{result.failed}</strong></div>
        </div>
      ) : null}
    </div>
  );
}
