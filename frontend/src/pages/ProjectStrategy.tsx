import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { useToast } from '../context/ToastContext';
import { getAnalyticsSummary } from '../api';
import type { AnalyticsSummaryResponse, DetailedTopicGap, DetailedKeywordGap, DetailedContentTypeGap } from '../api';
import {
  Target,
  Wand2,
  Sparkles,
  TrendingUp,
  Layers,
  Key,
  RefreshCw,
  Info
} from 'lucide-react';
import './ProjectStrategy.css';

const ProjectStrategy: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [analytics, setAnalytics] = useState<AnalyticsSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (projectId) {
      loadData();
    }
  }, [projectId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await getAnalyticsSummary(projectId!);
      setAnalytics(res.data);
    } catch (err: unknown) {
      setError('Failed to load content strategy.');
      showToast('Failed to load content strategy analytics', 'error');
    } finally {
      setLoading(false);
    }
  };

  const navigateToGenerate = (type: string, value: string) => {
    const params = new URLSearchParams();
    params.set(type, value);
    showToast(`Pre-filling AI Generator with: "${value}"`, 'info');
    navigate(`/projects/${projectId}/generate?${params.toString()}`);
  };

  if (loading) {
    return (
      <AppLayout projectId={projectId}>
        <div className="strategy-container">
          <div className="state-message">Analyzing competitor intelligence & gaps...</div>
        </div>
      </AppLayout>
    );
  }

  if (error) {
    return (
      <AppLayout projectId={projectId}>
        <div className="strategy-container">
          <div className="error-banner">{error}</div>
        </div>
      </AppLayout>
    );
  }

  if (!analytics) {
    return (
      <AppLayout projectId={projectId}>
        <div className="strategy-container">
          <div className="empty-state">No strategy data available.</div>
        </div>
      </AppLayout>
    );
  }

  const { detailed_topic_gaps, detailed_keyword_gaps, detailed_content_type_gaps } = analytics;

  return (
    <AppLayout projectId={projectId}>
      <header className="topbar strategy-topbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1>Content Strategy & Market Gaps</h1>
            <span className="status-pill status-purple">
              <Target size={13} /> Competitive Opportunities
            </span>
          </div>
          <p className="discovery-header-subtitle">
            Actionable content opportunities identified by analyzing competitor behavior versus your business.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="secondary-btn" onClick={loadData}>
            <RefreshCw size={15} />
            <span>Refresh</span>
          </button>
          <Link to={`/projects/${projectId}/intelligence`} className="primary-btn" style={{ textDecoration: 'none' }}>
            <Sparkles size={15} />
            <span>Combined Intelligence →</span>
          </Link>
        </div>
      </header>

      <div className="content-area strategy-content-wrap">
        <div className="strategy-sections">
          {/* Topic Opportunities */}
          <section className="opportunity-section">
            <div className="section-title-wrap">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <TrendingUp size={20} className="text-primary" />
                <h3>Topic Opportunities</h3>
              </div>
              <p className="section-desc">Topics your competitors post about frequently, but you do not.</p>
            </div>

            {detailed_topic_gaps && detailed_topic_gaps.length > 0 ? (
              <div className="opportunity-grid">
                {detailed_topic_gaps.map((gap: DetailedTopicGap, i: number) => (
                  <div key={i} className="opportunity-card">
                    <div className="opportunity-header">
                      <h4>{gap.topic}</h4>
                      <span className="gap-score">Gap: {gap.gap_score.toFixed(1)}x</span>
                    </div>
                    <div className="opportunity-stats">
                      <span>Competitors: <strong>{gap.competitor_frequency}</strong></span>
                      <span>You: <strong>{gap.project_frequency}</strong></span>
                    </div>
                    <button className="primary-btn generate-btn" onClick={() => navigateToGenerate('topic', gap.topic)}>
                      <Wand2 size={14} /> Generate Idea
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <Info size={24} style={{ marginBottom: '8px', color: '#94a3b8' }} />
                <p>No significant topic gaps detected yet. Collect more competitor data via the Scraping Pipeline.</p>
              </div>
            )}
          </section>

          {/* Keyword Opportunities */}
          <section className="opportunity-section">
            <div className="section-title-wrap">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Key size={20} className="text-primary" />
                <h3>Keyword Opportunities</h3>
              </div>
              <p className="section-desc">Keywords commonly used by competitors missing from your content.</p>
            </div>

            {detailed_keyword_gaps && detailed_keyword_gaps.length > 0 ? (
              <div className="opportunity-grid">
                {detailed_keyword_gaps.slice(0, 8).map((gap: DetailedKeywordGap, i: number) => (
                  <div key={i} className="opportunity-card">
                    <div className="opportunity-header">
                      <h4>{gap.keyword}</h4>
                      <span className="gap-score">Gap: {gap.gap_score.toFixed(1)}x</span>
                    </div>
                    <div className="opportunity-stats">
                      <span>Competitors: <strong>{gap.competitor_frequency}</strong></span>
                      <span>You: <strong>{gap.project_frequency}</strong></span>
                    </div>
                    <button className="primary-btn generate-btn" onClick={() => navigateToGenerate('keyword', gap.keyword)}>
                      <Wand2 size={14} /> Generate Idea
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">No significant keyword gaps detected.</div>
            )}
          </section>

          {/* Format Opportunities */}
          <section className="opportunity-section">
            <div className="section-title-wrap">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Layers size={20} className="text-primary" />
                <h3>Format Opportunities</h3>
              </div>
              <p className="section-desc">Content types performing well for competitors.</p>
            </div>

            {detailed_content_type_gaps && detailed_content_type_gaps.length > 0 ? (
              <div className="opportunity-grid">
                {detailed_content_type_gaps.map((gap: DetailedContentTypeGap, i: number) => (
                  <div key={i} className="opportunity-card">
                    <div className="opportunity-header">
                      <h4>{gap.content_type}</h4>
                      <span className="gap-score">Gap: {gap.gap_score.toFixed(1)}x</span>
                    </div>
                    <div className="opportunity-stats">
                      <span>Competitors: <strong>{gap.competitor_frequency}</strong></span>
                      <span>You: <strong>{gap.project_frequency}</strong></span>
                    </div>
                    <button className="primary-btn generate-btn" onClick={() => navigateToGenerate('content_type', gap.content_type)}>
                      <Wand2 size={14} /> Generate Idea
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">No format gaps detected.</div>
            )}
          </section>
        </div>
      </div>
    </AppLayout>
  );
};

export default ProjectStrategy;
