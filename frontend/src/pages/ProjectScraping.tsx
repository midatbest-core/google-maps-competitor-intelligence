import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { getScrapeRuns, startScrape, getScrapeRun, resumeScrapeRun } from '../api';
import type { ScrapeRun, ScrapeRunCompetitor } from '../api';
import './ProjectScraping.css';

const STATUS_LABELS: Record<string, string> = {
  QUEUED: 'Queued',
  RUNNING: 'Running',
  RETRYING: 'Retrying',
  PAUSED_MANUAL_INTERVENTION: 'Manual Intervention Required',
  PARTIAL_SUCCESS: 'Partial Success',
  SUCCESS: 'Success',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
  PENDING: 'Pending',
  NO_DATA: 'No Data',
  VERIFICATION_REQUIRED: 'Verification Required',
  ERROR: 'Error'
};

const ProjectScraping: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  
  const [runs, setRuns] = useState<ScrapeRun[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [activeRunDetails, setActiveRunDetails] = useState<ScrapeRun | null>(null);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [resuming, setResuming] = useState(false);
  
  const pollTimerRef = useRef<number | null>(null);


  const fetchRuns = async () => {
    try {
      const runsRes = await getScrapeRuns(projectId!);
      
      const sortedRuns = runsRes.data.sort((a, b) => {
        if (a.start_time && b.start_time) {
          return new Date(b.start_time).getTime() - new Date(a.start_time).getTime();
        }
        return b.id.localeCompare(a.id);
      });
      setRuns(sortedRuns);
      
      const active = sortedRuns.find(r => ['QUEUED', 'RUNNING', 'RETRYING', 'PAUSED_MANUAL_INTERVENTION'].includes(r.status));
      if (active) {
        if (!activeRunId) {
          setActiveRunId(active.id);
        }
      } else if (!activeRunId && sortedRuns.length > 0) {
        setActiveRunId(sortedRuns[0].id);
      }
    } catch (err: any) {
      console.error(err);
      setError('Failed to load scrape runs');
    } finally {
      setLoading(false);
    }
  };


  const fetchActiveRunDetails = async () => {
    if (!activeRunId) return;
    try {
      const res = await getScrapeRun(activeRunId);
      setActiveRunDetails(res.data);
      
      // Stop polling if run is completed
      if (['SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'CANCELLED'].includes(res.data.status)) {
        stopPolling();
      } else if (res.data.status === 'PAUSED_MANUAL_INTERVENTION') {
        // We can slow down polling or stop, let's stop for now to prevent spam
        stopPolling();
      }
    } catch (err) {
      console.error('Failed to load run details', err);
    }
  };

  const startPolling = () => {
    if (pollTimerRef.current) return;
    pollTimerRef.current = window.setInterval(() => {
      fetchActiveRunDetails();
      fetchRuns();
    }, 4000);
  };

  const stopPolling = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  useEffect(() => {
    if (projectId) {
      fetchRuns();
    }
    return () => stopPolling();
  }, [projectId]);

  useEffect(() => {
    if (activeRunId) {
      fetchActiveRunDetails();
      
      // If we select a run that is active, start polling
      const run = runs.find(r => r.id === activeRunId);
      if (run && ['QUEUED', 'RUNNING', 'RETRYING'].includes(run.status)) {
        startPolling();
      } else {
        stopPolling();
      }
    }
  }, [activeRunId]);

  const handleStartScrape = async () => {
    if (!projectId) return;
    setStarting(true);
    setError(null);
    try {
      const res = await startScrape(projectId);
      await fetchRuns();
      setActiveRunId(res.data.id);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to start scrape');
    } finally {
      setStarting(false);
    }
  };

  const handleResumeRun = async () => {
    if (!activeRunId) return;
    setResuming(true);
    setError(null);
    try {
      await resumeScrapeRun(activeRunId);
      await fetchActiveRunDetails();
      await fetchRuns();
      startPolling();
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to resume run');
    } finally {
      setResuming(false);
    }
  };

  const renderStatusBadge = (status: string) => {
    const s = status.toUpperCase();
    let badgeClass = 'status-default';
    if (['SUCCESS'].includes(s)) badgeClass = 'status-success';
    if (['FAILED', 'ERROR', 'CANCELLED'].includes(s)) badgeClass = 'status-error';
    if (['RUNNING', 'RETRYING'].includes(s)) badgeClass = 'status-running';
    if (['QUEUED', 'PENDING'].includes(s)) badgeClass = 'status-warning';
    if (['PARTIAL_SUCCESS'].includes(s)) badgeClass = 'status-partial';
    if (['PAUSED_MANUAL_INTERVENTION', 'VERIFICATION_REQUIRED'].includes(s)) badgeClass = 'status-manual';
    
    return <span className={`status-badge ${badgeClass}`}>{STATUS_LABELS[status] || status}</span>;
  };

  if (loading) {
    return (
      <AppLayout projectId={projectId}>
        <div className="scraping-page loading-state">
          <p>Loading scrape runs...</p>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout projectId={projectId}>
      <div className="scraping-page">
        <header className="page-header">
          <div>
            <h1>Scraping</h1>
            <p>Monitor and manage competitor data collection.</p>
          </div>
          <button 
            className="btn-primary" 
            onClick={handleStartScrape}
            disabled={starting || !!(activeRunDetails && ['QUEUED', 'RUNNING', 'RETRYING'].includes(activeRunDetails.status))}
          >
            {starting ? 'Starting...' : 'Start New Scrape'}
          </button>
        </header>

        {error && <div className="error-message">{error}</div>}

        <div className="scraping-content">
          <div className="scraping-sidebar">


            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1rem' }}>Recent Runs</h3>
            {runs.length === 0 ? (
              <p className="empty-text">No scrape runs yet.</p>
            ) : (
              <div className="run-list">
                {runs.map(run => (
                  <div 
                    key={run.id} 
                    className={`run-list-item ${activeRunId === run.id ? 'active' : ''}`}
                    onClick={() => setActiveRunId(run.id)}
                  >
                    <div className="run-list-header">
                      <span className="run-id">{run.id.split('-')[0]}</span>
                      {renderStatusBadge(run.status)}
                    </div>
                    <div className="run-list-meta">
                      {run.start_time ? new Date(run.start_time).toLocaleString() : 'Not started'}
                    </div>
                    <div className="run-list-stats">
                      {run.competitors_succeeded} / {run.competitors_attempted} succeeded
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="scraping-main">
            {activeRunDetails ? (
              <div className="run-details-panel">
                <div className="run-details-header">
                  <h2>Run {activeRunDetails.id}</h2>
                  {renderStatusBadge(activeRunDetails.status)}
                </div>

                {activeRunDetails.status === 'PAUSED_MANUAL_INTERVENTION' && (
                  <div className="manual-intervention-alert">
                    <h4>Manual verification required</h4>
                    <p>The scraper has paused because manual verification is required. Complete verification in the configured browser/session, then resume the run.</p>
                    <button className="btn-warning" onClick={handleResumeRun} disabled={resuming}>
                      {resuming ? 'Resuming...' : 'Resume Run'}
                    </button>
                  </div>
                )}

                <div className="stats-grid">
                  <div className="stat-card">
                    <span className="stat-label">Total Attempted</span>
                    <span className="stat-value">{activeRunDetails.competitors_attempted}</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Succeeded</span>
                    <span className="stat-value text-success">{activeRunDetails.competitors_succeeded}</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Failed</span>
                    <span className="stat-value text-error">{activeRunDetails.competitors_failed}</span>
                  </div>
                  <div className="stat-card">
                    <span className="stat-label">Started</span>
                    <span className="stat-value small-text">
                      {activeRunDetails.start_time ? new Date(activeRunDetails.start_time).toLocaleString() : 'N/A'}
                    </span>
                  </div>
                </div>

                <div className="competitors-section">
                  <h3>Competitor Results</h3>
                  {(!activeRunDetails.competitor_runs || activeRunDetails.competitor_runs.length === 0) ? (
                    <p className="empty-text">No competitor details available.</p>
                  ) : (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Business</th>
                          <th>Status</th>
                          <th>New Posts</th>
                          <th>Total Found</th>
                          <th>Error</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activeRunDetails.competitor_runs.map((cr: ScrapeRunCompetitor) => (
                          <tr key={cr.id}>
                            <td>{cr.business?.business_name || 'Unknown Business'}</td>
                            <td>{renderStatusBadge(cr.status)}</td>
                            <td>{cr.new_posts}</td>
                            <td>{cr.posts_discovered}</td>
                            <td className="error-cell">{cr.error_message || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            ) : (
              <div className="empty-state">
                {runs.length === 0 ? (
                  <div className="empty-message">
                    <h3>No Active Scrape</h3>
                    <p>Start your first scrape to collect competitor updates.</p>
                  </div>
                ) : (
                  <p>Select a run to view details.</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default ProjectScraping;
