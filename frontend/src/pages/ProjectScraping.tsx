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

const formatRunName = (run?: ScrapeRun | null): string => {
  if (!run) return 'Scrape Run';
  if (run.display_name) return run.display_name;
  if (run.run_number !== undefined && run.run_number !== null) {
    return `Scrape ${String(run.run_number).padStart(3, '0')}`;
  }
  return `Scrape #${run.id.slice(0, 8)}`;
};

const ProjectScraping: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [runs, setRuns] = useState<ScrapeRun[]>([]);
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const activeRunIdRef = useRef<string | null>(null);
  activeRunIdRef.current = activeRunId;
  const [activeRunDetails, setActiveRunDetails] = useState<ScrapeRun | null>(null);

  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [reconnectingMessage, setReconnectingMessage] = useState<string | null>(null);

  const pollTimeoutRef = useRef<number | null>(null);
  const isPollingActiveRef = useRef<boolean>(false);
  const inFlightPollRef = useRef<boolean>(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const consecutiveErrorsRef = useRef<number>(0);
  const lastLoggedErrorRef = useRef<string | null>(null);
  const isSubmittingScrapeRef = useRef<boolean>(false);
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
        activeRunIdRef.current = active.id;
        setActiveRunDetails(prev => prev?.id === active.id ? prev : active);
        startPolling();
      } else if (sortedRuns.length > 0 && !activeRunIdRef.current) {
        setActiveRunId(sortedRuns[0].id);
        activeRunIdRef.current = sortedRuns[0].id;
        setActiveRunDetails(sortedRuns[0]);
      }
    } catch (err: any) {
      console.error(err);
      showToast('Failed to load scrape runs', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    if (refreshing || !projectId) return;
    try {
      setRefreshing(true);
      const [runsRes, compRes] = await Promise.all([
        getScrapeRuns(projectId),
        getProjectCompetitors(projectId),
      ]);

      setCompetitors(compRes.data);

      const sortedRuns = runsRes.data.sort((a, b) => {
        if (a.start_time && b.start_time) {
          return new Date(b.start_time).getTime() - new Date(a.start_time).getTime();
        }
        return (b.run_number || 0) - (a.run_number || 0) || b.id.localeCompare(a.id);
      });
      setRuns(sortedRuns);

      const targetId = activeRunIdRef.current || sortedRuns[0]?.id;
      if (targetId && !targetId.startsWith('run-') && !targetId.startsWith('temp-')) {
        await fetchActiveRunDetails(targetId);
      }
      showToast('Scraping data refreshed', 'success');
    } catch (err: any) {
      console.error('Refresh error:', err);
      showToast('Failed to refresh scraping data', 'error');
    } finally {
      setRefreshing(false);
    }
  };

  const fetchActiveRunDetails = async (runId: string, signal?: AbortSignal) => {
    if (!runId || runId.startsWith('run-') || runId.startsWith('temp-')) {
      return;
    }
    try {
      const res = await getScrapeRun(runId, { signal });
      setActiveRunDetails(res.data);

      if (['SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'CANCELLED'].includes(res.data.status)) {
        // If this run is finished, check if any other runs are still active
        setRuns(prev => {
          const hasOtherActive = prev.some(r => r.id !== runId && ['QUEUED', 'RUNNING', 'RETRYING'].includes(r.status));
          if (!hasOtherActive) {
            stopPolling();
          }
          return prev;
        });

        // ONLY notify if this run was actively started/running in this session
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
    } catch (err: any) {
      if (err.name !== 'CanceledError' && err.name !== 'AbortError' && err.code !== 'ERR_CANCELED') {
        const errKey = `detail:${err.response?.status || 'net'}`;
        if (lastLoggedErrorRef.current !== errKey) {
          console.warn('[Run Details] Could not fetch run details:', err);
          lastLoggedErrorRef.current = errKey;
        }
      }
    }
  };

  const stopPolling = () => {
    isPollingActiveRef.current = false;
    if (pollTimeoutRef.current) {
      window.clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    inFlightPollRef.current = false;
    setReconnectingMessage(null);
  };

  const scheduleNextPoll = (delayMs: number) => {
    if (!isPollingActiveRef.current) return;
    if (pollTimeoutRef.current) {
      window.clearTimeout(pollTimeoutRef.current);
    }
    pollTimeoutRef.current = window.setTimeout(() => {
      pollOnce();
    }, delayMs);
  };

  const pollOnce = async () => {
    if (!isPollingActiveRef.current || !projectId) return;
    if (inFlightPollRef.current) return; // Prevent concurrent requests!

    inFlightPollRef.current = true;
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const runsRes = await getScrapeRuns(projectId, { signal: controller.signal });
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
        return;
      }

      let targetId = activeRunIdRef.current;
      // If current active ID is optimistic/temporary, see if backend created the active run
      if (targetId && (targetId.startsWith('run-') || targetId.startsWith('temp-'))) {
        const serverActiveRun = sorted.find(r => ['QUEUED', 'RUNNING', 'RETRYING'].includes(r.status));
        if (serverActiveRun) {
          targetId = serverActiveRun.id;
          setActiveRunId(serverActiveRun.id);
          activeRunIdRef.current = serverActiveRun.id;
          setActiveRunDetails(serverActiveRun);
        }
      }

      if (targetId && !targetId.startsWith('run-') && !targetId.startsWith('temp-')) {
        await fetchActiveRunDetails(targetId, controller.signal);
      }

      // Success: reset error tracking and schedule next standard poll (3.5s)
      consecutiveErrorsRef.current = 0;
      lastLoggedErrorRef.current = null;
      setReconnectingMessage(null);
      scheduleNextPoll(3500);
    } catch (err: any) {
      if (err.name === 'CanceledError' || err.name === 'AbortError' || err.code === 'ERR_CANCELED') {
        return;
      }

      consecutiveErrorsRef.current += 1;
      const status = err.response?.status;
      const errorMsg = err.response?.data?.detail || err.message || 'Network Error';
      const errorKey = `${status || 'network'}:${errorMsg}`;

      if (lastLoggedErrorRef.current !== errorKey) {
        console.warn(`[Scrape Polling] Request failed (Status: ${status || 'Network Error'}). Backing off...`);
        lastLoggedErrorRef.current = errorKey;
      }

      // Respect Retry-After header or calculate exponential backoff
      let delayMs = 3500;
      const retryAfterHeader = err.response?.headers?.['retry-after'];
      if (retryAfterHeader) {
        const parsed = parseInt(retryAfterHeader, 10);
        if (!isNaN(parsed) && parsed > 0) {
          delayMs = Math.min(parsed * 1000, 30000);
        }
      } else {
        // Exponential backoff: 3.5s -> 5.2s -> 7.8s -> 11.8s -> max 30s
        delayMs = Math.min(30000, Math.round(3500 * Math.pow(1.5, consecutiveErrorsRef.current)));
      }

      if (consecutiveErrorsRef.current >= 2) {
        setReconnectingMessage(`Backend temporarily busy (reconnecting in ${Math.round(delayMs / 1000)}s)...`);
      }

      scheduleNextPoll(delayMs);
    } finally {
      inFlightPollRef.current = false;
    }
  };

  const startPolling = () => {
    if (isPollingActiveRef.current) return;
    isPollingActiveRef.current = true;
    consecutiveErrorsRef.current = 0;
    scheduleNextPoll(1000);
  };

  useEffect(() => {
    if (projectId) {
      loadData();
    }
    return () => stopPolling();
  }, [projectId]);

  useEffect(() => {
    if (activeRunId && !activeRunId.startsWith('run-') && !activeRunId.startsWith('temp-')) {
      fetchActiveRunDetails(activeRunId);

      const run = runs.find(r => r.id === activeRunId);
      if (run && ['QUEUED', 'RUNNING', 'RETRYING'].includes(run.status)) {
        startPolling();
      }
    }
  }, [activeRunId]);

  const handleSelectRun = (run: ScrapeRun) => {
    setActiveRunId(run.id);
    activeRunIdRef.current = run.id;
    setActiveRunDetails(run);
    if (!run.id.startsWith('run-') && !run.id.startsWith('temp-')) {
      fetchActiveRunDetails(run.id);
    }
    if (['QUEUED', 'RUNNING', 'RETRYING'].includes(run.status)) {
      userInitiatedRunIdsRef.current.add(run.id);
      startPolling();
    }
  };

  const handleStartScrape = async () => {
    if (!projectId || starting || isSubmittingScrapeRef.current) return;
    if (competitors.length === 0) {
      showToast('Add competitors on the Discovery or Competitors page before scraping.', 'warning');
      return;
    }

    isSubmittingScrapeRef.current = true;
    setStarting(true);

    const tempId = `run-${Date.now()}`;
    const optimisticRun: ScrapeRun = {
      id: tempId,
      project_id: projectId,
      status: 'QUEUED',
      start_time: new Date().toISOString(),
      competitors_attempted: competitors.length,
      competitors_succeeded: 0,
      competitors_failed: 0,
      competitor_runs: competitors.map(c => ({
        id: `pending-${c.id}`,
        business_id: c.business_id,
        business: c.business,
        status: 'PENDING',
        posts_discovered: 0,
        new_posts: 0,
        duplicates_skipped: 0,
      })),
    };

    setActiveRunId(tempId);
    activeRunIdRef.current = tempId;
    setActiveRunDetails(optimisticRun);
    setRuns(prev => [optimisticRun, ...prev.filter(r => r.id !== tempId)]);

    try {
      const res = await startScrape(projectId);
      const newRun = res.data;

      userInitiatedRunIdsRef.current.add(newRun.id);
      setActiveRunId(newRun.id);
      activeRunIdRef.current = newRun.id;
      setActiveRunDetails(newRun);
      setRuns(prev => [newRun, ...prev.filter(r => r.id !== tempId && r.id !== newRun.id)]);

      showToast(`Scrape pipeline started for ${competitors.length} competitors!`, 'info');
      startPolling();
    } catch (err: any) {
      const status = err.response?.status;
      const msg = err.response?.data?.detail || 'Failed to start scrape run';

      if (status === 409 || msg.includes('already has an active run')) {
        showToast('A scrape run is already in progress. Syncing with active run...', 'info');
        setRuns(prev => prev.filter(r => r.id !== tempId));
        await loadData();
        startPolling();
      } else {
        showToast(msg, 'error');
        setRuns(prev => prev.filter(r => r.id !== tempId));
        if (activeRunIdRef.current === tempId) {
          setActiveRunId(runs[0]?.id || null);
          activeRunIdRef.current = runs[0]?.id || null;
          setActiveRunDetails(runs[0] || null);
        }
        await loadData();
      }
    } finally {
      setStarting(false);
      isSubmittingScrapeRef.current = false;
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
              <Database size={13} /> Competitor Posts Collector
            </span>
          </div>
          <p className="scraping-header-subtitle">
            Collect Google Maps updates, photos, and promotional posts for your active competitor roster.
          </p>
        </div>
        <div className="topbar-actions">
          <button
            className="secondary-btn"
            onClick={handleRefresh}
            disabled={refreshing}
            title="Refresh runs and competitor progress"
          >
            <RefreshCw size={15} className={refreshing ? 'spin' : ''} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
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
        {reconnectingMessage && (
          <div className="pipeline-banner" style={{ background: '#fffbeb', borderColor: '#fef3c7', color: '#92400e', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px', borderRadius: '8px' }}>
            <Clock size={16} />
            <span style={{ fontSize: '0.875rem' }}>{reconnectingMessage}</span>
          </div>
        )}

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
                <span className="active-scrape-id">{formatRunName(activeRun)}</span>
              </div>
              <p className="active-scrape-desc">
                Extracting posts and updates for {competitors.length} competitors. Real-time updates stream below automatically.
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
                        <span className="run-card-id">{formatRunName(run)}</span>
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
                    <h2>{formatRunName(activeRunDetails)}</h2>
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
