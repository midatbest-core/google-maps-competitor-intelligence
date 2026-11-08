import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { useToast } from '../context/ToastContext';
import {
  getProjectCompetitors,
  addDirectCompetitor,
  deleteProjectCompetitor,
  getProjectSummary,
  updateProject,
} from '../api';
import type { Competitor } from '../api';
import {
  Users,
  Compass,
  Database,
  Plus,
  Building2,
  MapPin,
  ExternalLink,
  Check,
  RefreshCw,
  X,
  Trash2
} from 'lucide-react';
import './ProjectCompetitors.css';

const ProjectCompetitors = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [ownBusinessId, setOwnBusinessId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState<string>('');
  const [loading, setLoading] = useState(true);

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
        getProjectSummary(projectId!),
      ]);
      setCompetitors(compRes.data);
      setOwnBusinessId(projRes.data.project.own_business_id || null);
      setProjectName(projRes.data.project.name || '');
    } catch (err: any) {
      showToast('Failed to load competitors', 'error');
    } finally {
      setLoading(false);
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

      showToast(`Added "${formName.trim()}" to competitor roster!`, 'success');
      setShowAddForm(false);
      setFormName('');
      setFormUrl('');
      setFormAddress('');
      await loadData();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to add competitor';
      setFormError(msg);
      showToast(msg, 'error');
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleSetOwnBusiness = async (businessId: string, businessName: string) => {
    try {
      await updateProject(projectId!, { own_business_id: businessId });
      setOwnBusinessId(businessId);
      showToast(`Set "${businessName}" as your primary business!`, 'success');
    } catch (err: any) {
      showToast('Failed to update primary business', 'error');
    }
  };

  const handleRemoveCompetitor = async (competitorId: string, businessName: string, isOwn: boolean) => {
    if (isOwn) {
      const confirm = window.confirm(`"${businessName}" is your designated primary business. Are you sure you want to remove it from the roster?`);
      if (!confirm) return;
    }
    try {
      await deleteProjectCompetitor(projectId!, competitorId);
      showToast(`Removed "${businessName}" from roster`, 'info');
      if (isOwn) {
        setOwnBusinessId(null);
      }
      await loadData();
    } catch (err: any) {
      showToast('Failed to remove competitor from roster', 'error');
    }
  };

  const ownBusiness = competitors.find(c => c.business_id === ownBusinessId);

  return (
    <AppLayout projectId={projectId} projectName={projectName}>
      {/* Top Header */}
      <header className="topbar competitors-topbar">
        <div className="topbar-left">
          <div className="topbar-title-row">
            <h1>Competitor Roster</h1>
            <span className="status-pill status-purple">
              <Users size={13} /> {competitors.length} Tracked
            </span>
          </div>
          <p className="competitors-header-subtitle">
            Manage your project roster, designate your business, and add direct competitors.
          </p>
        </div>

        <div className="topbar-actions">
          <button className="secondary-btn" onClick={loadData} title="Refresh roster">
            <RefreshCw size={15} />
            <span>Refresh</span>
          </button>
          <button
            className="secondary-btn"
            onClick={() => setShowAddForm(!showAddForm)}
          >
            <Plus size={15} />
            <span>{showAddForm ? 'Cancel Add' : 'Add Direct'}</span>
          </button>
          <button
            className="primary-btn"
            onClick={() => navigate(`/projects/${projectId}/discovery`)}
          >
            <Compass size={15} />
            <span>Discover More</span>
          </button>
        </div>
      </header>

      <div className="content-area">
        {/* Roster Metrics Banner */}
        <div className="roster-metrics-grid">
          <div className="roster-metric-card">
            <span className="metric-title">Total in Roster</span>
            <span className="metric-number">{competitors.length}</span>
            <span className="metric-desc">Businesses registered in project</span>
          </div>

          <div className="roster-metric-card highlight-card">
            <span className="metric-title">Your Primary Business</span>
            <span className="metric-number text-accent">
              {ownBusiness?.business?.business_name || 'Not Designated'}
            </span>
            <span className="metric-desc">
              {ownBusiness ? 'Used as reference for topic gaps' : 'Select a business below to designate'}
            </span>
          </div>

          <div className="roster-metric-card action-card">
            <span className="metric-title">Next Step: Data Collection</span>
            <button
              className="primary-btn mt-2"
              onClick={() => navigate(`/projects/${projectId}/scraping`)}
            >
              <Database size={15} />
              <span>Go to Scraping Pipeline</span>
            </button>
          </div>
        </div>

        {/* Direct Add Form Collapsible */}
        {showAddForm && (
          <div className="direct-add-card animate-slide-in">
            <div className="direct-add-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Plus size={18} className="text-primary" />
                <h3>Add Direct Competitor</h3>
              </div>
              <button
                className="close-panel-btn"
                onClick={() => setShowAddForm(false)}
                aria-label="Close add form"
              >
                <X size={18} />
              </button>
            </div>

            {formError && (
              <div className="error-banner">
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleAddDirect} className="direct-add-form">
              <div className="form-grid">
                <div className="form-field">
                  <label>Business Name *</label>
                  <input
                    type="text"
                    value={formName}
                    onChange={e => setFormName(e.target.value)}
                    placeholder="e.g. Starbucks, The Daily Cafe"
                    required
                  />
                </div>
                <div className="form-field">
                  <label>Google Maps URL (Optional)</label>
                  <input
                    type="url"
                    value={formUrl}
                    onChange={e => setFormUrl(e.target.value)}
                    placeholder="https://maps.google.com/..."
                  />
                </div>
              </div>

              <div className="form-field mt-3">
                <label>Address (Optional)</label>
                <input
                  type="text"
                  value={formAddress}
                  onChange={e => setFormAddress(e.target.value)}
                  placeholder="e.g. 123 Main St, Bandra West"
                />
              </div>

              <div className="form-actions-row mt-4">
                <button
                  type="button"
                  className="secondary-btn"
                  onClick={() => setShowAddForm(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="primary-btn"
                  disabled={formSubmitting}
                >
                  <Plus size={16} />
                  <span>{formSubmitting ? 'Adding...' : 'Add to Roster'}</span>
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Competitor List */}
        {loading && competitors.length === 0 ? (
          <div className="roster-grid">
            {[1, 2, 3, 4].map(n => (
              <div key={n} className="roster-card-skeleton skeleton" style={{ height: '140px' }} />
            ))}
          </div>
        ) : competitors.length === 0 ? (
          <div className="empty-roster-card">
            <div className="empty-icon-box">
              <Users size={32} />
            </div>
            <h3>No Competitors in Roster</h3>
            <p>
              Scout new local businesses on Google Maps or add known businesses directly.
            </p>
            <div className="empty-actions-row">
              <button
                className="primary-btn"
                onClick={() => navigate(`/projects/${projectId}/discovery`)}
              >
                <Compass size={16} />
                <span>Discover Competitors</span>
              </button>
              <button
                className="secondary-btn"
                onClick={() => setShowAddForm(true)}
              >
                <Plus size={16} />
                <span>Add Direct</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="roster-grid">
            {competitors.map(c => {
              const isOwn = c.business_id === ownBusinessId;
              const name = c.business?.business_name || 'Unknown Business';

              return (
                <div
                  key={c.id}
                  className={`roster-card ${isOwn ? 'is-own-business' : ''}`}
                >
                  <div className="roster-card-top">
                    <div className="business-avatar">
                      <Building2 size={18} />
                    </div>
                    <div className="roster-name-col">
                      <h4>{name}</h4>
                      {c.business?.category && (
                        <span className="category-pill">{c.business.category}</span>
                      )}
                    </div>
                    {isOwn && (
                      <span className="status-pill status-success">
                        <Check size={12} /> YOUR BUSINESS
                      </span>
                    )}
                  </div>

                  {c.business?.address && (
                    <p className="roster-address" title={c.business.address}>
                      <MapPin size={13} className="pin-icon" />
                      <span>{c.business.address}</span>
                    </p>
                  )}

                  <div className="roster-card-footer">
                    {c.business?.google_maps_url ? (
                      <a
                        href={c.business.google_maps_url}
                        target="_blank"
                        rel="noreferrer"
                        className="card-ext-link"
                      >
                        Google Maps <ExternalLink size={12} />
                      </a>
                    ) : (
                      <span className="text-dim" style={{ fontSize: '12px' }}>No Maps Link</span>
                    )}

                    <div className="roster-actions-group">
                      {!isOwn && (
                        <button
                          className="btn-set-own"
                          onClick={() => handleSetOwnBusiness(c.business_id, name)}
                          title="Set this profile as your primary business"
                        >
                          Set as My Business
                        </button>
                      )}
                      <button
                        className="btn-remove-roster"
                        onClick={() => handleRemoveCompetitor(c.id, name, isOwn)}
                        title="Remove competitor from project roster"
                      >
                        <Trash2 size={13} />
                        <span>Remove</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default ProjectCompetitors;
