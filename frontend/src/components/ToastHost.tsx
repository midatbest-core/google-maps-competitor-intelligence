import { useEffect, useState } from 'react';

interface ToastMessage {
  id: number;
  text: string;
}

const ToastHost = () => {
  const [messages, setMessages] = useState<ToastMessage[]>([]);

  useEffect(() => {
    let nextId = 0;
    const handleError = (event: Event) => {
      const text = (event as CustomEvent<string>).detail;
      if (!text) return;
      const id = ++nextId;
      setMessages((current) => [...current.slice(-2), { id, text }]);
      window.setTimeout(() => {
        setMessages((current) => current.filter((message) => message.id !== id));
      }, 6000);
    };
    window.addEventListener('app:error', handleError);
    return () => window.removeEventListener('app:error', handleError);
  }, []);

  return (
    <div className="toast-stack" aria-live="assertive" aria-atomic="false">
      {messages.map((message) => (
        <div className="toast-error" role="alert" key={message.id}>
          <span>{message.text}</span>
          <button
            type="button"
            aria-label="Dismiss error"
            onClick={() => setMessages((current) => current.filter((item) => item.id !== message.id))}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
};

export default ToastHost;
