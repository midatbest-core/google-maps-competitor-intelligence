import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { getProjectReviews, getProjectCompetitors } from '../api';
import type { ReviewItem, Competitor } from '../api';
import './ProjectPosts.css';

const ProjectReviews: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();

  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedCompetitor, setSelectedCompetitor] = useState<string>('');
  const [selectedSentiment, setSelectedSentiment] = useState<string>('');
  const [selectedSource, setSelectedSource] = useState<string>('');

  useEffect(() => {
    if (projectId) {
      loadCompetitors();
    }
  }, [projectId]);

  useEffect(() => {
    if (projectId) {
      loadReviews();
    }
  }, [projectId, page, selectedCompetitor, selectedSentiment, selectedSource]);

  const loadCompetitors = async () => {
    try {
      const res = await getProjectCompetitors(projectId!);
      setCompetitors(res.data);
    } catch {
      // Non-critical, ignore
    }
  };

  const loadReviews = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | undefined> = {
        page,
        page_size: 15,
      };
      if (selectedCompetitor) params.competitor_id = selectedCompetitor;
      if (selectedSentiment) params.sentiment = selectedSentiment;
      if (selectedSource) params.source = selectedSource;

      const res = await getProjectReviews(projectId!, params);
      setReviews(res.data.items);
      setTotal(res.data.total);
      setPages(res.data.pages);
    } catch {
      setError('Unable to load reviews. Please verify network or project settings.');
    } finally {
      setLoading(false);
    }
  };

  const formatStars = (rating?: number) => {
    if (rating == null) return 'No rating';
    const rounded = Math.round(rating);
    return '★'.repeat(rounded) + '☆'.repeat(5 - rounded) + ` (${rating.toFixed(1)})`;
  };

  const getSentimentClass = (sentiment?: string) => {
    switch (sentiment?.toUpperCase()) {
      case 'POSITIVE':
        return 'sentiment-positive';
      case 'NEGATIVE':
        return 'sentiment-negative';
      default:
        return 'sentiment-neutral';
    }
  };

  return (
    <AppLayout projectId={projectId}>
      <div className="posts-container">
        <div className="posts-header">
          <div>
            <h2>Customer Reviews & Feedback</h2>
            <p className="subtitle">Real Google Maps customer feedback and competitor complaints ({total} total)</p>
          </div>
          <Link to={`/projects/${projectId}/intelligence`} className="btn-primary" style={{ textDecoration: 'none' }}>
            View Combined Intelligence →
          </Link>
        </div>

        {/* Filters Toolbar */}
        <div className="filters-toolbar" style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '24px' }}>
          <select
            className="filter-select"
            value={selectedCompetitor}
            onChange={(e) => { setSelectedCompetitor(e.target.value); setPage(1); }}
            style={{ padding: '8px 12px', borderRadius: '6px', background: '#1e293b', color: '#f8fafc', border: '1px solid #334155' }}
          >
            <option value="">All Competitors & Locations</option>
            {competitors.map((c) => (
              <option key={c.business_id} value={c.business_id}>
                {c.business?.business_name || c.business_id}
              </option>
            ))}
          </select>

          <select
            className="filter-select"
            value={selectedSentiment}
            onChange={(e) => { setSelectedSentiment(e.target.value); setPage(1); }}
            style={{ padding: '8px 12px', borderRadius: '6px', background: '#1e293b', color: '#f8fafc', border: '1px solid #334155' }}
          >
            <option value="">All Sentiments</option>
            <option value="POSITIVE">Positive Feedback</option>
            <option value="NEUTRAL">Neutral Feedback</option>
            <option value="NEGATIVE">Customer Complaints</option>
          </select>

          <select
            className="filter-select"
            value={selectedSource}
            onChange={(e) => { setSelectedSource(e.target.value); setPage(1); }}
            style={{ padding: '8px 12px', borderRadius: '6px', background: '#1e293b', color: '#f8fafc', border: '1px solid #334155' }}
          >
            <option value="">All Extraction Sources</option>
            <option value="browser_scraper">Playwright Browser Extractor</option>
            <option value="google_places_api">Google Places API</option>
            <option value="gosom_scraper">Gosom Scraper</option>
          </select>
        </div>

        {loading ? (
          <div className="loading-state">Loading reviews data...</div>
        ) : error ? (
          <div className="error-message">{error}</div>
        ) : reviews.length === 0 ? (
          <div className="empty-state">
            <p>No customer reviews collected matching the selected criteria.</p>
            <Link to={`/projects/${projectId}/scraping`} className="btn-secondary" style={{ marginTop: '12px', display: 'inline-block' }}>
              Run Collection Job
            </Link>
          </div>
        ) : (
          <div className="posts-grid">
            {reviews.map((r) => (
              <div key={r.id} className="post-card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h4 style={{ margin: '0 0 4px', fontSize: '15px', color: '#f8fafc' }}>
                      {r.business_name || 'Business Location'}
                    </h4>
                    <span style={{ fontSize: '13px', color: '#94a3b8' }}>
                      By {r.author_name || 'Anonymous User'} • {r.relative_time_description || 'Recently'}
                    </span>
                  </div>
                  <span className={`sentiment-badge ${getSentimentClass(r.sentiment)}`} style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>
                    {r.sentiment || 'NEUTRAL'}
                  </span>
                </div>

                <div style={{ color: '#fbbf24', fontSize: '14px', letterSpacing: '1px' }}>
                  {formatStars(r.rating)}
                </div>

                <p style={{ margin: '0', fontSize: '14px', lineHeight: '1.6', color: '#cbd5e1' }}>
                  {r.text || <em style={{ color: '#64748b' }}>No text content provided in review.</em>}
                </p>

                {r.response_text && (
                  <div style={{ background: '#0f172a', padding: '10px 14px', borderRadius: '6px', borderLeft: '3px solid #3b82f6', marginTop: '6px' }}>
                    <div style={{ fontSize: '12px', color: '#60a5fa', fontWeight: 600, marginBottom: '2px' }}>Response from Owner:</div>
                    <div style={{ fontSize: '13px', color: '#94a3b8' }}>{r.response_text}</div>
                  </div>
                )}

                <div style={{ marginTop: 'auto', paddingTop: '8px', borderTop: '1px solid #334155', display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#64748b' }}>
                  <span>Source: {r.source}</span>
                  <span>ID: {r.id.slice(0, 8)}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {pages > 1 && (
          <div className="pagination" style={{ display: 'flex', justifyContent: 'center', gap: '12px', marginTop: '32px' }}>
            <button
              className="btn-secondary"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </button>
            <span style={{ alignSelf: 'center', color: '#94a3b8', fontSize: '14px' }}>
              Page {page} of {pages}
            </span>
            <button
              className="btn-secondary"
              disabled={page >= pages}
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default ProjectReviews;

