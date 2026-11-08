import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { getProjectSummary } from '../api';
import {
  Compass,
  Users,
  Database,
  FileText,
  MessageSquareHeart,
  Sparkles,
  Target,
  Wand2,
  RefreshCw
} from 'lucide-react';
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
        <div className="content-area">
          <div className="state-message">Loading project command center...</div>
        </div>
      </AppLayout>
    );
  }

  if (error || !summary) {
    return (
      <AppLayout projectId={projectId}>
        <div className="content-area">
          <div className="error-banner">{error || 'Project not found'}</div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout projectId={projectId} projectName={summary.project.name}>
      {/* Top Header */}
      <header className="topbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1>{summary.project.name}</h1>
            <span className="status-pill status-purple">Active Project</span>
          </div>
          {summary.project.description ? (
            <p className="discovery-header-subtitle">{summary.project.description}</p>
          ) : (
            <p className="discovery-header-subtitle">Google Maps Competitor Intelligence & Studio</p>
          )}
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button className="secondary-btn" onClick={() => loadSummary(projectId!)}>
            <RefreshCw size={15} />
            <span>Refresh</span>
          </button>
          <Link to={`/projects/${projectId}/discovery`} className="secondary-btn">
            <Compass size={15} />
            <span>Discovery Scout</span>
          </Link>
          <Link to={`/projects/${projectId}/scraping`} className="primary-btn">
            <Database size={15} />
            <span>Scraping Pipeline</span>
          </Link>
        </div>
      </header>

      <div className="content-area">
        {/* Step-by-Step Guided Workflow Banner */}
        <div className="workflow-stepper-card">
          <div className="workflow-stepper-header">
            <span className="stepper-title">COMPETITIVE INTELLIGENCE JOURNEY</span>
            <span className="stepper-sub">4-Step Automated Intelligence Pipeline</span>
          </div>
          <div className="workflow-steps-grid">
            <Link to={`/projects/${projectId}/discovery`} className="workflow-step-box">
              <div className="step-num-badge">1</div>
              <div className="step-content">
                <strong>Scout Competitors</strong>
                <span>Search Google Maps by km radius</span>
              </div>
            </Link>

            <Link to={`/projects/${projectId}/competitors`} className="workflow-step-box">
              <div className="step-num-badge">2</div>
              <div className="step-content">
                <strong>Confirm Roster</strong>
                <span>Set your business & competitors</span>
              </div>
            </Link>

            <Link to={`/projects/${projectId}/scraping`} className="workflow-step-box">
              <div className="step-num-badge">3</div>
              <div className="step-content">
                <strong>Scrape Data</strong>
                <span>Collect posts & customer reviews</span>
              </div>
            </Link>

            <Link to={`/projects/${projectId}/strategy`} className="workflow-step-box">
              <div className="step-num-badge">4</div>
              <div className="step-content">
                <strong>Synthesize & Create</strong>
                <span>Identify gaps & generate content</span>
              </div>
            </Link>
          </div>
        </div>

        {/* High Level Key Metrics */}
        <div className="stats-grid mt-6">
          <div className="stat-card">
            <div className="stat-card-header">
              <Users size={18} className="text-primary" />
              <span className="stat-label">Competitors Roster</span>
            </div>
            <div className="stat-value">{summary.competitor_count}</div>
            <span className="stat-foot">Tracked businesses</span>
          </div>

          <div className="stat-card">
            <div className="stat-card-header">
              <FileText size={18} style={{ color: '#38bdf8' }} />
              <span className="stat-label">Business Posts</span>
            </div>
            <div className="stat-value" style={{ color: '#38bdf8' }}>{summary.post_count}</div>
            <span className="stat-foot">Scraped & analyzed updates</span>
          </div>

          <div className="stat-card">
            <div className="stat-card-header">
              <MessageSquareHeart size={18} style={{ color: '#a855f7' }} />
              <span className="stat-label">Customer Reviews</span>
            </div>
            <div className="stat-value" style={{ color: '#c084fc' }}>{summary.review_count || 0}</div>
            <span className="stat-foot">Feedback & sentiment records</span>
          </div>

          <div className="stat-card">
            <div className="stat-card-header">
              <Wand2 size={18} style={{ color: '#ec4899' }} />
              <span className="stat-label">Content Generated</span>
            </div>
            <div className="stat-value" style={{ color: '#f472b6' }}>{summary.generated_content_count}</div>
            <span className="stat-foot">Marketing campaign drafts</span>
          </div>
        </div>

        {/* Feature Modules Grid */}
        <div className="section-title-wrap" style={{ marginTop: '40px', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '20px', margin: 0 }}>Project Intelligence Modules</h2>
          <p style={{ color: '#94a3b8', fontSize: '13.5px', margin: '4px 0 0' }}>
            Jump into specialized intelligence, analytics, and content generation workspaces.
          </p>
        </div>

        <div className="projects-grid">
          <Link to={`/projects/${projectId}/discovery`} className="module-card">
            <div className="module-card-icon" style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8' }}>
              <Compass size={22} />
            </div>
            <div className="module-card-body">
              <div className="module-card-title-row">
                <h3>Discovery Scout</h3>
                <span className="status-pill status-purple">SCOUT</span>
              </div>
              <p>Search Google Maps by range in kilometers, inspect ratings, and add candidates directly to your roster.</p>
              <span className="module-link-arrow">Open Scout &rarr;</span>
            </div>
          </Link>

          <Link to={`/projects/${projectId}/scraping`} className="module-card">
            <div className="module-card-icon" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8' }}>
              <Database size={22} />
            </div>
            <div className="module-card-body">
              <div className="module-card-title-row">
                <h3>Scraping Pipeline</h3>
                <span className="status-pill status-running">DATA</span>
              </div>
              <p>Run automated scrapers for all tracked competitors to extract both promotional posts and customer reviews.</p>
              <span className="module-link-arrow">Open Pipeline &rarr;</span>
            </div>
          </Link>

          <Link to={`/projects/${projectId}/intelligence`} className="module-card">
            <div className="module-card-icon" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#a855f7' }}>
              <Sparkles size={22} />
            </div>
            <div className="module-card-body">
              <div className="module-card-title-row">
                <h3>Combined Intelligence</h3>
                <span className="status-pill status-purple">AI INSIGHT</span>
              </div>
              <p>Compare marketing promises with authentic customer reviews to uncover market gaps and competitor vulnerabilities.</p>
              <span className="module-link-arrow">Open Combined Intel &rarr;</span>
            </div>
          </Link>

          <Link to={`/projects/${projectId}/strategy`} className="module-card">
            <div className="module-card-icon" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
              <Target size={22} />
            </div>
            <div className="module-card-body">
              <div className="module-card-title-row">
                <h3>Content Strategy Gaps</h3>
                <span className="status-pill status-warning">STRATEGY</span>
              </div>
              <p>Detect high-leverage topic, keyword, and format gaps where competitors post frequently but you do not.</p>
              <span className="module-link-arrow">Open Strategy &rarr;</span>
            </div>
          </Link>

          <Link to={`/projects/${projectId}/posts`} className="module-card">
            <div className="module-card-icon" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
              <FileText size={22} />
            </div>
            <div className="module-card-body">
              <div className="module-card-title-row">
                <h3>Business Posts Repository</h3>
                <span className="status-pill status-success">POSTS</span>
              </div>
              <p>Inspect extracted competitor updates, captions, media links, and AI topic tags with instant search & filters.</p>
              <span className="module-link-arrow">View Posts &rarr;</span>
            </div>
          </Link>

          <Link to={`/projects/${projectId}/generate`} className="module-card">
            <div className="module-card-icon" style={{ background: 'rgba(236, 72, 153, 0.15)', color: '#ec4899' }}>
              <Wand2 size={22} />
            </div>
            <div className="module-card-body">
              <div className="module-card-title-row">
                <h3>AI Content Studio</h3>
                <span className="status-pill status-purple">STUDIO</span>
              </div>
              <p>Turn market opportunities into high-converting social media posts, headlines, and campaigns using Gemini.</p>
              <span className="module-link-arrow">Open Studio &rarr;</span>
            </div>
          </Link>
        </div>
      </div>
    </AppLayout>
  );
};

export default ProjectDashboard;
