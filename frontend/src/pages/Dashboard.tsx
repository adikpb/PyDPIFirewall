
import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Metrics {
  total_requests: number;
  blocked_requests: number;
}

interface Status {
  fastapi_port: number;
  mitmproxy_port: number;
  proxy_running: boolean;
  rules_count: number;
  db_path: string;
  log_level: string;
  uptime_sec: number;
}

const Dashboard = () => {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const metricsResponse = await axios.get('/metrics');
        setMetrics(metricsResponse.data);

        const statusResponse = await axios.get('/status');
        setStatus(statusResponse.data);
      } catch (err) {
        setError('Failed to fetch data from the backend. Please ensure the backend is running.');
        console.error(err);
      }
    };

    fetchData();
    const intervalId = setInterval(fetchData, 5000); // Fetch data every 5 seconds

    return () => clearInterval(intervalId); // Cleanup interval on component unmount
  }, []);

  if (error) {
    return <div className="alert alert-danger">{error}</div>;
  }

  if (!metrics || !status) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <h1>Dashboard</h1>
      
      <div className="row">
        <div className="col-md-6">
          <div className="card">
            <div className="card-header">Metrics</div>
            <div className="card-body">
              <p>Total Requests: {metrics.total_requests}</p>
              <p>Blocked Requests: {metrics.blocked_requests}</p>
            </div>
          </div>
        </div>
        <div className="col-md-6">
          <div className="card">
            <div className="card-header">Status</div>
            <div className="card-body">
              <p>Proxy Running: {status.proxy_running ? 'Yes' : 'No'}</p>
              <p>Rules Count: {status.rules_count}</p>
              <p>Uptime (seconds): {status.uptime_sec}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
