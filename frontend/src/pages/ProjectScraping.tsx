import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { useToast } from '../context/ToastContext';
import {
  getScrapeRuns,
  startScrape,
  getScrapeRun,
  resumeScrapeRun,
  deleteScrapeRun,
  getProjectCompetitors,
} from '../api';
import type { ScrapeRun, ScrapeRunCompetitor, Competitor } from '../api';
import {
  Database,
  Play,
  RefreshCw,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowRight,
  FileText,
  MessageSquareHeart,
  Sparkles,
  Info,
  ShieldAlert,
  Users
} from 'lucide-react';
import './ProjectScraping.css';

const STATUS_CONFIG: Record<string, { label: string; pillClass: string; icon: string }> = {
  QUEUED: { label: 'Queued', pillClass: 'status-queued', icon: 'queued' },
  RUNNING: { label: 'Scraping Active', pillClass: 'status-running', icon: 'running' },
  RETRYING: { label: 'Retrying', pillClass: 'status-warning', icon: 'running' },
  PAUSED_MANUAL_INTERVENTION: { label: 'Action Required', pillClass: 'status-warning', icon: 'warning' },
  PARTIAL_SUCCESS: { label: 'Partial Success', pillClass: 'status-warning', icon: 'success' },
  SUCCESS: { label: 'Completed', pillClass: 'status-success', icon: 'success' },
  FAILED: { label: 'Failed', pillClass: 'status-failed', icon: 'failed' },
  CANCELLED: { label: 'Cancelled', pillClass: 'status-queued', icon: 'failed' },
  PENDING: { label: 'Pending', pillClass: 'status-queued', icon: 'queued' },
  NO_DATA: { label: 'No Posts Found', pillClass: 'status-queued', icon: 'queued' },
  VERIFICATION_REQUIRED: { label: 'Verification Needed', pillClass: 'status-warning', icon: 'warning' },
  ERROR: { label: 'Error', pillClass: 'status-failed', icon: 'failed' },
};

