import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import {
  getDiscoveryRuns,
  startDiscovery,
  getDiscoveryCandidates,
  selectDiscoveryCandidate,
  rejectDiscoveryCandidate,
  bulkSelectDiscoveryCandidates,
  bulkRejectDiscoveryCandidates,
} from '../api';
import type { DiscoveryRun, DiscoveryCandidate } from '../api';
import './ProjectDiscovery.css';

const ProjectDiscovery = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [runs, setRuns] = useState<DiscoveryRun[]>([]);
  const [candidates, setCandidates] = useState<DiscoveryCandidate[]>([]);

  const [loadingRuns, setLoadingRuns] = useState(true);
  const [loadingCandidates, setLoadingCandidates] = useState(false);

  // Discovery Form State
  const [showDiscoveryForm, setShowDiscoveryForm] = useState(false);
  const [formQuery, setFormQuery] = useState('');
  const [formLocation, setFormLocation] = useState('');
  const [formCategory, setFormCategory] = useState('');
  const [formRadius, setFormRadius] = useState<number>(10);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  // Multi-selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkSubmitting, setBulkSubmitting] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  const pollTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (projectId) {
      loadRuns();
      loadCandidates();
    }
  }, [projectId]);

  // Polling effect for active discovery runs
  useEffect(() => {
    const hasActiveRun = runs.some(r => r.status === 'QUEUED' || r.status === 'RUNNING');
    if (hasActiveRun) {
      if (!pollTimerRef.current) {
        pollTimerRef.current = window.setInterval(async () => {
          if (!projectId) return;
          try {
            const [runsRes, candRes] = await Promise.all([
              getDiscoveryRuns(projectId),
              getDiscoveryCandidates(projectId, 0, 100),
            ]);
            setRuns(runsRes.data);
            setCandidates(candRes.data);
          } catch (e) {
            console.error('Error during discovery polling', e);
          }
        }, 3000);
      }
    } else {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    }

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [runs, projectId]);

  const loadRuns = async () => {
    try {
      setLoadingRuns(true);
      const res = await getDiscoveryRuns(projectId!);
      setRuns(res.data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoadingRuns(false);
    }
  };

  const loadCandidates = async () => {
    try {
      setLoadingCandidates(true);
      const res = await getDiscoveryCandidates(projectId!, 0, 100);
      setCandidates(res.data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoadingCandidates(false);
    }
  };

  const handleStartDiscovery = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setFormSubmitting(true);
      setFormError('');
      const res = await startDiscovery(projectId!, {
        query: formQuery.trim() || undefined,
        location: formLocation.trim() || undefined,
        category: formCategory.trim() || undefined,
        radius: formRadius > 0 ? formRadius : 10,
      });
      setShowDiscoveryForm(false);
      setFormQuery('');
      setFormLocation('');
      setFormCategory('');
      setActionSuccessMsg(
        `Discovery started with a ${formRadius} km radius search! Finding competitors now...`
      );
      setRuns(prev => [res.data, ...prev.filter(r => r.id !== res.data.id)]);
      setTimeout(() => {
        loadRuns();
        loadCandidates();
      }, 1000);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to start discovery');
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleSelect = async (candidateId: string) => {
    try {
      await selectDiscoveryCandidate(projectId!, candidateId);
      setActionSuccessMsg('Competitor added to project! Scraping starts when you trigger it on the Scraping page.');
      setSelectedIds(prev => {
        const next = new Set(prev);
        next.delete(candidateId);
        return next;
      });
      loadCandidates();
    } catch (err) {
      alert('Failed to select candidate.');
    }
  };

  const handleReject = async (candidateId: string) => {
    try {
      await rejectDiscoveryCandidate(projectId!, candidateId);
      setSelectedIds(prev => {
        const next = new Set(prev);
        next.delete(candidateId);
        return next;
      });
      loadCandidates();
    } catch (err) {
      alert('Failed to reject candidate.');
    }
  };

  // Toggle single selection
  const toggleSelectCandidate = (candidateId: string, status: string) => {
    if (status !== 'NEW') return;
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(candidateId)) {
        next.delete(candidateId);
      } else {
        next.add(candidateId);
      }
      return next;
    });
  };

  // Toggle select all new candidates
  const newCandidates = candidates.filter(c => c.status === 'NEW');
  const allNewSelected = newCandidates.length > 0 && newCandidates.every(c => selectedIds.has(c.id));

  const handleToggleSelectAll = () => {
    if (allNewSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(newCandidates.map(c => c.id)));
    }
  };

  // Bulk add selected candidates as competitors
  const handleBulkSelect = async () => {
    if (selectedIds.size === 0) return;
    const count = selectedIds.size;
    try {
      setBulkSubmitting(true);
      await bulkSelectDiscoveryCandidates(projectId!, Array.from(selectedIds));
      setActionSuccessMsg(
        `✓ Added ${count} competitors to your project! They are now visible on your Competitors and Scraping pages.`
      );
      setSelectedIds(new Set());
      loadCandidates();
    } catch (err) {
      alert('Failed to add selected competitors.');
    } finally {
      setBulkSubmitting(false);
    }
  };

  // Bulk reject selected candidates
  const handleBulkReject = async () => {
    if (selectedIds.size === 0) return;
    const count = selectedIds.size;
    try {
      setBulkSubmitting(true);
      await bulkRejectDiscoveryCandidates(projectId!, Array.from(selectedIds));
      setActionSuccessMsg(`Rejected ${count} candidates.`);
      setSelectedIds(new Set());
      loadCandidates();
    } catch (err) {
      alert('Failed to reject selected candidates.');
    } finally {
      setBulkSubmitting(false);
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'QUEUED':
        return 'badge-queued';
      case 'RUNNING':
        return 'badge-running';
      case 'SUCCESS':
        return 'badge-success';
      case 'PARTIAL_SUCCESS':
        return 'badge-warning';
      case 'FAILED':
        return 'badge-failed';
      case 'PAUSED_MANUAL_INTERVENTION':
        return 'badge-warning';
      default:
        return 'badge-default';
    }
  };

  const getCandidateBadgeClass = (status: string) => {
    switch (status) {
      case 'NEW':
        return 'badge-new';
      case 'SELECTED':
        return 'badge-selected';
      case 'REJECTED':
        return 'badge-rejected';
      case 'ALREADY_COMPETITOR':
        return 'badge-already';
      default:
        return 'badge-default';
    }
  };

  const radiusPresets = [2, 5, 10, 25, 50];

  return (
    <AppLayout projectId={projectId}>
      <header className="topbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Discovery ({newCandidates.length} New Candidates)</h1>
          <p className="discovery-header-subtitle">
            Find and choose competitors in your area. Scraping starts strictly when you trigger it on the Scraping page.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="secondary-btn" onClick={() => navigate(`/projects/${projectId}/competitors`)}>
            Competitors
          </button>
          <button className="secondary-btn" onClick={() => navigate(`/projects/${projectId}/scraping`)}>
            Scraping Page
          </button>
          <button className="primary-btn" onClick={() => setShowDiscoveryForm(!showDiscoveryForm)}>
            {showDiscoveryForm ? 'Close Form' : '+ New Discovery'}
          </button>
        </div>
      </header>

      <div className="content-area">
        {actionSuccessMsg && (
          <div className="discovery-banner-success">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span className="banner-icon">✓</span>
              <span>{actionSuccessMsg}</span>
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <button
                className="banner-action-btn"
                onClick={() => navigate(`/projects/${projectId}/scraping`)}
              >
                Go to Scraping Page &rarr;
              </button>
              <button className="banner-close-btn" onClick={() => setActionSuccessMsg(null)}>
                &times;
              </button>
            </div>
          </div>
        )}

        {showDiscoveryForm && (
          <div className="form-container mb-6 discovery-search-box">
            <div className="discovery-box-header">
              <div>
                <h2>Start Competitor Discovery</h2>
                <p className="form-subtitle">Search businesses by keyword, location, and radius in kilometers.</p>
              </div>
              <button className="icon-btn" onClick={() => setShowDiscoveryForm(false)}>&times;</button>
            </div>

            {formError && <div className="state-message error">{formError}</div>}

            <form onSubmit={handleStartDiscovery} className="create-form">
              <div className="form-grid-2">
                <div className="form-group">
                  <label>Search Query / Keywords *</label>
                  <input
                    type="text"
                    value={formQuery}
                    onChange={e => setFormQuery(e.target.value)}
                    placeholder="e.g. bakeries, cafes, pastry shops"
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Location (City / Area)</label>
                  <input
                    type="text"
                    value={formLocation}
                    onChange={e => setFormLocation(e.target.value)}
                    placeholder="e.g. Bandra, Mumbai"
                  />
                </div>
              </div>

              <div className="form-grid-2" style={{ marginTop: '16px' }}>
                <div className="form-group">
                  <label>Business Category (Optional)</label>
                  <input
                    type="text"
                    value={formCategory}
                    onChange={e => setFormCategory(e.target.value)}
                    placeholder="e.g. Bakery"
                  />
                </div>

                <div className="form-group">
                  <label>
                    Search Radius (Range in km): <strong style={{ color: '#60a5fa' }}>{formRadius} km</strong>
                  </label>
                  <div className="radius-selector-wrap">
                    <div className="radius-presets">
                      {radiusPresets.map(r => (
                        <button
                          key={r}
                          type="button"
                          className={`radius-pill ${formRadius === r ? 'active' : ''}`}
                          onClick={() => setFormRadius(r)}
                        >
                          {r} km
                        </button>
                      ))}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
                      <input
                        type="range"
                        min="1"
                        max="50"
                        step="1"
                        value={formRadius}
                        onChange={e => setFormRadius(Number(e.target.value))}
                        className="radius-slider"
                      />
                      <span style={{ fontSize: '12px', color: '#94a3b8', minWidth: '45px' }}>{formRadius} km</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="form-actions" style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button
                  type="button"
                  className="secondary-btn"
                  onClick={() => setShowDiscoveryForm(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="primary-btn" disabled={formSubmitting}>
                  {formSubmitting ? 'Searching...' : `Search within ${formRadius} km`}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Multi-Select Floating / Sticky Action Bar */}
        {selectedIds.size > 0 && (
          <div className="bulk-selection-bar">
            <div className="bulk-selection-info">
              <span className="selection-badge">{selectedIds.size}</span>
              <span className="selection-text">
                {selectedIds.size === 1 ? '1 competitor' : `${selectedIds.size} competitors`} selected for project
              </span>
            </div>
            <div className="bulk-selection-actions">
              <button
                className="primary-btn bulk-btn"
                onClick={handleBulkSelect}
                disabled={bulkSubmitting}
              >
                {bulkSubmitting ? 'Adding...' : `✓ Add ${selectedIds.size} as Competitors`}
              </button>
              <button
                className="secondary-btn bulk-btn-reject"
                onClick={handleBulkReject}
                disabled={bulkSubmitting}
              >
                Reject Selected
              </button>
              <button
                className="text-btn"
                onClick={() => setSelectedIds(new Set())}
                disabled={bulkSubmitting}
              >
                Deselect All
              </button>
            </div>
          </div>
        )}

        <div className="discovery-layout">
          {/* Left Column: Runs History */}
          <div className="runs-column">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 className="section-title">Runs History</h2>
              <button className="icon-btn" onClick={loadRuns} title="Refresh Runs">&#x21bb;</button>
            </div>
            {loadingRuns && <div className="state-message">Loading runs...</div>}
            {!loadingRuns && runs.length === 0 && (
              <div className="empty-state-small">No discovery runs yet. Click "+ New Discovery" above.</div>
            )}
            <div className="runs-list">
              {runs.map(run => (
                <div key={run.id} className="run-card">
                  <div className="run-header">
                    <span className="run-date">{run.started_at ? new Date(run.started_at).toLocaleDateString() : 'Pending'}</span>
                    <span className={`status-badge ${getStatusBadgeClass(run.status)}`}>{run.status.replace(/_/g, ' ')}</span>
                  </div>
                  <div className="run-details">
                    {run.query && <div><strong>Query:</strong> {run.query}</div>}
                    {run.location && <div><strong>Location:</strong> {run.location}</div>}
                    <div><strong>Radius:</strong> {run.radius || 10} km</div>
                    {run.error_message && (
                      <div style={{ color: 'var(--accent-red)', fontSize: '0.8rem', marginTop: '4px' }}>
                        {run.error_message}
                      </div>
                    )}
                  </div>
                  <div className="run-stats">
                    <span>{run.total_candidates} Found</span>
                    <span>{run.duplicates_skipped} Skipped</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Column: Candidates */}
          <div className="candidates-column">
            <div className="candidates-header-row">
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <h2 className="section-title" style={{ margin: 0 }}>
                  Candidates ({candidates.length})
                </h2>
                {newCandidates.length > 0 && (
                  <label className="select-all-label">
                    <input
                      type="checkbox"
                      checked={allNewSelected}
                      onChange={handleToggleSelectAll}
                    />
                    <span>Select All New ({newCandidates.length})</span>
                  </label>
                )}
              </div>
              <button className="icon-btn" onClick={loadCandidates} title="Refresh Candidates">&#x21bb;</button>
            </div>

            {loadingCandidates && <div className="state-message">Loading candidates...</div>}
            {!loadingCandidates && candidates.length === 0 && (
              <div className="empty-state">
                No discovery candidates found. Start a new discovery run with a keyword and radius in km.
              </div>
            )}

            <div className="candidates-list">
              {candidates.map(cand => {
                const isSelected = selectedIds.has(cand.id);
                const isNew = cand.status === 'NEW';
                return (
                  <div
                    key={cand.id}
                    className={`candidate-card ${isSelected ? 'selected' : ''} ${!isNew ? 'non-selectable' : ''}`}
                    onClick={() => isNew && toggleSelectCandidate(cand.id, cand.status)}
                  >
                    <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start', flex: 1 }}>
                      {isNew && (
                        <div className="candidate-checkbox-wrap" onClick={e => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelectCandidate(cand.id, cand.status)}
                            className="candidate-checkbox"
                          />
                        </div>
                      )}

                      <div className="candidate-info">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <h3 style={{ margin: 0 }}>{cand.business_name}</h3>
                          {isSelected && (
                            <span className="selected-tag">✓ Selected</span>
                          )}
                        </div>

                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '6px', flexWrap: 'wrap' }}>
                          {cand.category && <span className="category-badge">{cand.category}</span>}
                          {cand.distance_km != null && (
                            <span className="distance-badge">
                              📍 {cand.distance_km} km away
                            </span>
                          )}
                          {cand.rating && (
                            <span className="rating-badge">
                              ★ {cand.rating} ({cand.review_count || 0})
                            </span>
                          )}
                        </div>

                        <div className="candidate-meta" style={{ marginTop: '8px' }}>
                          {cand.address && <span>{cand.address}</span>}
                        </div>

                        <div style={{ display: 'flex', gap: '14px', marginTop: '8px' }}>
                          {cand.source_url && (
                            <a
                              href={cand.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="maps-link"
                              onClick={e => e.stopPropagation()}
                            >
                              Google Maps &rarr;
                            </a>
                          )}
                          {cand.website && (
                            <a
                              href={cand.website}
                              target="_blank"
                              rel="noreferrer"
                              className="maps-link"
                              onClick={e => e.stopPropagation()}
                            >
                              Website &rarr;
                            </a>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="candidate-actions" onClick={e => e.stopPropagation()}>
                      <div className={`status-badge ${getCandidateBadgeClass(cand.status)}`} style={{ marginBottom: '12px', textAlign: 'center' }}>
                        {cand.status.replace(/_/g, ' ')}
                      </div>

                      {isNew && (
                        <div className="action-buttons">
                          <button
                            className="primary-btn-sm"
                            onClick={() => handleSelect(cand.id)}
                            title="Add as competitor"
                          >
                            + Select
                          </button>
                          <button
                            className="secondary-btn-sm"
                            onClick={() => handleReject(cand.id)}
                            title="Reject candidate"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default ProjectDiscovery;
