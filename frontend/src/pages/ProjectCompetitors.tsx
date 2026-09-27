import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { getProjectCompetitors, addDirectCompetitor, getProjectSummary, updateProject } from '../api';
import type { Competitor } from '../api';
import './ProjectCompetitors.css';

const ProjectCompetitors = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [ownBusinessId, setOwnBusinessId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // Direct Add Form State
  const [showAddForm, setShowAddForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formUrl, setFormUrl] = useState('');
  const [formAddress, setFormAddress] = useState('');
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  useEffect(() => {
    if (projectId) {
      loadData();
    }
  }, [projectId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [compRes, projRes] = await Promise.all([
        getProjectCompetitors(projectId!),
        getProjectSummary(projectId!)
      ]);
      setCompetitors(compRes.data);
      setOwnBusinessId(projRes.data.project.own_business_id || null);
    } catch (err: any) {
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadCompetitors = async () => {
    // legacy method for reloading just competitors if needed, though loadData is preferred now
    try {
      const compRes = await getProjectCompetitors(projectId!);
      setCompetitors(compRes.data);
    } catch (err: any) {
      setError('Failed to load competitors');
    }
  };

  const handleAddDirect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      setFormError('Business name is required');
      return;
    }

    try {
      setFormSubmitting(true);
      setFormError('');
      await addDirectCompetitor(projectId!, {
        business_name: formName.trim(),
        source_url: formUrl.trim() || undefined,
        address: formAddress.trim() || undefined,
      });
      setShowAddForm(false);
      setFormName('');
      setFormUrl('');
      setFormAddress('');
      loadCompetitors();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to add competitor');
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleSetOwnBusiness = async (businessId: string) => {
    try {
      await updateProject(projectId!, { own_business_id: businessId });
      setOwnBusinessId(businessId);
    } catch (err: any) {
      setError('Failed to update own business');
    }
  };

  return (
    <AppLayout projectId={projectId}>
      <header className="topbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Competitors ({competitors.length})</h1>
        <div style={{ display: 'flex', gap: '16px' }}>
          <button className="secondary-btn" onClick={() => setShowAddForm(!showAddForm)}>
            {showAddForm ? 'Cancel Add' : 'Add Direct'}
          </button>
          <button className="primary-btn" onClick={() => navigate(`/projects/${projectId}/discovery`)}>
            Discover
          </button>
        </div>
      </header>

      <div className="content-area">
        {showAddForm && (
          <div className="form-container mb-6">
            <h2>Add Direct Competitor</h2>
            {formError && <div className="state-message error">{formError}</div>}
            <form onSubmit={handleAddDirect} className="create-form">
              <div className="form-group">
                <label>Business Name *</label>
                <input
                  type="text"
                  value={formName}
                  onChange={e => setFormName(e.target.value)}
                  placeholder="e.g. Starbucks"
                  required
                />
              </div>
              <div className="form-group">
                <label>Google Maps URL (Optional)</label>
                <input
                  type="url"
                  value={formUrl}
                  onChange={e => setFormUrl(e.target.value)}
                  placeholder="https://maps.google.com/..."
                />
              </div>
              <div className="form-group">
                <label>Address (Optional)</label>
                <input
                  type="text"
                  value={formAddress}
                  onChange={e => setFormAddress(e.target.value)}
                  placeholder="e.g. 123 Coffee St."
                />
              </div>
              <div className="form-actions" style={{ marginTop: '16px' }}>
                <button type="submit" className="primary-btn" disabled={formSubmitting}>
                  {formSubmitting ? 'Adding...' : 'Add Competitor'}
                </button>
              </div>
            </form>
          </div>
        )}

        {loading && <div className="state-message">Loading competitors...</div>}
        {error && <div className="state-message error">{error}</div>}

        {!loading && !error && competitors.length === 0 && (
          <div className="empty-state">
            <p>No competitors added yet.</p>
            <div style={{ marginTop: '24px', display: 'flex', gap: '16px', justifyContent: 'center' }}>
              <button className="secondary-btn" onClick={() => setShowAddForm(true)}>Add Competitor</button>
              <button className="primary-btn" onClick={() => navigate(`/projects/${projectId}/discovery`)}>Discover Competitors</button>
            </div>
          </div>
        )}

        {!loading && !error && competitors.length > 0 && (
          <div className="competitors-list">
            {competitors.map(c => (
              <div key={c.id} className="competitor-card">
                <div className="competitor-info">
                  <h3>{c.business?.business_name || 'Unknown Business'}</h3>
                  {c.business?.category && <span className="category-badge">{c.business.category}</span>}
                  {c.business?.address && <p className="address">{c.business.address}</p>}
                  {c.business?.google_maps_url && (
                    <a href={c.business.google_maps_url} target="_blank" rel="noreferrer" className="maps-link">
                      View on Maps &rarr;
                    </a>
                  )}
                </div>
                <div className="competitor-status" style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'flex-end' }}>
                  <div>
                    <span className={`status-dot ${c.is_active ? 'active' : 'inactive'}`}></span>
                    {c.is_active ? 'Active' : 'Inactive'}
                  </div>
                  {c.business_id === ownBusinessId ? (
                    <span className="badge" style={{ backgroundColor: '#10b981', color: 'white', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem' }}>Your Business</span>
                  ) : (
                    <button 
                      className="secondary-btn" 
                      style={{ padding: '4px 8px', fontSize: '0.8rem' }}
                      onClick={() => handleSetOwnBusiness(c.business_id)}
                    >
                      Set as My Business
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default ProjectCompetitors;
