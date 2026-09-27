import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { getProjectSummary } from '../api';
import './Dashboard.css'; // Reusing dashboard styles

interface ProjectSummary {
  project: {
    id: string;
    name: string;
    description?: string;
  };
  competitor_count: number;
  post_count: number;
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
        <h1>{summary.project.name}</h1>
      </header>
      
      <div className="content-area">
        {summary.project.description && (
          <p style={{ color: '#94a3b8', fontSize: '16px', marginBottom: '24px' }}>
            {summary.project.description}
          </p>
        )}
        
        <div className="stats-grid mt-6">
          <div className="stat-card">
            <h3>Competitors Monitored</h3>
            <div className="stat-value">{summary.competitor_count}</div>
          </div>
          <div className="stat-card">
            <h3>Posts Analyzed</h3>
            <div className="stat-value">{summary.post_count}</div>
          </div>
          <div className="stat-card">
            <h3>Content Generated</h3>
            <div className="stat-value">{summary.generated_content_count}</div>
          </div>
          <div className="stat-card">
            <h3>Discovery Candidates</h3>
            <div className="stat-value">{summary.discovery_count}</div>
          </div>
          <div className="stat-card">
            <h3>Latest Scrape</h3>
            <div className="stat-value" style={{fontSize: '18px', marginTop: '16px'}}>
              {summary.latest_scrape ? summary.latest_scrape_status : 'Never'}
            </div>
          </div>
        </div>

        <h2 className="section-title mt-6" style={{marginTop: '48px'}}>Project Modules</h2>
        <div className="projects-grid mt-4">
          <div className="project-card" style={{cursor: 'default'}}>
            <h3>Competitor Intel</h3>
            <p>This module is being integrated.</p>
          </div>
          <div className="project-card" style={{cursor: 'default'}}>
            <h3>Discovery</h3>
            <p>This module is being integrated.</p>
          </div>
          <div className="project-card" style={{cursor: 'default'}}>
            <h3>Content Studio</h3>
            <p>This module is being integrated.</p>
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default ProjectDashboard;
