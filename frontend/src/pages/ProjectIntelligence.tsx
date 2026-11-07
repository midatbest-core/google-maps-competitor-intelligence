import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import {
  getProjectIntelligence,
  generateProjectIntelligence,
} from '../api';
import type {
  CombinedIntelligenceReport,
  StrategicDisconnect,
  ActionableRecommendation,
  ContentIdeaItem,
  CompetitorInsightItem,
} from '../api';
import './ProjectStrategy.css';

const ProjectIntelligence: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [report, setReport] = useState<CombinedIntelligenceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (projectId) {
      loadReport();
    }
  }, [projectId]);

  const loadReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getProjectIntelligence(projectId!);
      setReport(res.data);
    } catch {
      // 404 is normal if none generated yet
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSynthesize = async () => {
    setGenerating(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await generateProjectIntelligence(projectId!);
      setReport(res.data);
      setSuccessMsg('Successfully synthesized new combined intelligence from posts and reviews!');
      setTimeout(() => setSuccessMsg(null), 6000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to generate intelligence. Check if collection data exists.');
    } finally {
      setGenerating(false);
    }
  };

  const sendToStudio = (idea: ContentIdeaItem) => {
    const params = new URLSearchParams();
    params.set('topic', idea.title);
    params.set('campaign_context', `Hook: ${idea.hook}\nAngle: ${idea.angle}\nEvidence: ${idea.evidence_backed_reason}`);
    navigate(`/projects/${projectId}/generate?${params.toString()}`);
  };

  const getPriorityBadgeClass = (priority: string) => {
    switch (priority) {
      case 'HIGH':
        return 'priority-high';
      case 'MEDIUM':
        return 'priority-medium';
      default:
        return 'priority-low';
    }
  };

  return (
    <AppLayout projectId={projectId}>
      <div className="strategy-container">
        {/* Top Header */}
        <div className="strategy-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h2>Combined Intelligence Engine</h2>
            <p className="subtitle">
              Synthesizing competitor marketing posts with real customer review feedback to uncover strategic disconnects and business opportunities.
            </p>
          </div>
          <button
            className="btn-primary"
            onClick={handleSynthesize}
            disabled={generating}
            style={{ padding: '12px 24px', fontSize: '15px', fontWeight: 600 }}
          >
            {generating ? 'Synthesizing with Gemini...' : '⚡ Synthesize New Intelligence'}
          </button>
        </div>

        {successMsg && (
          <div style={{ background: '#064e3b', color: '#6ee7b7', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', border: '1px solid #047857' }}>
            {successMsg}
          </div>
        )}

        {error && (
          <div className="error-message" style={{ marginBottom: '20px' }}>
            {error}
          </div>
        )}

        {loading ? (
          <div className="loading-state">Loading intelligence models...</div>
        ) : !report ? (
          <div className="empty-state" style={{ padding: '60px 20px', textAlign: 'center' }}>
            <h3 style={{ fontSize: '20px', color: '#f8fafc', marginBottom: '8px' }}>No Combined Intelligence Report Yet</h3>
            <p style={{ color: '#94a3b8', maxWidth: '540px', margin: '0 auto 24px' }}>
              Run our Playwright and Places collectors in Scraping to collect competitor posts and reviews, then click "Synthesize New Intelligence".
            </p>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <Link to={`/projects/${projectId}/scraping`} className="btn-secondary" style={{ textDecoration: 'none' }}>
                Go to Scraping Controls
              </Link>
              <button className="btn-primary" onClick={handleSynthesize} disabled={generating}>
                Generate Baseline Analysis
              </button>
            </div>
          </div>
        ) : (
          <div className="strategy-sections">
            {/* Metrics Overview Bar */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '32px' }}>
              <div className="stat-card" style={{ background: '#1e293b', padding: '16px', borderRadius: '8px', border: '1px solid #334155' }}>
                <span style={{ fontSize: '13px', color: '#94a3b8' }}>Competitors Analyzed</span>
                <div style={{ fontSize: '24px', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>{report.competitors_analyzed}</div>
              </div>
              <div className="stat-card" style={{ background: '#1e293b', padding: '16px', borderRadius: '8px', border: '1px solid #334155' }}>
                <span style={{ fontSize: '13px', color: '#94a3b8' }}>Posts Synthesized</span>
                <div style={{ fontSize: '24px', fontWeight: 700, color: '#38bdf8', marginTop: '4px' }}>{report.posts_analyzed}</div>
              </div>
              <div className="stat-card" style={{ background: '#1e293b', padding: '16px', borderRadius: '8px', border: '1px solid #334155' }}>
                <span style={{ fontSize: '13px', color: '#94a3b8' }}>Customer Reviews Analyzed</span>
                <div style={{ fontSize: '24px', fontWeight: 700, color: '#a855f7', marginTop: '4px' }}>{report.reviews_analyzed}</div>
              </div>
              <div className="stat-card" style={{ background: '#1e293b', padding: '16px', borderRadius: '8px', border: '1px solid #334155' }}>
                <span style={{ fontSize: '13px', color: '#94a3b8' }}>Report Generated</span>
                <div style={{ fontSize: '14px', fontWeight: 500, color: '#cbd5e1', marginTop: '8px' }}>
                  {new Date(report.created_at).toLocaleDateString()} via {report.provider || 'Gemini'}
                </div>
              </div>
            </div>

            {/* SECTION 1: STRATEGIC DISCONNECTS (The core feature) */}
            <section className="opportunity-section" style={{ marginBottom: '40px' }}>
              <div style={{ borderBottom: '2px solid #3b82f6', paddingBottom: '8px', marginBottom: '20px' }}>
                <h3 style={{ fontSize: '20px', color: '#60a5fa', margin: 0 }}>
                  🔍 Strategic Disconnects (Advertised Promise vs Customer Reality)
                </h3>
                <p className="section-desc" style={{ marginTop: '4px' }}>
                  Where competitors promote an ideal experience in posts, but real customer reviews reveal friction and dissatisfaction.
                </p>
              </div>

              {report.strategic_disconnects && report.strategic_disconnects.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {report.strategic_disconnects.map((item: StrategicDisconnect, idx: number) => (
                    <div
                      key={idx}
                      style={{
                        background: '#1e293b',
                        borderRadius: '10px',
                        border: '1px solid #334155',
                        padding: '24px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '16px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h4 style={{ fontSize: '17px', color: '#f8fafc', margin: 0 }}>
                          Competitor: <span style={{ color: '#38bdf8' }}>{item.competitor_name}</span>
                        </h4>
                        <span style={{ background: '#450a0a', color: '#f87171', padding: '4px 10px', borderRadius: '4px', fontSize: '12px', fontWeight: 600 }}>
                          Disconnect Identified
                        </span>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                        {/* What They Advertise */}
                        <div style={{ background: '#0f172a', padding: '16px', borderRadius: '8px', borderLeft: '4px solid #0284c7' }}>
                          <div style={{ fontSize: '12px', textTransform: 'uppercase', color: '#38bdf8', fontWeight: 700, marginBottom: '6px' }}>
                            📢 Advertised Claim (Posts)
                          </div>
                          <p style={{ margin: 0, fontSize: '14px', color: '#cbd5e1', lineHeight: '1.5' }}>
                            {item.advertised_promise}
                          </p>
                        </div>

                        {/* Customer Reality */}
                        <div style={{ background: '#0f172a', padding: '16px', borderRadius: '8px', borderLeft: '4px solid #ef4444' }}>
                          <div style={{ fontSize: '12px', textTransform: 'uppercase', color: '#f87171', fontWeight: 700, marginBottom: '6px' }}>
                            ⚠️ Customer Reality (Reviews)
                          </div>
                          <p style={{ margin: 0, fontSize: '14px', color: '#cbd5e1', lineHeight: '1.5' }}>
                            {item.customer_reality}
                          </p>
                        </div>
                      </div>

                      {/* Our Business Opportunity */}
                      <div style={{ background: '#022c22', padding: '16px', borderRadius: '8px', borderLeft: '4px solid #10b981' }}>
                        <div style={{ fontSize: '12px', textTransform: 'uppercase', color: '#34d399', fontWeight: 700, marginBottom: '6px' }}>
                          💡 Strategic Advantage for Your Business
                        </div>
                        <p style={{ margin: '0 0 10px', fontSize: '14px', color: '#e2e8f0', lineHeight: '1.5' }}>
                          {item.opportunity}
                        </p>
                        <div style={{ fontSize: '13px', color: '#a7f3d0' }}>
                          <strong>Recommended Play:</strong> {item.recommended_action}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state">No strategic disconnects identified in current dataset.</div>
              )}
            </section>

            {/* SECTION 2: ACTIONABLE RECOMMENDATIONS WITH EVIDENCE */}
            <section className="opportunity-section" style={{ marginBottom: '40px' }}>
              <div style={{ borderBottom: '2px solid #10b981', paddingBottom: '8px', marginBottom: '20px' }}>
                <h3 style={{ fontSize: '20px', color: '#34d399', margin: 0 }}>
                  🎯 Evidence-Backed Actionable Recommendations
                </h3>
                <p className="section-desc" style={{ marginTop: '4px' }}>
                  Recommendations supported by direct citations to observed competitor posts and customer review patterns.
                </p>
              </div>

              {report.actionable_recommendations && report.actionable_recommendations.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px' }}>
                  {report.actionable_recommendations.map((rec: ActionableRecommendation, idx: number) => (
                    <div
                      key={idx}
                      style={{
                        background: '#1e293b',
                        borderRadius: '10px',
                        border: '1px solid #334155',
                        padding: '20px',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                          <span style={{ textTransform: 'uppercase', fontSize: '11px', letterSpacing: '1px', color: '#94a3b8', fontWeight: 600 }}>
                            {rec.category}
                          </span>
                          <span
                            className={getPriorityBadgeClass(rec.priority)}
                            style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700 }}
                          >
                            {rec.priority} PRIORITY
                          </span>
                        </div>

                        <h4 style={{ fontSize: '16px', color: '#f8fafc', margin: '0 0 10px' }}>
                          {rec.title}
                        </h4>

                        <p style={{ fontSize: '14px', color: '#cbd5e1', lineHeight: '1.5', margin: '0 0 12px' }}>
                          {rec.description}
                        </p>

                        <div style={{ background: '#0f172a', padding: '10px 12px', borderRadius: '6px', fontSize: '13px', color: '#94a3b8', marginBottom: '16px' }}>
                          <strong style={{ color: '#e2e8f0' }}>Rationale:</strong> {rec.rationale}
                        </div>
                      </div>

                      {/* Supporting Evidence Citations */}
                      {rec.supporting_evidence && rec.supporting_evidence.length > 0 && (
                        <div style={{ borderTop: '1px solid #334155', paddingTop: '12px' }}>
                          <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#64748b', fontWeight: 700, marginBottom: '8px' }}>
                            Supporting Source Evidence ({rec.supporting_evidence.length}):
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            {rec.supporting_evidence.map((ev, evIdx) => (
                              <div
                                key={evIdx}
                                style={{
                                  fontSize: '12px',
                                  color: '#94a3b8',
                                  background: '#090d16',
                                  padding: '8px 10px',
                                  borderRadius: '4px',
                                  borderLeft: `2px solid ${ev.source_type === 'review' ? '#a855f7' : '#38bdf8'}`,
                                }}
                              >
                                <span style={{ color: ev.source_type === 'review' ? '#c084fc' : '#7dd3fc', fontWeight: 600, marginRight: '6px' }}>
                                  [{ev.source_type.toUpperCase()}]
                                </span>
                                {ev.business_name && <strong style={{ color: '#e2e8f0' }}>{ev.business_name}: </strong>}
                                {ev.quote_or_summary}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state">No specific recommendations generated yet.</div>
              )}
            </section>

            {/* SECTION 3: CONTENT CONCEPTS (Ready for Studio) */}
            <section className="opportunity-section" style={{ marginBottom: '40px' }}>
              <div style={{ borderBottom: '2px solid #a855f7', paddingBottom: '8px', marginBottom: '20px' }}>
                <h3 style={{ fontSize: '20px', color: '#c084fc', margin: 0 }}>
                  ✍️ High-Converting Content & Campaign Ideas
                </h3>
                <p className="section-desc" style={{ marginTop: '4px' }}>
                  Campaign hooks formulated to turn competitor shortcomings into your marketing advantage.
                </p>
              </div>

              {report.content_ideas && report.content_ideas.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
                  {report.content_ideas.map((idea: ContentIdeaItem, idx: number) => (
                    <div
                      key={idx}
                      style={{
                        background: '#1e293b',
                        borderRadius: '10px',
                        border: '1px solid #334155',
                        padding: '20px',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                          <span style={{ fontSize: '11px', color: '#c084fc', fontWeight: 600, textTransform: 'uppercase' }}>
                            {idea.suggested_format}
                          </span>
                          <span style={{ fontSize: '12px', color: '#64748b' }}>Target: {idea.target_audience}</span>
                        </div>

                        <h4 style={{ fontSize: '16px', color: '#f8fafc', margin: '0 0 10px' }}>
                          {idea.title}
                        </h4>

                        <div style={{ background: '#0f172a', padding: '12px', borderRadius: '6px', borderLeft: '3px solid #a855f7', marginBottom: '12px' }}>
                          <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '4px' }}>Hook:</div>
                          <div style={{ fontSize: '14px', color: '#f1f5f9', fontStyle: 'italic' }}>
                            "{idea.hook}"
                          </div>
                        </div>

                        <p style={{ fontSize: '13px', color: '#cbd5e1', margin: '0 0 12px' }}>
                          <strong>Angle:</strong> {idea.angle}
                        </p>

                        <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '16px' }}>
                          <strong>Why it works:</strong> {idea.evidence_backed_reason}
                        </div>
                      </div>

                      <button
                        className="btn-primary"
                        onClick={() => sendToStudio(idea)}
                        style={{ width: '100%', marginTop: '12px', fontSize: '13px' }}
                      >
                        Send to Content Studio →
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state">No content concepts generated yet.</div>
              )}
            </section>

            {/* SECTION 4: PER-COMPETITOR INTEL & POSITIONING */}
            <section className="opportunity-section">
              <div style={{ borderBottom: '2px solid #e2e8f0', paddingBottom: '8px', marginBottom: '20px' }}>
                <h3 style={{ fontSize: '20px', color: '#f8fafc', margin: 0 }}>
                  🏢 Competitor Profiles & Positioning Analysis
                </h3>
              </div>

              {report.competitor_insights && report.competitor_insights.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
                  {report.competitor_insights.map((comp: CompetitorInsightItem, idx: number) => (
                    <div
                      key={idx}
                      style={{
                        background: '#1e293b',
                        borderRadius: '10px',
                        border: '1px solid #334155',
                        padding: '20px',
                      }}
                    >
                      <h4 style={{ fontSize: '17px', color: '#f8fafc', margin: '0 0 4px' }}>
                        {comp.competitor_name}
                      </h4>
                      <div style={{ fontSize: '13px', color: '#38bdf8', fontWeight: 600, marginBottom: '16px' }}>
                        Positioning: {comp.positioning}
                      </div>

                      <div style={{ marginBottom: '12px' }}>
                        <div style={{ fontSize: '12px', color: '#10b981', fontWeight: 600, textTransform: 'uppercase' }}>Strengths:</div>
                        <ul style={{ margin: '4px 0 0', paddingLeft: '18px', fontSize: '13px', color: '#cbd5e1' }}>
                          {comp.strengths.map((s, sIdx) => <li key={sIdx}>{s}</li>)}
                        </ul>
                      </div>

                      <div style={{ marginBottom: '12px' }}>
                        <div style={{ fontSize: '12px', color: '#ef4444', fontWeight: 600, textTransform: 'uppercase' }}>Weaknesses:</div>
                        <ul style={{ margin: '4px 0 0', paddingLeft: '18px', fontSize: '13px', color: '#cbd5e1' }}>
                          {comp.weaknesses.map((w, wIdx) => <li key={wIdx}>{w}</li>)}
                        </ul>
                      </div>

                      <div style={{ marginBottom: '12px' }}>
                        <div style={{ fontSize: '12px', color: '#f59e0b', fontWeight: 600, textTransform: 'uppercase' }}>Recurring Complaints:</div>
                        <ul style={{ margin: '4px 0 0', paddingLeft: '18px', fontSize: '13px', color: '#cbd5e1' }}>
                          {comp.recurring_complaints.map((c, cIdx) => <li key={cIdx}>{c}</li>)}
                        </ul>
                      </div>

                      <div>
                        <div style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase' }}>Marketing Patterns:</div>
                        <ul style={{ margin: '4px 0 0', paddingLeft: '18px', fontSize: '13px', color: '#cbd5e1' }}>
                          {comp.marketing_patterns.map((m, mIdx) => <li key={mIdx}>{m}</li>)}
                        </ul>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state">No competitor breakdown available.</div>
              )}
            </section>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default ProjectIntelligence;

