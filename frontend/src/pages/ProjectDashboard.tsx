import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { getProjectSummary } from '../api';
import './Dashboard.css';

interface ProjectSummary {
  project: {
    id: string;
    name: string;
    description?: string;
  };
  competitor_count: number;
  post_count: number;
  review_count?: number;
  generated_content_count: number;
  latest_scrape: string | null;
  latest_scrape_status: string | null;
  discovery_count: number;
}

const ProjectDashboard = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const [summary, setSummary] = useState<ProjectSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (projectId) {
      loadSummary(projectId);
    }
  }, [projectId]);

  const loadSummary = async (id: string) => {
    try {
      setLoading(true);
      const res = await getProjectSummary(id);
      setSummary(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load project summary');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <AppLayout projectId={projectId}>
        <div className="state-message">Loading project dashboard...</div>
      </AppLayout>
    );
  }

  if (error || !summary) {
    return (
      <AppLayout projectId={projectId}>
        <div className="state-message error">{error || 'Project not found'}</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout projectId={projectId}>
      <header className="topbar">
        <div>
          <h1>{summary.project.name}</h1>
          {summary.project.description && (
            <p style={{ color: '#94a3b8', fontSize: '15px', marginTop: '4px' }}>
              {summary.project.description}
            </p>
          )}
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <Link to={`/projects/${projectId}/scraping`} className="btn-secondary" style={{ textDecoration: 'none' }}>
            Run Scraper
          </Link>
          <Link to={`/projects/${projectId}/intelligence`} className="btn-primary" style={{ textDecoration: 'none' }}>
            View Intelligence
          </Link>
        </div>
      </header>

      <div className="content-area">
        <div className="stats-grid mt-6">
          <div className="stat-card">
            <h3>Competitors Monitored</h3>
            <div className="stat-value">{summary.competitor_count}</div>
          </div>
          <div className="stat-card">
            <h3>Posts Synthesized</h3>
            <div className="stat-value">{summary.post_count}</div>
          </div>
          <div className="stat-card">
            <h3>Reviews Collected</h3>
            <div className="stat-value" style={{ color: '#a855f7' }}>{summary.review_count || 0}</div>
          </div>
          <div className="stat-card">
            <h3>Content Generated</h3>
            <div className="stat-value">{summary.generated_content_count}</div>
          </div>
          <div className="stat-card">
            <h3>Latest Scrape Status</h3>
            <div className="stat-value" style={{ fontSize: '16px', marginTop: '16px', color: summary.latest_scrape_status === 'SUCCESS' ? '#34d399' : '#94a3b8' }}>
              {summary.latest_scrape ? summary.latest_scrape_status : 'Never Run'}
            </div>
          </div>
        </div>

        <h2 className="section-title mt-6" style={{ marginTop: '48px' }}>Project Intelligence Modules</h2>
        <div className="projects-grid mt-4">
          <Link to={`/projects/${projectId}/intelligence`} className="project-card" style={{ textDecoration: 'none', borderLeft: '4px solid #3b82f6' }}>
            <h3 style={{ color: '#60a5fa' }}>Combined Intelligence Engine</h3>
            <p>Connect competitor marketing promises with real customer reviews to reveal strategic disconnects and high-leverage opportunities.</p>
          </Link>

          <Link to={`/projects/${projectId}/competitors`} className="project-card" style={{ textDecoration: 'none', borderLeft: '4px solid #10b981' }}>
            <h3 style={{ color: '#34d399' }}>Competitors & Discovery</h3>
            <p>Track direct competitors, resolve canonical Google Maps IDs, and discover emerging local businesses.</p>
          </Link>

          <Link to={`/projects/${projectId}/reviews`} className="project-card" style={{ textDecoration: 'none', borderLeft: '4px solid #a855f7' }}>
            <h3 style={{ color: '#c084fc' }}>Customer Reviews Feed</h3>
            <p>Filter customer complaints, satisfaction patterns, and owner responses across all monitored competitors.</p>
          </Link>

          <Link to={`/projects/${projectId}/posts`} className="project-card" style={{ textDecoration: 'none', borderLeft: '4px solid #38bdf8' }}>
            <h3 style={{ color: '#38bdf8' }}>Business Updates & Posts</h3>
            <p>Analyze competitor promotional posts, CTAs, media, and posting cadence extracted via Playwright.</p>
          </Link>

          <Link to={`/projects/${projectId}/strategy`} className="project-card" style={{ textDecoration: 'none', borderLeft: '4px solid #f59e0b' }}>
            <h3 style={{ color: '#fbbf24' }}>Content Strategy</h3>
            <p>Detect market gaps in topics, keywords, and content formats where competitors are currently underserved.</p>
          </Link>

          <Link to={`/projects/${projectId}/generate`} className="project-card" style={{ textDecoration: 'none', borderLeft: '4px solid #ec4899' }}>
            <h3 style={{ color: '#f472b6' }}>Content Studio</h3>
            <p>Turn synthesized competitor intelligence and customer pain points into high-converting marketing campaigns.</p>
          </Link>
        </div>
      </div>
    </AppLayout>
  );
};

export default ProjectDashboard;
