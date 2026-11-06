import { useCallback, useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { getDiscoveryRuns, startDiscovery, getDiscoveryCandidates, selectDiscoveryCandidate, rejectDiscoveryCandidate } from '../api';
import type { DiscoveryRun, DiscoveryCandidate } from '../api';
import './ProjectDiscovery.css';

const ProjectDiscovery = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  
  const [runs, setRuns] = useState<DiscoveryRun[]>([]);
  const [candidates, setCandidates] = useState<DiscoveryCandidate[]>([]);
  
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  // Removed unused error state
  
  // Discovery Form State
  const [showDiscoveryForm, setShowDiscoveryForm] = useState(false);
  const [formQuery, setFormQuery] = useState('');
  const [formLocation, setFormLocation] = useState('');
  const [formCategory, setFormCategory] = useState('');
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  const loadRuns = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await getDiscoveryRuns(projectId);
      setRuns(res.data);
    } catch {
      setFormError('Failed to load discovery runs');
    } finally {
      setLoadingRuns(false);
    }
  }, [projectId]);

  const loadCandidates = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await getDiscoveryCandidates(projectId, 0, 100);
      setCandidates(res.data);
    } catch {
      setFormError('Failed to load discovery candidates');
    } finally {
      setLoadingCandidates(false);
    }
  }, [projectId]);

  useEffect(() => {
    // Async external-data synchronization; state updates occur after awaited requests.
    // oxlint-disable-next-line react/set-state-in-effect
    void loadRuns();
    void loadCandidates();
  }, [loadRuns, loadCandidates]);

  const handleStartDiscovery = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setFormSubmitting(true);
      setFormError('');
      await startDiscovery(projectId!, {
        query: formQuery.trim() || undefined,
        location: formLocation.trim() || undefined,
        category: formCategory.trim() || undefined,
        radius: 50, // default
      });
      setShowDiscoveryForm(false);
      setFormQuery('');
      setFormLocation('');
      setFormCategory('');
      await loadRuns();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to start discovery');
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleSelect = async (candidateId: string) => {
    try {
      await selectDiscoveryCandidate(projectId!, candidateId);
      await loadCandidates(); // Refresh candidate statuses
    } catch {
      alert('Failed to select candidate.');
    }
  };

  const handleReject = async (candidateId: string) => {
    try {
      await rejectDiscoveryCandidate(projectId!, candidateId);
      await loadCandidates(); // Refresh candidate statuses
    } catch {
      alert('Failed to reject candidate.');
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch(status) {
      case 'QUEUED': return 'badge-queued';
      case 'RUNNING': return 'badge-running';
      case 'SUCCESS': return 'badge-success';
      case 'PARTIAL_SUCCESS': return 'badge-warning';
      case 'FAILED': return 'badge-failed';
      case 'PAUSED_MANUAL_INTERVENTION': return 'badge-warning';
      default: return 'badge-default';
    }
  };

  const getCandidateBadgeClass = (status: string) => {
    switch(status) {
      case 'NEW': return 'badge-new';
      case 'SELECTED': return 'badge-selected';
      case 'REJECTED': return 'badge-rejected';
      case 'ALREADY_COMPETITOR': return 'badge-already';
      default: return 'badge-default';
    }
  };

  return (
    <AppLayout projectId={projectId}>
      <header className="topbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Discovery ({candidates.filter(c => c.status === 'NEW').length} New)</h1>
        <div style={{ display: 'flex', gap: '16px' }}>
          <button className="secondary-btn" onClick={() => navigate(`/projects/${projectId}/competitors`)}>
            View Competitors
          </button>
          <button className="primary-btn" onClick={() => setShowDiscoveryForm(!showDiscoveryForm)}>
            {showDiscoveryForm ? 'Cancel Discovery' : 'New Discovery'}
          </button>
        </div>
      </header>

      <div className="content-area">
        {showDiscoveryForm && (
          <div className="form-container mb-6">
            <h2>Start Discovery Run</h2>
            <p className="form-subtitle">Find new competitors automatically in your target area.</p>
            {formError && <div className="state-message error">{formError}</div>}
            
            <form onSubmit={handleStartDiscovery} className="create-form">
              <div className="form-group">
                <label>Query / Keywords</label>
                <input
                  type="text"
                  value={formQuery}
                  onChange={e => setFormQuery(e.target.value)}
                  placeholder="e.g. coffee shops near me"
                />
              </div>
              <div className="form-group">
                <label>Location (Optional)</label>
                <input
                  type="text"
                  value={formLocation}
                  onChange={e => setFormLocation(e.target.value)}
                  placeholder="e.g. Seattle, WA"
                />
              </div>
              <div className="form-group">
                <label>Category (Optional)</label>
                <input
                  type="text"
                  value={formCategory}
                  onChange={e => setFormCategory(e.target.value)}
                  placeholder="e.g. Cafe"
                />
              </div>
              <div className="form-actions" style={{ marginTop: '16px' }}>
                <button type="submit" className="primary-btn" disabled={formSubmitting}>
                  {formSubmitting ? 'Starting...' : 'Start Discovery'}
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="discovery-layout">
          <div className="runs-column">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 className="section-title">Runs History</h2>
              <button className="icon-btn" onClick={loadRuns} title="Refresh Runs">&#x21bb;</button>
            </div>
            {loadingRuns && <div className="state-message">Loading runs...</div>}
            {!loadingRuns && runs.length === 0 && (
              <div className="empty-state-small">No discovery runs yet.</div>
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
                  </div>
                  <div className="run-stats">
                    <span>{run.total_candidates} Found</span>
                    <span>{run.duplicates_skipped} Skipped</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          <div className="candidates-column">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 className="section-title">Candidates</h2>
              <button className="icon-btn" onClick={loadCandidates} title="Refresh Candidates">&#x21bb;</button>
            </div>
            
            {loadingCandidates && <div className="state-message">Loading candidates...</div>}
            {!loadingCandidates && candidates.length === 0 && (
              <div className="empty-state">No discovery candidates found.</div>
            )}
            
            <div className="candidates-list">
              {candidates.map(cand => (
                <div key={cand.id} className="candidate-card">
                  <div className="candidate-info">
                    <h3>{cand.business_name}</h3>
                    {cand.category && <span className="category-badge">{cand.category}</span>}
                    <div className="candidate-meta">
                      {cand.address && <span>{cand.address}</span>}
                      {cand.rating && <span>&bull; {cand.rating} &#9733; ({cand.review_count || 0})</span>}
                    </div>
                    {cand.website && (
                      <a href={cand.website} target="_blank" rel="noreferrer" className="maps-link">
                        Website &rarr;
                      </a>
                    )}
                  </div>
                  <div className="candidate-actions">
                    <div className={`status-badge ${getCandidateBadgeClass(cand.status)}`} style={{marginBottom: '12px', textAlign: 'center'}}>
                      {cand.status.replace(/_/g, ' ')}
                    </div>
                    
                    {cand.status === 'NEW' && (
                      <div className="action-buttons">
                        <button className="primary-btn-sm" onClick={() => handleSelect(cand.id)}>Select</button>
                        <button className="secondary-btn-sm" onClick={() => handleReject(cand.id)}>Reject</button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default ProjectDiscovery;