const ProjectScraping: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [runs, setRuns] = useState<ScrapeRun[]>([]);
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [activeRunDetails, setActiveRunDetails] = useState<ScrapeRun | null>(null);

  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [resuming, setResuming] = useState(false);

  const pollTimerRef = useRef<number | null>(null);
  const completedRunsNotifiedRef = useRef<Set<string>>(new Set());
  const userInitiatedRunIdsRef = useRef<Set<string>>(new Set());

  const loadData = async () => {
    try {
      setLoading(true);
      const [runsRes, compRes] = await Promise.all([
        getScrapeRuns(projectId!),
        getProjectCompetitors(projectId!),
      ]);

      setCompetitors(compRes.data);

      const sortedRuns = runsRes.data.sort((a, b) => {
        if (a.start_time && b.start_time) {
          return new Date(b.start_time).getTime() - new Date(a.start_time).getTime();
        }
        return b.id.localeCompare(a.id);
      });
      setRuns(sortedRuns);

      const active = sortedRuns.find(r =>
        ['QUEUED', 'RUNNING', 'RETRYING', 'PAUSED_MANUAL_INTERVENTION'].includes(r.status)
      );
      if (active) {
        if (['QUEUED', 'RUNNING', 'RETRYING'].includes(active.status)) {
          userInitiatedRunIdsRef.current.add(active.id);
        }
        setActiveRunId(active.id);
        setActiveRunDetails(prev => prev?.id === active.id ? prev : active);
      } else if (sortedRuns.length > 0 && !activeRunId) {
        setActiveRunId(sortedRuns[0].id);
        setActiveRunDetails(sortedRuns[0]);
      }
    } catch (err: any) {
      console.error(err);
      showToast('Failed to load scrape runs', 'error');
    } finally {
      setLoading(false);
    }
  };

  const fetchActiveRunDetails = async (runId: string) => {
    try {
      const res = await getScrapeRun(runId);
      setActiveRunDetails(res.data);

      if (['SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'CANCELLED'].includes(res.data.status)) {
        stopPolling();

        // ONLY notify if this run was actively started/running in this session,
        // and has not already shown a completion notification
        if (
          userInitiatedRunIdsRef.current.has(runId) &&
          !completedRunsNotifiedRef.current.has(runId)
        ) {
          completedRunsNotifiedRef.current.add(runId);
          userInitiatedRunIdsRef.current.delete(runId);

          if (res.data.status === 'SUCCESS') {
            showToast('Scraping run completed successfully!', 'success');
          } else if (res.data.status === 'PARTIAL_SUCCESS') {
            showToast('Scrape run finished with some competitor warnings.', 'warning');
          } else if (res.data.status === 'FAILED') {
            showToast('Scraping run failed.', 'error');
          }
        }
      }
    } catch (err) {
      console.error('Failed to load run details', err);
    }
  };

  const startPolling = () => {
    if (pollTimerRef.current) return;
    pollTimerRef.current = window.setInterval(async () => {
      if (!projectId) return;
      try {
        const runsRes = await getScrapeRuns(projectId);
        const sorted = runsRes.data.sort((a, b) => {
          if (a.start_time && b.start_time) {
            return new Date(b.start_time).getTime() - new Date(a.start_time).getTime();
          }
          return b.id.localeCompare(a.id);
        });
        setRuns(sorted);

        const hasActive = sorted.some(r => ['QUEUED', 'RUNNING', 'RETRYING'].includes(r.status));
        if (!hasActive) {
          stopPolling();
        }

        if (activeRunId) {
          await fetchActiveRunDetails(activeRunId);
        }
      } catch (e) {
        console.error('Polling error', e);
      }
    }, 2800);
  };

  const stopPolling = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  useEffect(() => {
    if (projectId) {
      loadData();
    }
    return () => stopPolling();
  }, [projectId]);

  useEffect(() => {
    if (activeRunId) {
      fetchActiveRunDetails(activeRunId);

      const run = runs.find(r => r.id === activeRunId);
      if (run && ['QUEUED', 'RUNNING', 'RETRYING'].includes(run.status)) {
        startPolling();
      } else {
        stopPolling();
      }
    }
  }, [activeRunId]);

  const handleSelectRun = (run: ScrapeRun) => {
    setActiveRunId(run.id);
    setActiveRunDetails(run); // Immediately switch details view so user sees it right away!
    fetchActiveRunDetails(run.id);
    if (['QUEUED', 'RUNNING', 'RETRYING'].includes(run.status)) {
      userInitiatedRunIdsRef.current.add(run.id);
      startPolling();
    }
  };

  const handleStartScrape = async () => {
    if (!projectId) return;
    if (competitors.length === 0) {
      showToast('Add competitors on the Discovery or Competitors page before scraping.', 'warning');
      return;
    }

    setStarting(true);
    try {
      const res = await startScrape(projectId);
      const newRun = res.data;

      // Instantly open and display the new run before background requests finish
      userInitiatedRunIdsRef.current.add(newRun.id);
      setActiveRunId(newRun.id);
      setActiveRunDetails(newRun);
      setRuns(prev => [newRun, ...prev.filter(r => r.id !== newRun.id)]);

      showToast(`Scrape pipeline started for ${competitors.length} competitors!`, 'info');
      startPolling();
      loadData();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to start scrape run';
      showToast(msg, 'error');
      await loadData();
    } finally {
      setStarting(false);
    }
  };

  const handleResumeRun = async () => {
    if (!activeRunId) return;
    setResuming(true);
    try {
      const res = await resumeScrapeRun(activeRunId);
      userInitiatedRunIdsRef.current.add(activeRunId);
      completedRunsNotifiedRef.current.delete(activeRunId); // allow notification when resumed run finishes
      showToast('Resuming scrape run...', 'info');
      if (res.data) {
        setActiveRunDetails(res.data);
      }
      await loadData();
      startPolling();
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to resume run', 'error');
    } finally {
      setResuming(false);
    }
  };

  const handleDeleteRun = async (e: React.MouseEvent, runId: string) => {
    e.stopPropagation();
    if (!window.confirm('Delete this scrape run? Scraped posts and reviews will be preserved.')) return;

    try {
      await deleteScrapeRun(projectId!, runId);
      showToast('Scrape run deleted.', 'info');
      if (activeRunId === runId) {
        setActiveRunId(null);
        setActiveRunDetails(null);
      }
      await loadData();
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to delete run', 'error');
    }
  };

  const renderStatusBadge = (status: string) => {
    const config = STATUS_CONFIG[status.toUpperCase()] || {
      label: status,
      pillClass: 'status-queued',
      icon: 'queued',
    };

    return (
      <span className={`status-pill ${config.pillClass}`}>
        {config.icon === 'running' && <span className="pulse-dot running"></span>}
        {config.icon === 'success' && <CheckCircle2 size={12} />}
        {config.icon === 'failed' && <AlertCircle size={12} />}
        {config.label}
      </span>
    );
  };

  const activeRun = runs.find(r => ['QUEUED', 'RUNNING', 'RETRYING'].includes(r.status));

  return (
    <AppLayout projectId={projectId}>
      {/* Top Header */}
      <header className="topbar scraping-topbar">
        <div className="topbar-left">
          <div className="topbar-title-row">
            <h1>Scraping Pipeline</h1>
            <span className="status-pill status-running">
              <Database size={13} /> Posts & Reviews Collector
            </span>
          </div>
          <p className="scraping-header-subtitle">
            Collect Google Maps posts, photos, and customer reviews for your active competitor roster.
          </p>
        </div>
        <div className="topbar-actions">
          <button
            className="secondary-btn"
            onClick={loadData}
            title="Refresh runs"
          >
            <RefreshCw size={15} />
            <span>Refresh</span>
          </button>
          <button
            className="secondary-btn"
            onClick={() => navigate(`/projects/${projectId}/competitors`)}
          >
            <Users size={15} />
            <span>View Roster ({competitors.length})</span>
          </button>
          <button
            className="primary-btn"
            onClick={handleStartScrape}
            disabled={starting || competitors.length === 0}
          >
            <Play size={15} />
            <span>
              {starting
                ? 'Starting Pipeline...'
                : `Start Scraping (${competitors.length} Competitors)`}
            </span>
          </button>
        </div>
      </header>

      <div className="content-area">
        {/* Pipeline Decoupling Banner */}
        <div className="pipeline-banner scraping">
          <Info size={20} className="banner-icon" />
          <div className="banner-content">
            <strong>Data Collection Pipeline (Decoupled from Discovery):</strong> This pipeline scrapes social posts and reviews for the businesses in your <strong>Competitor Roster</strong> ({competitors.length} active). To discover and add new competitors, use the <Link to={`/projects/${projectId}/discovery`} className="banner-link">Discovery Scout page <ArrowRight size={12} /></Link>.
          </div>
        </div>

        {/* Live Active Scrape Banner / Card */}
        {activeRun && (
          <div className="active-scrape-card animate-slide-in">
            <div className="scrape-pulse-indicator">
              <span className="pulse-dot running"></span>
            </div>
            <div className="active-scrape-info">
              <div className="active-scrape-header">
                <span className="status-pill status-running">
                  <span className="pulse-dot running"></span> RUNNING NOW
                </span>
                <span className="active-scrape-id">Run #{activeRun.id.split('-')[0]}</span>
              </div>
              <p className="active-scrape-desc">
                Extracting posts and reviews for {competitors.length} competitors. Real-time updates stream below automatically.
              </p>
            </div>
          </div>
        )}

        {/* Main 2-Column Content Layout */}
        <div className="scraping-layout">
          {/* Left Column: Recent Runs List */}
          <div className="scraping-sidebar-col">
            <div className="runs-sidebar-header">
              <h3>Run History</h3>
              <span className="runs-count-badge">{runs.length} Runs</span>
            </div>

            {loading && runs.length === 0 ? (
              <div className="runs-skeleton-list">
                {[1, 2, 3].map(n => (
                  <div key={n} className="run-card-skeleton skeleton" style={{ height: '90px' }} />
                ))}
              </div>
            ) : runs.length === 0 ? (
              <div className="empty-runs-box">
                <Database size={28} className="text-dim" />
                <h4>No Scrapes Yet</h4>
                <p>Click "Start Scraping" above to run your first data collection.</p>
              </div>
            ) : (
              <div className="runs-list">
                {runs.map(run => {
                  const isSelected = activeRunId === run.id;
                  const isRunActive = ['QUEUED', 'RUNNING', 'RETRYING'].includes(run.status);

                  return (
                    <div
                      key={run.id}
                      className={`run-card ${isSelected ? 'active' : ''} ${isRunActive ? 'is-active-run' : ''}`}
                      onClick={() => handleSelectRun(run)}
                    >
                      <div className="run-card-top">
                        <span className="run-card-id">#{run.id.split('-')[0]}</span>
                        <div className="run-card-status-wrap">
                          {renderStatusBadge(run.status)}
                          <button
                            className="delete-run-btn"
                            onClick={e => handleDeleteRun(e, run.id)}
                            title="Delete run"
                            aria-label="Delete run"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>

                      <div className="run-card-meta">
                        <Clock size={12} />
                        <span>
                          {run.start_time
                            ? new Date(run.start_time).toLocaleString(undefined, {
                                dateStyle: 'short',
                                timeStyle: 'short',
                              })
                            : 'Not started'}
                        </span>
                      </div>

                      <div className="run-card-metrics">
                        <span>
                          <strong>{run.competitors_succeeded}</strong> / {run.competitors_attempted} Competitors
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right Column: Run Details & Competitor Breakdown */}
          <div className="scraping-details-col">
            {activeRunDetails ? (
              <div className="run-details-card">
                <div className="run-details-top">
                  <div>
                    <span className="details-subtitle">Scrape Run Inspection</span>
                    <h2>Run #{activeRunDetails.id}</h2>
                  </div>
                  <div>{renderStatusBadge(activeRunDetails.status)}</div>
                </div>

                {/* Manual Intervention Banner */}
                {activeRunDetails.status === 'PAUSED_MANUAL_INTERVENTION' && (
                  <div className="manual-intervention-box animate-slide-in">
                    <ShieldAlert size={22} className="text-warning" />
                    <div className="intervention-text">
                      <h4>Manual Verification Triggered</h4>
                      <p>
                        A captcha or verification checkpoint was encountered. Complete verification in the visible browser session, then click resume.
                      </p>
                      <button
                        className="btn-warning"
                        onClick={handleResumeRun}
                        disabled={resuming}
                      >
                        {resuming ? 'Resuming...' : 'Resume Scrape Run'}
                      </button>
                    </div>
                  </div>
                )}

                {/* Metrics Stats Row */}
                <div className="metrics-summary-grid">
                  <div className="metric-box">
                    <span className="metric-label">Competitors Attempted</span>
                    <span className="metric-val">{activeRunDetails.competitors_attempted}</span>
                  </div>
                  <div className="metric-box">
                    <span className="metric-label">Succeeded</span>
                    <span className="metric-val text-success">
                      {activeRunDetails.competitors_succeeded}
                    </span>
                  </div>
                  <div className="metric-box">
                    <span className="metric-label">Failed / Stalled</span>
                    <span className="metric-val text-error">
                      {activeRunDetails.competitors_failed}
                    </span>
                  </div>
                  <div className="metric-box">
                    <span className="metric-label">Pipeline Started</span>
                    <span className="metric-val small">
                      {activeRunDetails.start_time
                        ? new Date(activeRunDetails.start_time).toLocaleTimeString()
                        : 'N/A'}
                    </span>
                  </div>
                </div>

                {/* Quick Navigation into Extracted Data */}
                {['SUCCESS', 'PARTIAL_SUCCESS'].includes(activeRunDetails.status) && (
                  <div className="quick-intel-actions">
                    <Link
                      to={`/projects/${projectId}/posts`}
                      className="secondary-btn"
                    >
                      <FileText size={15} />
                      <span>View Posts</span>
                    </Link>
                    <Link
                      to={`/projects/${projectId}/reviews`}
                      className="secondary-btn"
                    >
                      <MessageSquareHeart size={15} />
                      <span>View Reviews</span>
                    </Link>
                    <Link
                      to={`/projects/${projectId}/intelligence`}
                      className="primary-btn"
                    >
                      <Sparkles size={15} />
                      <span>Synthesize Combined Intel</span>
                    </Link>
                  </div>
                )}

                {/* Competitor Scrape Results Table */}
                <div className="competitor-results-section">
                  <div className="section-header-row">
                    <h3>Competitor Scrape Results</h3>
                    <span className="results-count">
                      {activeRunDetails.competitor_runs?.length || 0} Businesses
                    </span>
                  </div>

                  {!activeRunDetails.competitor_runs || activeRunDetails.competitor_runs.length === 0 ? (
                    <p className="no-competitors-text">No competitor details recorded for this run.</p>
                  ) : (
                    <div className="table-responsive-wrapper">
                      <table className="modern-table">
                        <thead>
                          <tr>
                            <th>Business Name</th>
                            <th>Status</th>
                            <th>New Posts</th>
                            <th>Total Found</th>
                            <th>Status Notes / Error</th>
                          </tr>
                        </thead>
                        <tbody>
                          {activeRunDetails.competitor_runs.map((cr: ScrapeRunCompetitor) => (
                            <tr key={cr.id}>
                              <td className="business-cell">
                                <strong>{cr.business?.business_name || 'Unknown Business'}</strong>
                              </td>
                              <td>{renderStatusBadge(cr.status)}</td>
                              <td>
                                <span className="stat-highlight">{cr.new_posts}</span>
                              </td>
                              <td>{cr.posts_discovered}</td>
                              <td className="note-cell">{cr.error_message || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="select-run-placeholder">
                <Database size={36} className="text-dim" />
                <h3>Select a Scrape Run</h3>
                <p>Click on any run from the history sidebar to view competitor performance and extracted metrics.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default ProjectScraping;
