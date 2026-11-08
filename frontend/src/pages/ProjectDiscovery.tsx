import { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { useToast } from '../context/ToastContext';
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
import {
  Compass,
  Search,
  MapPin,
  Sliders,
  Check,
  X,
  Star,
  ExternalLink,
  RefreshCw,
  CheckSquare,
  Square,
  Users,
  ArrowRight,
  Info
} from 'lucide-react';
import './ProjectDiscovery.css';

const ProjectDiscovery = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [runs, setRuns] = useState<DiscoveryRun[]>([]);
  const [candidates, setCandidates] = useState<DiscoveryCandidate[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);

  // Form State
  const [showDiscoveryForm, setShowDiscoveryForm] = useState(false);
  const [formQuery, setFormQuery] = useState('');
  const [formLocation, setFormLocation] = useState('');
  const [formCategory, setFormCategory] = useState('');
  const [formRadius, setFormRadius] = useState<number>(10);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  // Filters & Search
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'NEW' | 'SELECTED' | 'ALREADY_COMPETITOR' | 'REJECTED'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Multi-selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkSubmitting, setBulkSubmitting] = useState(false);

  const pollTimerRef = useRef<number | null>(null);

  const radiusPresets = [2, 5, 10, 25, 50];

  useEffect(() => {
    if (projectId) {
      loadRuns();
      loadCandidates();
    }
  }, [projectId]);

  // Real-time polling when runs are active
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

            const stillActive = runsRes.data.some(r => r.status === 'QUEUED' || r.status === 'RUNNING');
            if (!stillActive) {
              showToast('Discovery search completed! Candidates updated.', 'success');
            }
          } catch (e) {
            console.error('Error during discovery polling', e);
          }
        }, 2500);
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
  }, [runs, projectId, showToast]);

  const loadRuns = async () => {
    try {
      const res = await getDiscoveryRuns(projectId!);
      setRuns(res.data);
    } catch (err: any) {
      console.error(err);
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
      showToast(`Scout search initiated across a ${formRadius} km radius!`, 'info');

      setRuns(prev => [res.data, ...prev.filter(r => r.id !== res.data.id)]);
      setTimeout(() => {
        loadRuns();
        loadCandidates();
      }, 800);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to start discovery');
      showToast(err.response?.data?.detail || 'Failed to start discovery', 'error');
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleSelect = async (candidateId: string) => {
    try {
      await selectDiscoveryCandidate(projectId!, candidateId);
      showToast('Competitor added to project! Scraping starts on the Scraping page.', 'success');
      setCandidates(prev =>
        prev.map(c => (c.id === candidateId ? { ...c, status: 'SELECTED' } : c))
      );
      setSelectedIds(prev => {
        const next = new Set(prev);
        next.delete(candidateId);
        return next;
      });
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Failed to select candidate', 'error');
    }
  };

  const handleReject = async (candidateId: string) => {
    try {
      await rejectDiscoveryCandidate(projectId!, candidateId);
      showToast('Candidate dismissed.', 'info');
      setCandidates(prev =>
        prev.map(c => (c.id === candidateId ? { ...c, status: 'REJECTED' } : c))
      );
      setSelectedIds(prev => {
        const next = new Set(prev);
        next.delete(candidateId);
        return next;
      });
    } catch (err: any) {
      showToast('Failed to reject candidate', 'error');
    }
  };

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

  const newCandidates = useMemo(() => candidates.filter(c => c.status === 'NEW'), [candidates]);

  const handleToggleSelectAllNew = () => {
    if (selectedIds.size === newCandidates.length && newCandidates.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(newCandidates.map(c => c.id)));
    }
  };

  const handleBulkSelect = async () => {
    if (selectedIds.size === 0) return;
    try {
      setBulkSubmitting(true);
      const ids = Array.from(selectedIds);
      await bulkSelectDiscoveryCandidates(projectId!, ids);
      showToast(`Successfully added ${ids.length} competitors to roster!`, 'success');
      setCandidates(prev =>
        prev.map(c => (ids.includes(c.id) ? { ...c, status: 'SELECTED' } : c))
      );
      setSelectedIds(new Set());
    } catch (err: any) {
      showToast('Failed to select competitors in bulk', 'error');
    } finally {
      setBulkSubmitting(false);
    }
  };

  const handleBulkReject = async () => {
    if (selectedIds.size === 0) return;
    try {
      setBulkSubmitting(true);
      const ids = Array.from(selectedIds);
      await bulkRejectDiscoveryCandidates(projectId!, ids);
      showToast(`Dismissed ${ids.length} candidates.`, 'info');
      setCandidates(prev =>
        prev.map(c => (ids.includes(c.id) ? { ...c, status: 'REJECTED' } : c))
      );
      setSelectedIds(new Set());
    } catch (err: any) {
      showToast('Failed to reject candidates', 'error');
    } finally {
      setBulkSubmitting(false);
    }
  };

  // Filtered candidate list
  const filteredCandidates = useMemo(() => {
    return candidates.filter(cand => {
      if (statusFilter !== 'ALL' && cand.status !== statusFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = (cand.business_name || '').toLowerCase().includes(q);
        const matchesAddress = (cand.address || '').toLowerCase().includes(q);
        const matchesCat = (cand.category || '').toLowerCase().includes(q);
        if (!matchesName && !matchesAddress && !matchesCat) return false;
      }
      return true;
    });
  }, [candidates, statusFilter, searchQuery]);

  // Counts for filter pills
  const counts = useMemo(() => {
    return {
      all: candidates.length,
      new: candidates.filter(c => c.status === 'NEW').length,
      selected: candidates.filter(c => c.status === 'SELECTED').length,
      already: candidates.filter(c => c.status === 'ALREADY_COMPETITOR').length,
      rejected: candidates.filter(c => c.status === 'REJECTED').length,
    };
  }, [candidates]);

  const activeRun = runs.find(r => r.status === 'RUNNING' || r.status === 'QUEUED');

  return (
    <AppLayout projectId={projectId}>
      {/* Top Header */}
      <header className="topbar discovery-topbar">
        <div className="topbar-left">
          <div className="topbar-title-row">
            <h1>Discovery Scout</h1>
            <span className="status-pill status-purple">
              <Compass size={13} /> Google Places Scout
            </span>
          </div>
          <p className="discovery-header-subtitle">
            Find and select competitors in your target radius. Scraping posts and customer reviews happens separately on the Scraping page.
          </p>
        </div>
        <div className="topbar-actions">
          <button
            className="secondary-btn"
            onClick={() => { loadRuns(); loadCandidates(); }}
            title="Refresh candidate list"
          >
            <RefreshCw size={15} className={loadingCandidates ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
          <button
            className="secondary-btn"
            onClick={() => navigate(`/projects/${projectId}/competitors`)}
          >
            <Users size={15} />
            <span>Roster</span>
          </button>
          <button
            className="primary-btn"
            onClick={() => setShowDiscoveryForm(!showDiscoveryForm)}
          >
            <Search size={15} />
            <span>{showDiscoveryForm ? 'Close Search' : 'New Scout Search'}</span>
          </button>
        </div>
      </header>

      <div className="content-area">
        {/* Decoupling Explanation Banner */}
        <div className="pipeline-banner discovery">
          <Info size={20} className="banner-icon" />
          <div className="banner-content">
            <strong>Candidate Scouting (Decoupled from Scraping):</strong> This tool scouts Google Maps for businesses within your selected radius. Selecting a business adds it to your <strong>Competitor Roster</strong>. Post and review collection will strictly wait until you trigger a run on the <button onClick={() => navigate(`/projects/${projectId}/scraping`)} className="banner-link">Scraping Pipeline page <ArrowRight size={12} /></button>.
          </div>
        </div>

        {/* Real-time Active Scout Radar */}
        {activeRun && (
          <div className="active-scout-card animate-slide-in">
            <div className="radar-spinner">
              <div className="radar-circle"></div>
              <Compass size={24} className="radar-icon pulse" />
            </div>
            <div className="active-scout-details">
              <div className="active-scout-header">
                <span className="status-pill status-running">
                  <span className="pulse-dot running"></span>
                  SCANNING GOOGLE MAPS
                </span>
                <span className="active-scout-query">"{activeRun.query || 'Nearby Competitors'}"</span>
              </div>
              <p className="active-scout-sub">
                Searching within <strong>{activeRun.radius || 10} km radius</strong> for businesses. Candidates will populate automatically below.
              </p>
            </div>
          </div>
        )}

        {/* Discovery Search Form Modal/Collapsible */}
        {showDiscoveryForm && (
          <div className="discovery-search-panel animate-slide-in">
            <div className="search-panel-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Sliders size={18} className="text-primary" />
                <h3>Scout Radius & Search Parameters</h3>
              </div>
              <button
                className="close-panel-btn"
                onClick={() => setShowDiscoveryForm(false)}
                aria-label="Close search form"
              >
                <X size={18} />
              </button>
            </div>

            {formError && (
              <div className="error-banner">
                <Info size={16} />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleStartDiscovery} className="scout-form">
              <div className="form-grid">
                <div className="form-field">
                  <label>Search Query / Keyword</label>
                  <input
                    type="text"
                    value={formQuery}
                    onChange={e => setFormQuery(e.target.value)}
                    placeholder="e.g. bakeries, artisanal cafes, sweet shops"
                    required
                  />
                  <span className="field-hint">Business type or keywords to find on Google Maps</span>
                </div>

                <div className="form-field">
                  <label>Location / Landmark (Optional)</label>
                  <input
                    type="text"
                    value={formLocation}
                    onChange={e => setFormLocation(e.target.value)}
                    placeholder="e.g. Bandra West, Mumbai"
                  />
                  <span className="field-hint">Defaults to project location if omitted</span>
                </div>
              </div>

              {/* Radius in Kilometers Picker */}
              <div className="radius-selector-box">
                <div className="radius-header">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <MapPin size={16} className="text-primary" />
                    <span>Search Range (Radius in Kilometers)</span>
                  </label>
                  <span className="radius-val-badge">{formRadius} km</span>
                </div>

                <div className="radius-presets">
                  {radiusPresets.map(preset => (
                    <button
                      type="button"
                      key={preset}
                      className={`preset-btn ${formRadius === preset ? 'active' : ''}`}
                      onClick={() => setFormRadius(preset)}
                    >
                      {preset} km
                    </button>
                  ))}
                </div>

                <div className="radius-slider-wrap">
                  <input
                    type="range"
                    min="1"
                    max="50"
                    step="1"
                    value={formRadius}
                    onChange={e => setFormRadius(Number(e.target.value))}
                    className="modern-range-slider"
                  />
                  <div className="slider-labels">
                    <span>1 km</span>
                    <span>10 km</span>
                    <span>25 km</span>
                    <span>50 km</span>
                  </div>
                </div>
              </div>

              <div className="form-actions-row">
                <button
                  type="button"
                  className="secondary-btn"
                  onClick={() => setShowDiscoveryForm(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="primary-btn"
                  disabled={formSubmitting}
                >
                  <Search size={16} />
                  <span>{formSubmitting ? 'Scouting Google Maps...' : `Search within ${formRadius} km`}</span>
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Candidate Controls: Status Tabs & Quick Search */}
        <div className="candidate-controls-bar">
          <div className="status-tabs">
            <button
              className={`tab-btn ${statusFilter === 'ALL' ? 'active' : ''}`}
              onClick={() => setStatusFilter('ALL')}
            >
              All ({counts.all})
            </button>
            <button
              className={`tab-btn ${statusFilter === 'NEW' ? 'active' : ''}`}
              onClick={() => setStatusFilter('NEW')}
            >
              New Candidates ({counts.new})
            </button>
            <button
              className={`tab-btn ${statusFilter === 'SELECTED' ? 'active' : ''}`}
              onClick={() => setStatusFilter('SELECTED')}
            >
              Selected ({counts.selected})
            </button>
            <button
              className={`tab-btn ${statusFilter === 'ALREADY_COMPETITOR' ? 'active' : ''}`}
              onClick={() => setStatusFilter('ALREADY_COMPETITOR')}
            >
              In Roster ({counts.already})
            </button>
            <button
              className={`tab-btn ${statusFilter === 'REJECTED' ? 'active' : ''}`}
              onClick={() => setStatusFilter('REJECTED')}
            >
              Dismissed ({counts.rejected})
            </button>
          </div>

          <div className="filter-search-wrap">
            <Search size={15} className="search-icon" />
            <input
              type="text"
              placeholder="Filter candidates..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="quick-search-input"
            />
            {searchQuery && (
              <button
                className="clear-search-btn"
                onClick={() => setSearchQuery('')}
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Quick Multi-Select Header (when NEW candidates available) */}
        {newCandidates.length > 0 && statusFilter !== 'SELECTED' && statusFilter !== 'ALREADY_COMPETITOR' && (
          <div className="multi-select-header">
            <button
              className="select-all-btn"
              onClick={handleToggleSelectAllNew}
            >
              {selectedIds.size === newCandidates.length && newCandidates.length > 0 ? (
                <CheckSquare size={16} className="text-primary" />
              ) : (
                <Square size={16} />
              )}
              <span>
                {selectedIds.size === newCandidates.length && newCandidates.length > 0
                  ? 'Deselect All New'
                  : `Select All New (${newCandidates.length})`}
              </span>
            </button>
            {selectedIds.size > 0 && (
              <span className="selected-counter-pill">
                {selectedIds.size} selected
              </span>
            )}
          </div>
        )}

        {/* Candidates List Grid */}
        {loadingCandidates && candidates.length === 0 ? (
          <div className="candidates-loading-grid">
            {[1, 2, 3, 4].map(n => (
              <div key={n} className="candidate-card-skeleton skeleton" style={{ height: '180px' }} />
            ))}
          </div>
        ) : filteredCandidates.length === 0 ? (
          <div className="empty-candidates-card">
            <div className="empty-icon-box">
              <Compass size={32} />
            </div>
            <h3>No Candidates Found</h3>
            <p>
              {candidates.length === 0
                ? 'Launch your first Scout Search to find local competitors on Google Maps.'
                : 'No candidates match your current filter or search criteria.'}
            </p>
            {candidates.length === 0 && (
              <button
                className="primary-btn mt-4"
                onClick={() => setShowDiscoveryForm(true)}
              >
                <Search size={16} />
                <span>Launch Scout Search</span>
              </button>
            )}
          </div>
        ) : (
          <div className="candidates-grid">
            {filteredCandidates.map(cand => {
              const isSelected = selectedIds.has(cand.id);
              const isNew = cand.status === 'NEW';
              const isRoster = cand.status === 'ALREADY_COMPETITOR';
              const isSelectedStatus = cand.status === 'SELECTED';

              return (
                <div
                  key={cand.id}
                  className={`candidate-card ${isSelected ? 'is-selected' : ''} ${!isNew ? 'is-settled' : ''}`}
                  onClick={() => isNew && toggleSelectCandidate(cand.id, cand.status)}
                >
                  <div className="card-top">
                    {/* Checkbox for NEW items */}
                    {isNew && (
                      <div
                        className="custom-checkbox"
                        onClick={e => {
                          e.stopPropagation();
                          toggleSelectCandidate(cand.id, cand.status);
                        }}
                      >
                        {isSelected ? (
                          <CheckSquare size={18} className="checkbox-checked" />
                        ) : (
                          <Square size={18} className="checkbox-empty" />
                        )}
                      </div>
                    )}

                    <div className="business-title-wrap">
                      <h4>{cand.business_name}</h4>
                      {cand.category && (
                        <span className="category-pill">{cand.category}</span>
                      )}
                    </div>

                    {/* Status Pill */}
                    <div className="card-status-slot">
                      {isNew && <span className="status-pill status-queued">NEW</span>}
                      {isSelectedStatus && (
                        <span className="status-pill status-success">
                          <Check size={12} /> ADDED
                        </span>
                      )}
                      {isRoster && (
                        <span className="status-pill status-purple">
                          IN ROSTER
                        </span>
                      )}
                      {cand.status === 'REJECTED' && (
                        <span className="status-pill status-failed">DISMISSED</span>
                      )}
                    </div>
                  </div>

                  {/* Badges: Rating & Distance */}
                  <div className="candidate-badges-row">
                    {cand.distance_km != null && (
                      <span className="distance-badge">
                        <MapPin size={12} /> {cand.distance_km} km away
                      </span>
                    )}
                    {cand.rating != null && (
                      <span className="rating-badge">
                        <Star size={12} className="star-icon" />
                        <strong>{cand.rating.toFixed(1)}</strong>
                        <span className="review-count">({cand.review_count || 0})</span>
                      </span>
                    )}
                  </div>

                  {/* Address */}
                  {cand.address && (
                    <p className="candidate-address" title={cand.address}>
                      {cand.address}
                    </p>
                  )}

                  {/* External Links */}
                  <div className="candidate-links-row" onClick={e => e.stopPropagation()}>
                    {cand.source_url && (
                      <a
                        href={cand.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="card-ext-link"
                      >
                        Google Maps <ExternalLink size={12} />
                      </a>
                    )}
                    {cand.website && (
                      <a
                        href={cand.website}
                        target="_blank"
                        rel="noreferrer"
                        className="card-ext-link"
                      >
                        Website <ExternalLink size={12} />
                      </a>
                    )}
                  </div>

                  {/* Action Buttons */}
                  {isNew && (
                    <div className="card-actions-row" onClick={e => e.stopPropagation()}>
                      <button
                        className="btn-select-candidate"
                        onClick={() => handleSelect(cand.id)}
                        title="Add to project competitor roster"
                      >
                        <Check size={14} /> Add to Roster
                      </button>
                      <button
                        className="btn-dismiss-candidate"
                        onClick={() => handleReject(cand.id)}
                        title="Dismiss candidate"
                      >
                        <X size={14} /> Dismiss
                      </button>
                    </div>
                  )}

                  {cand.status === 'REJECTED' && (
                    <div className="card-actions-row" onClick={e => e.stopPropagation()}>
                      <button
                        className="btn-reconsider"
                        onClick={() => handleSelect(cand.id)}
                      >
                        + Reconsider & Add
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Sticky Floating Multi-Select Action Bar */}
        {selectedIds.size > 0 && (
          <div className="floating-bulk-bar animate-slide-in">
            <div className="bulk-bar-info">
              <span className="bulk-badge">{selectedIds.size}</span>
              <span className="bulk-label">
                {selectedIds.size === 1 ? '1 competitor' : `${selectedIds.size} competitors`} selected
              </span>
            </div>
            <div className="bulk-bar-actions">
              <button
                className="primary-btn bulk-action-btn"
                onClick={handleBulkSelect}
                disabled={bulkSubmitting}
              >
                <Check size={16} />
                <span>{bulkSubmitting ? 'Adding...' : `Add ${selectedIds.size} to Roster`}</span>
              </button>
              <button
                className="secondary-btn bulk-dismiss-btn"
                onClick={handleBulkReject}
                disabled={bulkSubmitting}
              >
                <X size={15} />
                <span>Dismiss</span>
              </button>
              <button
                className="bulk-cancel-btn"
                onClick={() => setSelectedIds(new Set())}
                disabled={bulkSubmitting}
              >
                Clear
              </button>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default ProjectDiscovery;
