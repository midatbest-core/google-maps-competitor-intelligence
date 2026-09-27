import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { getAnalyticsSummary } from '../api';
import type { AnalyticsSummaryResponse, DetailedTopicGap, DetailedKeywordGap, DetailedContentTypeGap } from '../api';
import './ProjectStrategy.css';

const ProjectStrategy: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  
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
    } finally {
      setLoading(false);
    }
  };

  const navigateToGenerate = (type: string, value: string) => {
    const params = new URLSearchParams();
    params.set(type, value);
    navigate(`/projects/${projectId}/generate?${params.toString()}`);
  };

  if (loading) {
    return (
      <AppLayout projectId={projectId}>
        <div className="strategy-container">
          <div className="loading-state">Analyzing intelligence...</div>
        </div>
      </AppLayout>
    );
  }

  if (error) {
    return (
      <AppLayout projectId={projectId}>
        <div className="strategy-container">
          <div className="error-message">{error}</div>
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
      <div className="strategy-container">
        <div className="strategy-header">
          <h2>Content Strategy</h2>
          <p>Actionable opportunities identified from competitor behavior.</p>
        </div>

        <div className="strategy-sections">
          
          <section className="opportunity-section">
            <h3>Topic Opportunities</h3>
            <p className="section-desc">Topics your competitors post about frequently, but you do not.</p>
            {detailed_topic_gaps && detailed_topic_gaps.length > 0 ? (
              <div className="opportunity-grid">
                {detailed_topic_gaps.map((gap: DetailedTopicGap, i: number) => (
                  <div key={i} className="opportunity-card">
                    <div className="opportunity-header">
                      <h4>{gap.topic}</h4>
                      <span className="gap-score">Gap: {gap.gap_score.toFixed(1)}x</span>
                    </div>
                    <div className="opportunity-stats">
                      <span>Competitors: {gap.competitor_frequency}</span>
                      <span>You: {gap.project_frequency}</span>
                    </div>
                    <button className="btn-primary generate-btn" onClick={() => navigateToGenerate('topic', gap.topic)}>
                      Generate Idea
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">No significant topic gaps detected. Try gathering more data.</div>
            )}
          </section>

          <section className="opportunity-section">
            <h3>Keyword Opportunities</h3>
            <p className="section-desc">Keywords commonly used by competitors missing from your content.</p>
            {detailed_keyword_gaps && detailed_keyword_gaps.length > 0 ? (
              <div className="opportunity-grid">
                {detailed_keyword_gaps.slice(0, 8).map((gap: DetailedKeywordGap, i: number) => (
                  <div key={i} className="opportunity-card">
                    <div className="opportunity-header">
                      <h4>{gap.keyword}</h4>
                      <span className="gap-score">Gap: {gap.gap_score.toFixed(1)}x</span>
                    </div>
                    <div className="opportunity-stats">
                      <span>Competitors: {gap.competitor_frequency}</span>
                      <span>You: {gap.project_frequency}</span>
                    </div>
                    <button className="btn-primary generate-btn" onClick={() => navigateToGenerate('keyword', gap.keyword)}>
                      Generate Idea
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">No significant keyword gaps detected.</div>
            )}
          </section>

          <section className="opportunity-section">
            <h3>Format Opportunities</h3>
            <p className="section-desc">Content types performing well for competitors.</p>
            {detailed_content_type_gaps && detailed_content_type_gaps.length > 0 ? (
              <div className="opportunity-grid">
                {detailed_content_type_gaps.map((gap: DetailedContentTypeGap, i: number) => (
                  <div key={i} className="opportunity-card">
                    <div className="opportunity-header">
                      <h4>{gap.content_type}</h4>
                      <span className="gap-score">Gap: {gap.gap_score.toFixed(1)}x</span>
                    </div>
                    <div className="opportunity-stats">
                      <span>Competitors: {gap.competitor_frequency}</span>
                      <span>You: {gap.project_frequency}</span>
                    </div>
                    <button className="btn-primary generate-btn" onClick={() => navigateToGenerate('content_type', gap.content_type)}>
                      Generate Idea
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
