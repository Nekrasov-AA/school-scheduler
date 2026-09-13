import React, { useEffect, useState } from 'react';

interface BackendHealth {
  status: string;
}

export const App: React.FC = () => {
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || '';
    fetch(`${apiUrl}/api/health`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then((data: BackendHealth) => {
        setHealth(data);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div>
      <h1>School Scheduler</h1>
      <h2>Backend Health Check</h2>
      {loading && <p>Checking backend connection...</p>}
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {health && (
        <p>
          Backend Status: <strong>{health.status}</strong>
        </p>
      )}
    </div>
  );
};

export default App;
