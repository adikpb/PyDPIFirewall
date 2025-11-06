
import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Log {
  id: number;
  url: string;
  blocked: boolean;
  timestamp: string;
  headers: string;
  body: string;
  matched_rule: string;
}

const Logs = () => {
  const [logs, setLogs] = useState<Log[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [blocked, setBlocked] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const params = { page, page_size: pageSize, blocked: blocked === null ? undefined : blocked };
        const response = await axios.get('/logs', { params });
        setLogs(response.data.items);
        setTotal(response.data.total);
      } catch (err) {
        setError('Failed to fetch logs.');
        console.error(err);
      }
    };

    fetchLogs();
    const intervalId = setInterval(fetchLogs, 5000); // Fetch data every 5 seconds

    return () => clearInterval(intervalId); // Cleanup interval on component unmount
  }, [page, pageSize, blocked]);

  const handlePurge = async () => {
    if (window.confirm('Are you sure you want to delete all logs?')) {
      try {
        await axios.delete('/logs');
        setPage(1);
        // Refetch logs
        const params = { page: 1, page_size: pageSize, blocked: blocked === null ? undefined : blocked };
        const response = await axios.get('/logs', { params });
        setLogs(response.data.items);
        setTotal(response.data.total);
      } catch (err) {
        setError('Failed to delete logs.');
        console.error(err);
      }
    }
  };

  if (error) {
    return <div className="alert alert-danger">{error}</div>;
  }

  return (
    <div>
      <h1>Logs</h1>
      <div className="d-flex justify-content-between mb-3">
        <div>
          <button className="btn btn-danger" onClick={handlePurge}>Purge All Logs</button>
        </div>
        <div className="btn-group">
          <button className={`btn ${blocked === null ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setBlocked(null)}>All</button>
          <button className={`btn ${blocked === true ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setBlocked(true)}>Blocked</button>
          <button className={`btn ${blocked === false ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setBlocked(false)}>Allowed</button>
        </div>
      </div>
      <table className="table table-striped">
        <thead>
          <tr>
            <th>ID</th>
            <th>Timestamp</th>
            <th>URL</th>
            <th>Blocked</th>
            <th>Matched Rule</th>
          </tr>
        </thead>
        <tbody>
          {logs.map(log => (
            <tr key={log.id}>
              <td>{log.id}</td>
              <td>{new Date(log.timestamp).toLocaleString()}</td>
              <td>{log.url}</td>
              <td>{log.blocked ? 'Yes' : 'No'}</td>
              <td>{log.matched_rule}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="d-flex justify-content-between">
        <span>Total: {total}</span>
        <nav>
          <ul className="pagination">
            <li className={`page-item ${page === 1 ? 'disabled' : ''}`}>
              <button className="page-link" onClick={() => setPage(page - 1)}>Previous</button>
            </li>
            <li className={`page-item ${logs.length < pageSize ? 'disabled' : ''}`}>
              <button className="page-link" onClick={() => setPage(page + 1)}>Next</button>
            </li>
          </ul>
        </nav>
      </div>
    </div>
  );
};

export default Logs;
