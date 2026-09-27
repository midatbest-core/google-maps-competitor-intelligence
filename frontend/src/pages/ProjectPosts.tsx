import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { getProjectPosts, getAnalyticsSummary, getProjectCompetitors } from '../api';
import type { Competitor, PostResponse, AnalyticsSummaryResponse, TopicFrequency, KeywordFrequency, DetailedTopicGap } from '../api';
import './ProjectPosts.css';

const ProjectPosts: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  
  const [posts, setPosts] = useState<PostResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [selectedPost, setSelectedPost] = useState<PostResponse | null>(null);

  // Filters from URL
  const page = parseInt(searchParams.get('page') || '1', 10);
  const search = searchParams.get('search') || '';
  const competitorId = searchParams.get('competitor_id') || '';
  const topic = searchParams.get('topic') || '';
  const hasAnalysis = searchParams.get('has_analysis') || '';

  useEffect(() => {
    if (projectId) {
      loadData();
    }
  }, [projectId, page, search, competitorId, topic, hasAnalysis]);

  const loadData = async () => {
    setLoading(true);
    try {
      // Load competitors for the filter dropdown
      if (competitors.length === 0) {
        const compRes = await getProjectCompetitors(projectId!);
        setCompetitors(compRes.data);
      }
      
      // Load analytics summary
      if (!analytics) {
        try {
          const anRes = await getAnalyticsSummary(projectId!);
          setAnalytics(anRes.data);
        } catch (e) {
          console.error("Failed to load analytics", e);
        }
      }

      // Load posts
      const params: Record<string, string | number | boolean | undefined> = { page, page_size: 20 };
      if (search) params.search = search;
      if (competitorId) params.competitor_id = competitorId;
      if (topic) params.topic = topic;
      if (hasAnalysis === 'true') params.has_analysis = true;
      else if (hasAnalysis === 'false') params.has_analysis = false;

      const postsRes = await getProjectPosts(projectId!, params);
      setPosts(postsRes.data.items);
      setTotal(postsRes.data.total);
      setPages(postsRes.data.pages);
      
    } catch (err) {
      setError('Failed to load posts repository.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key: string, value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value) {
      newParams.set(key, value);
    } else {
      newParams.delete(key);
    }
    newParams.set('page', '1'); // Reset pagination
    setSearchParams(newParams);
  };

  const handleClearFilters = () => {
    setSearchParams({});
  };

  const renderIntelligenceDashboard = () => {
    if (!analytics) return null;

    return (
      <div className="intelligence-dashboard">
        <h3>Project Intelligence</h3>
        <div className="intelligence-grid">
          <div className="intelligence-card">
            <h4>Top Topics</h4>
            {analytics.topics?.length > 0 ? (
              <ul className="intel-list">
                {analytics.topics.slice(0, 5).map((t: TopicFrequency, i: number) => (
                  <li key={i}>
                    <span className="intel-label">{t.topic}</span>
                    <span className="intel-value">{t.count} posts</span>
                  </li>
                ))}
              </ul>
            ) : <p className="empty-state">Not enough analyzed content yet.</p>}
          </div>

          <div className="intelligence-card">
            <h4>Top Keywords</h4>
            {analytics.keywords?.length > 0 ? (
              <div className="keyword-cloud">
                {analytics.keywords.slice(0, 10).map((k: KeywordFrequency, i: number) => (
                  <span key={i} className="keyword-tag">{k.keyword} ({k.count})</span>
                ))}
              </div>
            ) : <p className="empty-state">Not enough analyzed content yet.</p>}
          </div>

          <div className="intelligence-card">
            <h4>Content Gaps (Topics)</h4>
            {analytics.detailed_topic_gaps?.length > 0 ? (
              <ul className="intel-list">
                {analytics.detailed_topic_gaps.slice(0, 5).map((g: DetailedTopicGap, i: number) => (
                  <li key={i}>
                    <span className="intel-label">{g.topic}</span>
                    <span className="intel-value gap-high">Competitors: {g.competitor_frequency} | You: {g.project_frequency}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="empty-state">No significant gaps detected or lack of data.</p>}
          </div>
        </div>
      </div>
    );
  };

  return (
    <AppLayout projectId={projectId}>
      <div className="posts-container">
        
        {renderIntelligenceDashboard()}

        <div className="posts-header-row">
          <h2 style={{margin:0}}>Posts Repository</h2>
          <span className="post-count-badge">{total} posts found</span>
        </div>

        <div className="filters-bar">
          <input 
            type="text" 
            placeholder="Search posts..." 
            className="filter-input"
            value={searchParams.get('search') || ''}
            onChange={(e) => {
              const newParams = new URLSearchParams(searchParams);
              if (e.target.value) newParams.set('search', e.target.value);
              else newParams.delete('search');
              newParams.set('page', '1');
              setSearchParams(newParams);
            }}
          />
          
          <select 
            className="filter-select" 
            value={competitorId} 
            onChange={(e) => handleFilterChange('competitor_id', e.target.value)}
          >
            <option value="">All Competitors</option>
            {competitors.map(c => (
              <option key={c.business_id} value={c.business_id}>{c.business?.business_name}</option>
            ))}
          </select>

          <select 
            className="filter-select" 
            value={topic} 
            onChange={(e) => handleFilterChange('topic', e.target.value)}
          >
            <option value="">All Topics</option>
            {analytics?.topics?.map((t: TopicFrequency) => (
              <option key={t.topic} value={t.topic}>{t.topic}</option>
            ))}
          </select>

          <select 
            className="filter-select" 
            value={hasAnalysis} 
            onChange={(e) => handleFilterChange('has_analysis', e.target.value)}
          >
            <option value="">Analysis: All</option>
            <option value="true">Analyzed Only</option>
            <option value="false">Not Analyzed</option>
          </select>

          <button className="btn-secondary" onClick={handleClearFilters}>Clear Filters</button>
        </div>

        {error && <div className="error-message">{error}</div>}

        {loading ? (
          <div className="loading-state">Loading posts...</div>
        ) : (
          <>
            {posts.length === 0 ? (
              <div className="empty-state-large">
                <p>No competitor posts match your criteria.</p>
                {searchParams.toString() === '' && (
                  <p>Run a scrape in the Scraping tab to populate this repository.</p>
                )}
              </div>
            ) : (
              <div className="posts-grid">
                {posts.map(post => (
                  <div key={post.id} className="post-card" onClick={() => setSelectedPost(post)}>
                    <div className="post-card-header">
                      <strong>{post.business?.business_name}</strong>
                      <span className="post-date">{post.published_date ? new Date(post.published_date).toLocaleDateString() : 'Unknown date'}</span>
                    </div>
                    <div className="post-card-body">
                      {post.text_content ? (
                        <p>{post.text_content.substring(0, 150)}{post.text_content.length > 150 ? '...' : ''}</p>
                      ) : (
                        <p className="no-text">[Media Only Post]</p>
                      )}
                    </div>
                    <div className="post-card-footer">
                      <span className="media-count">{post.media?.length || 0} Media</span>
                      {post.analysis ? (
                        <span className="analysis-badge has-analysis">{post.analysis.topic || 'Analyzed'}</span>
                      ) : (
                        <span className="analysis-badge no-analysis">Pending Analysis</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            {pages > 1 && (
              <div className="pagination">
                <button 
                  disabled={page <= 1} 
                  onClick={() => handleFilterChange('page', (page - 1).toString())}
                >
                  Previous
                </button>
                <span>Page {page} of {pages}</span>
                <button 
                  disabled={page >= pages} 
                  onClick={() => handleFilterChange('page', (page + 1).toString())}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Detail Modal */}
      {selectedPost && (
        <div className="post-modal-overlay" onClick={() => setSelectedPost(null)}>
          <div className="post-modal-content" onClick={e => e.stopPropagation()}>
            <div className="post-modal-header">
              <h3>{selectedPost.business?.business_name}</h3>
              <button className="close-btn" onClick={() => setSelectedPost(null)}>×</button>
            </div>
            
            <div className="post-modal-meta">
              <span>Published: {selectedPost.published_date ? new Date(selectedPost.published_date).toLocaleString() : 'N/A'}</span>
              {selectedPost.source_url && (
                <a href={selectedPost.source_url} target="_blank" rel="noreferrer" className="source-link">Open Source ↗</a>
              )}
            </div>

            <div className="post-modal-text">
              {selectedPost.text_content || <span className="no-text">No text content.</span>}
            </div>

            {selectedPost.media && selectedPost.media.length > 0 && (
              <div className="post-modal-media">
                <h4>Media ({selectedPost.media.length})</h4>
                <div className="media-grid">
                  {selectedPost.media.map(m => (
                    <div key={m.id} className="media-item">
                      <span className="media-type">{m.media_type}</span>
                      <span className="media-meta">{m.width}x{m.height}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="post-modal-analysis">
              <h4>AI Analysis</h4>
              {selectedPost.analysis ? (
                <div className="analysis-details">
                  <div className="analysis-row"><span className="a-label">Topic:</span> <span className="a-value">{selectedPost.analysis.topic || 'N/A'}</span></div>
                  <div className="analysis-row"><span className="a-label">Subtopic:</span> <span className="a-value">{selectedPost.analysis.subtopic || 'N/A'}</span></div>
                  <div className="analysis-row"><span className="a-label">Content Type:</span> <span className="a-value">{selectedPost.analysis.content_type || 'N/A'}</span></div>
                  <div className="analysis-row"><span className="a-label">CTA:</span> <span className="a-value">{selectedPost.analysis.cta_type || 'N/A'}</span></div>
                  <div className="analysis-row"><span className="a-label">Sentiment:</span> <span className="a-value">{selectedPost.analysis.sentiment || 'N/A'}</span></div>
                  
                  {selectedPost.analysis.keywords && selectedPost.analysis.keywords.length > 0 && (
                    <div className="analysis-keywords">
                      <strong>Keywords:</strong>
                      <div className="keyword-cloud">
                        {selectedPost.analysis.keywords.map((kw, idx) => (
                          <span key={idx} className="keyword-tag">{kw}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="empty-state">Analysis not available yet.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default ProjectPosts;
