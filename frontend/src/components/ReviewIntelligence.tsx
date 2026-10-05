import React, { useEffect, useState } from 'react';
import { getReviewIntelligence, analyzeReviewIntelligence } from '../api';
import type { ReviewIntelligence as RIModel } from '../api';

const ReviewIntelligence: React.FC<{ projectId: string }> = ({ projectId }) => {
    const [intelligence, setIntelligence] = useState<RIModel | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [analyzing, setAnalyzing] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const loadData = async () => {
        try {
            setLoading(true);
            const res = await getReviewIntelligence(projectId);
            setIntelligence(res.data);
            setError(null);
        } catch (err: any) {
            if (err.response?.status !== 404) {
                setError("Failed to load review intelligence.");
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, [projectId]);

    const handleAnalyze = async () => {
        try {
            setAnalyzing(true);
            setError(null);
            const res = await analyzeReviewIntelligence(projectId);
            setIntelligence(res.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || "Failed to analyze reviews.");
        } finally {
            setAnalyzing(false);
        }
    };

    if (loading) {
        return (
            <div className="card" style={{ padding: '2rem', textAlign: 'center', opacity: 0.7 }}>
                <p>Loading Customer Voice...</p>
            </div>
        );
    }

    return (
        <div className="card" style={{ padding: '1.5rem', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#fff' }}>Customer Voice (Review Intelligence)</h3>
                <button
                    onClick={handleAnalyze}
                    disabled={analyzing}
                    className="btn-primary"
                    style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
                >
                    {analyzing ? 'Analyzing...' : (intelligence ? 'Re-analyze Reviews' : 'Analyze Customer Reviews')}
                </button>
            </div>

            {error && <div className="error-message" style={{ marginBottom: '1rem' }}>{error}</div>}

            {!intelligence ? (
                <div style={{ textAlign: 'center', padding: '2rem', opacity: 0.5 }}>
                    <p style={{ margin: 0 }}>No review intelligence available yet.</p>
                    <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem' }}>Analyze reviews to unlock customer insights.</p>
                </div>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>

                    {/* Top Stats */}
                    <div style={{ gridColumn: '1 / -1', display: 'flex', gap: '1rem', background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px' }}>
                        <div>
                            <span style={{ fontSize: '0.8rem', color: '#aaa', display: 'block' }}>Reviews Analyzed</span>
                            <span style={{ fontSize: '1.5rem', fontWeight: 600 }}>{intelligence.reviews_analyzed_count}</span>
                        </div>
                        <div style={{ paddingLeft: '1rem', borderLeft: '1px solid rgba(255,255,255,0.1)' }}>
                            <span style={{ fontSize: '0.8rem', color: '#aaa', display: 'block' }}>Avg Rating</span>
                            <span style={{ fontSize: '1.5rem', fontWeight: 600, color: '#fbbf24' }}>{intelligence.average_rating?.toFixed(1) || '-'} ★</span>
                        </div>
                        <div style={{ paddingLeft: '1rem', borderLeft: '1px solid rgba(255,255,255,0.1)' }}>
                            <span style={{ fontSize: '0.8rem', color: '#aaa', display: 'block' }}>Overall Sentiment</span>
                            <span style={{ fontSize: '1.2rem', fontWeight: 500, color: intelligence.overall_sentiment?.toLowerCase() === 'positive' ? '#10b981' : (intelligence.overall_sentiment?.toLowerCase() === 'negative' ? '#ef4444' : '#fff') }}>
                                {intelligence.overall_sentiment || 'Neutral'}
                            </span>
                        </div>
                        <div style={{ paddingLeft: '1rem', borderLeft: '1px solid rgba(255,255,255,0.1)', flex: 1 }}>
                            <span style={{ fontSize: '0.8rem', color: '#aaa', display: 'block' }}>Sentiment Breakdown</span>
                            <div style={{ display: 'flex', height: '6px', borderRadius: '3px', overflow: 'hidden', marginTop: '0.5rem' }}>
                                <div style={{ width: `${intelligence.positive_percentage || 0}%`, background: '#10b981' }}></div>
                                <div style={{ width: `${intelligence.neutral_percentage || 0}%`, background: '#9ca3af' }}></div>
                                <div style={{ width: `${intelligence.negative_percentage || 0}%`, background: '#ef4444' }}></div>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: '#aaa', marginTop: '0.25rem' }}>
                                <span>{intelligence.positive_percentage?.toFixed(0)}% Pos</span>
                                <span>{intelligence.neutral_percentage?.toFixed(0)}% Neu</span>
                                <span>{intelligence.negative_percentage?.toFixed(0)}% Neg</span>
                            </div>
                        </div>
                    </div>

                    {/* Left Column */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <div>
                            <h4 style={{ margin: '0 0 0.5rem 0', color: '#10b981', fontSize: '0.9rem' }}>Customers Frequently Praise</h4>
                            <ul style={{ margin: 0, paddingLeft: '1.2rem', color: '#e5e7eb', fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                {intelligence.praise_themes?.map((t, i) => <li key={i}>{t}</li>) || <li>None identified</li>}
                            </ul>
                        </div>
                        <div>
                            <h4 style={{ margin: '0 0 0.5rem 0', color: '#3b82f6', fontSize: '0.9rem' }}>Common Customer Needs</h4>
                            <ul style={{ margin: 0, paddingLeft: '1.2rem', color: '#e5e7eb', fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                {intelligence.customer_needs?.map((t, i) => <li key={i}>{t}</li>) || <li>None identified</li>}
                            </ul>
                        </div>
                    </div>

                    {/* Right Column */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <div>
                            <h4 style={{ margin: '0 0 0.5rem 0', color: '#ef4444', fontSize: '0.9rem' }}>Repeated Complaints & Pain Points</h4>
                            <ul style={{ margin: 0, paddingLeft: '1.2rem', color: '#e5e7eb', fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                {intelligence.complaint_themes?.map((t, i) => <li key={i}>{t}</li>) || <li>None identified</li>}
                                {intelligence.pain_points?.map((t, i) => <li key={`p${i}`}>{t}</li>)}
                            </ul>
                        </div>
                        <div>
                            <h4 style={{ margin: '0 0 0.5rem 0', color: '#a855f7', fontSize: '0.9rem' }}>Content & Business Opportunities</h4>
                            <ul style={{ margin: 0, paddingLeft: '1.2rem', color: '#e5e7eb', fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                {intelligence.business_opportunities?.map((t, i) => <li key={i}>{t}</li>) || <li>None identified</li>}
                            </ul>
                        </div>
                    </div>

                    <div style={{ gridColumn: '1 / -1', fontSize: '0.75rem', color: '#6b7280', textAlign: 'right', marginTop: '0.5rem' }}>
                        Analyzed with {intelligence.analysis_provider} ({intelligence.model_version}) on {new Date(intelligence.analyzed_at).toLocaleDateString()}
                    </div>
                </div>
            )}
        </div>
    );
};

export default ReviewIntelligence;
