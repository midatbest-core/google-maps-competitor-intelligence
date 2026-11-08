import { useState, useEffect } from 'react';
import { getProjects } from '../api';
import { useNavigate } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import {
  FolderPlus,
  Sparkles,
  MapPin,
  RefreshCw
} from 'lucide-react';
import './Dashboard.css';

interface Project {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
}

const Dashboard = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      setLoading(true);
      const res = await getProjects();
      setProjects(res.data);
    } catch (err) {
      setError('Unable to load projects. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppLayout>
      <header className="topbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Workspace Dashboard</h1>
          <p className="discovery-header-subtitle">Manage your competitor intelligence projects and marketing studios.</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="secondary-btn" onClick={loadProjects}>
            <RefreshCw size={15} />
            <span>Refresh</span>
          </button>
          <button className="primary-btn" onClick={() => navigate('/projects/new')}>
            <FolderPlus size={15} />
            <span>New Project</span>
          </button>
        </div>
      </header>

      <div className="content-area">
        {/* Welcome Hero Banner */}
        <div className="workflow-stepper-card mb-6">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
            <Sparkles size={20} className="text-primary" />
            <h2 style={{ margin: 0, fontSize: '20px', color: 'white' }}>Google Maps Competitor Intelligence Platform</h2>
          </div>
          <p style={{ margin: '0 0 16px 0', color: '#94a3b8', fontSize: '14px', lineHeight: '1.5', maxWidth: '640px' }}>
            Discover emerging local competitors, extract social posts & customer reviews with Playwright, uncover high-leverage topic gaps, and generate marketing campaigns.
          </p>
          <button className="primary-btn" onClick={() => navigate('/projects/new')}>
            <FolderPlus size={16} />
            <span>Create New Project</span>
          </button>
        </div>

        <div className="section-title-wrap" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '18px', margin: 0 }}>Your Projects ({projects.length})</h2>
        </div>

        {loading && (
          <div className="projects-grid">
            {[1, 2, 3].map(n => (
              <div key={n} className="project-card skeleton" style={{ height: '140px' }} />
            ))}
          </div>
        )}

        {error && <div className="error-banner mb-4">{error}</div>}

        {!loading && !error && projects.length === 0 && (
          <div className="empty-state">
            <MapPin size={36} className="text-dim" style={{ marginBottom: '12px' }} />
            <h3>No projects yet</h3>
            <p>Create your first competitor intelligence project to start scouting local markets.</p>
            <button className="primary-btn mt-4" onClick={() => navigate('/projects/new')}>
              <FolderPlus size={16} />
              <span>Create First Project</span>
            </button>
          </div>
        )}

        {!loading && !error && projects.length > 0 && (
          <div className="projects-grid">
            {projects.map(p => (
              <div
                key={p.id}
                className="project-card"
                onClick={() => navigate(`/projects/${p.id}`)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                  <h3 style={{ margin: 0 }}>{p.name}</h3>
                  <span className="status-pill status-purple" style={{ fontSize: '11px' }}>ACTIVE</span>
                </div>
                <p style={{ color: '#94a3b8', fontSize: '13px', lineHeight: '1.5', flex: 1, margin: '0 0 16px 0' }}>
                  {p.description || 'Google Maps competitor tracking & studio.'}
                </p>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 'auto', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                  <span style={{ fontSize: '11.5px', color: '#64748b' }}>ID: {p.id.slice(0, 8)}</span>
                  <span className="module-link-arrow">Open Project &rarr;</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default Dashboard;
