
import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Rule {
  pattern: string;
  type: string;
  action: string;
  description: string;
  port?: number;
}

const Rules = () => {
  const [rules, setRules] = useState<Rule[]>([]);
  const [lastLoaded, setLastLoaded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testUrl, setTestUrl] = useState('');
  const [testResult, setTestResult] = useState<any>(null);

  const fetchRules = async () => {
    try {
      const response = await axios.get('/rules');
      setRules(response.data.rules);
      setLastLoaded(response.data.last_loaded_at);
    } catch (err) {
      setError('Failed to fetch rules.');
      console.error(err);
    }
  };

  useEffect(() => {
    fetchRules();
    const intervalId = setInterval(fetchRules, 15000); // Fetch data every 15 seconds

    return () => clearInterval(intervalId); // Cleanup interval on component unmount
  }, []);

  const handleReload = async () => {
    try {
      await axios.post('/rules/reload');
      fetchRules();
    } catch (err) {
      setError('Failed to reload rules.');
      console.error(err);
    }
  };

  const handleTest = async () => {
    try {
      const response = await axios.post('/rules/test', { url: testUrl });
      setTestResult(response.data);
    } catch (err) {
      setError('Failed to test rule.');
      console.error(err);
    }
  };

  if (error) {
    return <div className="alert alert-danger">{error}</div>;
  }

  return (
    <div>
      <h1>Rules</h1>
      <div className="d-flex justify-content-between mb-3">
        <span>Last Loaded: {lastLoaded ? new Date(lastLoaded).toLocaleString() : 'Never'}</span>
        <button className="btn btn-primary" onClick={handleReload}>Reload Rules</button>
      </div>
      <table className="table table-striped">
        <thead>
          <tr>
            <th>Pattern</th>
            <th>Type</th>
            <th>Action</th>
            <th>Description</th>
            <th>Port</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule, index) => (
            <tr key={index}>
              <td>{rule.pattern}</td>
              <td>{rule.type}</td>
              <td>{rule.action}</td>
              <td>{rule.description}</td>
              <td>{rule.port}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-4">
        <h2>Test Rule</h2>
        <div className="input-group mb-3">
          <input type="text" className="form-control" placeholder="Enter URL to test" value={testUrl} onChange={(e) => setTestUrl(e.target.value)} />
          <button className="btn btn-outline-secondary" type="button" onClick={handleTest}>Test</button>
        </div>
        {testResult && (
          <div className={`alert ${testResult.matched ? 'alert-warning' : 'alert-success'}`}>
            {testResult.matched ? `Matched rule: ${testResult.rule.description}` : 'No rule matched.'}
          </div>
        )}
      </div>
    </div>
  );
};

export default Rules;
