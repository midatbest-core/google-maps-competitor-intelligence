import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { useToast } from '../context/ToastContext';
import { startGeneration, regenerateContent, retryGeneration, getGeneration, getGenerations, getGenerationPostSources } from '../api';
import type { GenerationRequest, GeneratedContentResponse, GenerationPostSource } from '../api';
import {
  Wand2,
  Copy,
  Check,
  RotateCw,
  Lightbulb,
  FileText,
  Sparkles,
  History,
  AlertCircle,
  Tag
} from 'lucide-react';
import './ProjectGenerate.css';

const ProjectGenerate: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const { showToast } = useToast();

  // Inputs
  const [workflowMode, setWorkflowMode] = useState<'MARKETING_OPPORTUNITIES' | 'CREATE_CONTENT'>(
    searchParams.has('context_type') || searchParams.has('topic') || searchParams.has('keyword') || searchParams.has('content_type')
      ? 'CREATE_CONTENT' : 'MARKETING_OPPORTUNITIES'
  );
  const [contextType, setContextType] = useState<GenerationRequest['context_type'] | ''>(searchParams.get('context_type') as GenerationRequest['context_type'] || (searchParams.has('content_type') ? 'content_type' : searchParams.has('keyword') ? 'keyword' : searchParams.has('topic') ? 'topic' : ''));
  const [contextValue, setContextValue] = useState(searchParams.get('context_value') || searchParams.get('topic') || searchParams.get('keyword') || searchParams.get('content_type') || '');
  const [contextGenerationId, setContextGenerationId] = useState(searchParams.get('context_generation_id') || '');
  const [topic, setTopic] = useState(searchParams.get('topic') || '');
  const [keyword, setKeyword] = useState(searchParams.get('keyword') || '');
  const [contentType, setContentType] = useState(searchParams.get('content_type') || '');
  const [instruction, setInstruction] = useState(searchParams.get('campaign_context') || '');

  // UI State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Results
  const [generations, setGenerations] = useState<GeneratedContentResponse[]>([]);
  const [postSources, setPostSources] = useState<GenerationPostSource[]>([]);

  // Load existing generations on mount
  useEffect(() => {
    if (projectId) {
      getGenerations(projectId, 0, 15)
        .then(res => setGenerations(res.data))
        .catch(err => console.error("Could not load previous generations", err));
    }
  }, [projectId]);

  useEffect(() => {
    if (projectId) getGenerationPostSources(projectId).then(res => setPostSources(res.data)).catch(() => setPostSources([]));
  }, [projectId]);

  // Periodically check status if there are QUEUED/RUNNING tasks
  useEffect(() => {
    let interval: ReturnType<typeof window.setInterval>;
    const activeTasks = generations.some(g => g.status === 'QUEUED' || g.status === 'RUNNING');

    if (activeTasks) {
      interval = setInterval(async () => {
        try {
          const updatedGens = await Promise.all(generations.map(async (g) => {
            if (g.status === 'QUEUED' || g.status === 'RUNNING') {
              const res = await getGeneration(projectId!, g.id);
              if (res.data.status === 'SUCCESS') {
                showToast('Content generation completed!', 'success');
              }
              return res.data;
            }
            return g;
          }));
          setGenerations(updatedGens);
        } catch (err: unknown) {
          // ignore polling error
        }
      }, 2500);
    }
    return () => clearInterval(interval);
  }, [generations, projectId, showToast]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    const payload: GenerationRequest = {
      generation_type: workflowMode === 'MARKETING_OPPORTUNITIES' ? 'IDEA' : 'FULL',
      workflow_mode: workflowMode,
      topic: workflowMode === 'CREATE_CONTENT' ? (topic || undefined) : undefined,
      content_type: workflowMode === 'CREATE_CONTENT' ? (contentType || undefined) : undefined,
      keywords: workflowMode === 'CREATE_CONTENT' && keyword ? [keyword] : undefined,
      campaign_context: workflowMode === 'CREATE_CONTENT' ? (instruction || undefined) : undefined,
      context_type: contextType || undefined,
      context_value: contextValue || undefined,
      context_generation_id: contextGenerationId || undefined,
      count: 1,
    };

    try {
      const res = await startGeneration(projectId!, payload);
      showToast(`Generating ${workflowMode === 'MARKETING_OPPORTUNITIES' ? 'marketing opportunities' : 'content'} with project intelligence...`, 'info');
      setGenerations([...res.data, ...generations]);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to start generation';
      setError(msg);
      showToast(msg, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegenerate = async (contentId: string, reason: string = '') => {
    try {
      showToast('Regenerating alternative variation...', 'info');
      const res = await regenerateContent(projectId!, contentId, { regeneration_reason: reason });
      setGenerations([res.data, ...generations]);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to regenerate content';
      setError(msg);
      showToast(msg, 'error');
    }
  };

  const handleRetry = async (contentId: string) => {
    setRetryingId(contentId);
    try {
      showToast('Retrying generation...', 'info');
      const res = await retryGeneration(projectId!, contentId);
      setGenerations(generations.map(g => g.id === contentId ? res.data : g));
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to retry generation';
      setError(msg);
      showToast(msg, 'error');
    } finally {
      setRetryingId(null);
    }
  };

  const copyToClipboard = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    showToast('Copied content to clipboard!', 'success');
    setTimeout(() => {
      setCopiedId(null);
    }, 2000);
  };

  return (
    <AppLayout projectId={projectId}>
      {/* Topbar */}
      <header className="topbar studio-topbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1>AI Content Studio</h1>
            <span className="status-pill status-purple">
              <Sparkles size={13} /> Gemini Generator
            </span>
          </div>
          <p className="discovery-header-subtitle">
            Generate high-converting content drafts grounded in scraped competitor intelligence and real customer reviews.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <Link to={`/projects/${projectId}/generations`} className="secondary-btn">
            <History size={15} />
            <span>Generations History</span>
          </Link>
        </div>
      </header>

      <div className="content-area">
        <div className="studio-layout">
          {/* Left Form Column */}
          <div className="studio-form-col">
            <div className="generator-card">
              <h3 style={{ margin: '0 0 16px', fontSize: '16px', color: 'white' }}>
                Generate with MapsIntel
              </h3>

              <form onSubmit={handleSubmit} className="generate-form">
                <div className="form-group">
                  <label>Mode</label>
                  <div className="mode-toggle">
                    <button
                      type="button"
                      className={`mode-btn ${workflowMode === 'MARKETING_OPPORTUNITIES' ? 'active' : ''}`}
                      onClick={() => setWorkflowMode('MARKETING_OPPORTUNITIES')}
                    >
                      <Lightbulb size={14} /> Marketing Opportunities
                    </button>
                    <button
                      type="button"
                      className={`mode-btn ${workflowMode === 'CREATE_CONTENT' ? 'active' : ''}`}
                      onClick={() => setWorkflowMode('CREATE_CONTENT')}
                    >
                      <FileText size={14} /> Create Content
                    </button>
                  </div>
                </div>

                <div className="context-indicator">
                  {workflowMode === 'MARKETING_OPPORTUNITIES'
                    ? 'Using project-wide intelligence'
                    : contextType && contextValue
                      ? `Based on ${contextType.replace('_', ' ')}: ${contextType === 'competitor_post' ? postSources.find(post => post.id === contextValue)?.business_name || 'selected post' : contextValue}`
                      : 'Using relevant project intelligence for your topic'}
                </div>

                {workflowMode === 'CREATE_CONTENT' && <>
                {contextType && contextValue && <div className="selected-context">
                  <span>Selected context: <strong>{contextType.replace('_', ' ')} · {contextType === 'competitor_post' ? postSources.find(post => post.id === contextValue)?.summary.slice(0, 90) || 'Selected post' : contextValue}</strong></span>
                  <button type="button" className="secondary-btn" onClick={() => { setContextType(''); setContextValue(''); setContextGenerationId(''); }}>Clear</button>
                </div>}
                <div className="form-group">
                  <label>Start from a competitor post (optional)</label>
                  <select value={contextType === 'competitor_post' ? contextValue : ''} onChange={e => {
                    const postId = e.target.value;
                    setContextType(postId ? 'competitor_post' : '');
                    setContextValue(postId);
                    setContextGenerationId('');
                  }}>
                    <option value="">Choose a collected post</option>
                    {postSources.map(post => <option key={post.id} value={post.id}>{post.business_name} · {(post.summary || 'Post').slice(0, 90)}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Topic Opportunity</label>
                  <input
                    type="text"
                    value={topic || (contextType === 'topic' ? contextValue : '')}
                    onChange={e => setTopic(e.target.value)}
                    placeholder="e.g. Weekend Brunch, Dessert Specials"
                  />
                </div>

                <div className="form-group">
                  <label>Target Keyword</label>
                  <input
                    type="text"
                    value={keyword}
                    onChange={e => setKeyword(e.target.value)}
                    placeholder="e.g. artisanal bakery, family dinner"
                  />
                </div>

                <div className="form-group">
                  <label>Content Format</label>
                  <input
                    type="text"
                    value={contentType}
                    onChange={e => setContentType(e.target.value)}
                    placeholder="e.g. Limited Offer, Event, Behind-the-scenes"
                  />
                </div>

                <div className="form-group">
                  <label>Custom Instructions & Tone</label>
                  <textarea
                    rows={4}
                    value={instruction}
                    onChange={e => setInstruction(e.target.value)}
                    placeholder="e.g. Highlight our fresh organic ingredients and invite readers to tag a friend..."
                  />
                </div>
                </>}

                {error && (
                  <div className="error-banner mb-3">
                    <AlertCircle size={15} />
                    <span>{error}</span>
                  </div>
                )}

                <button
                  type="submit"
                  className="primary-btn submit-btn"
                  disabled={isSubmitting}
                >
                  <Wand2 size={16} />
                  <span>
                    {isSubmitting
                      ? 'Generating with intelligence...'
                      : workflowMode === 'MARKETING_OPPORTUNITIES' ? 'Find Marketing Opportunities' : 'Create Content'}
                  </span>
                </button>
              </form>
            </div>
          </div>

          {/* Right Results Column */}
          <div className="studio-results-col">
            <div className="results-column-header">
              <h3>Generated Drafts ({generations.length})</h3>
            </div>

            {generations.length === 0 ? (
              <div className="empty-results-box">
                <Wand2 size={36} className="text-dim" />
                <h4>No Content Generated Yet</h4>
                <p>Fill in parameters on the left and click Generate to produce content backed by your competitive data.</p>
              </div>
            ) : (
              <div className="results-feed">
                {generations.map(gen => {
                  const isQueued = gen.status === 'QUEUED' || gen.status === 'RUNNING';
                  const isCopied = copiedId === gen.id;

                  return (
                    <div
                      key={gen.id}
                      className={`generation-card status-${gen.status.toLowerCase()} animate-slide-in`}
                    >
                      <div className="gen-header">
                        <span className="gen-type-badge">
                          {gen.source_context?.workflow_mode === 'MARKETING_OPPORTUNITIES' ? <Lightbulb size={13} /> : <FileText size={13} />}
                          {gen.source_context?.workflow_mode === 'MARKETING_OPPORTUNITIES' ? 'MARKETING OPPORTUNITY' : 'CONTENT DRAFT'}
                        </span>
                        <span className={`status-pill ${isQueued ? 'status-running' : gen.status === 'SUCCESS' ? 'status-success' : 'status-failed'}`}>
                          {isQueued && <span className="pulse-dot running"></span>}
                          {gen.status.replace(/_/g, ' ')}
                        </span>
                      </div>

                      {isQueued && (
                        <div className="gen-loading">
                          <div className="pulse-dot running"></div>
                          <span>Crafting post with Gemini AI...</span>
                        </div>
                      )}

                      {gen.status === 'FAILED' && (
                        <div className="gen-error-box">
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                            <AlertCircle size={16} />
                            <span>{gen.error_message || 'Generation failed'}</span>
                          </div>
                          <div className="gen-actions-bar" style={{ marginTop: '8px' }}>
                            <button
                              type="button"
                              className="secondary-btn"
                              disabled={retryingId === gen.id}
                              onClick={() => handleRetry(gen.id)}
                            >
                              <RotateCw size={14} className={retryingId === gen.id ? 'animate-spin' : ''} />
                              <span>{retryingId === gen.id ? 'Retrying...' : 'Retry Generation'}</span>
                            </button>
                          </div>
                        </div>
                      )}

                      {gen.status === 'SUCCESS' && (
                        <div className="gen-success-content">
                          {gen.source_context?.title && <h4 className="generated-title">{gen.source_context.title}</h4>}
                          <div className="content-body">
                            {gen.generation_type === 'IDEA' ? gen.generated_idea : gen.full_copy}
                          </div>

                          <div className="content-meta-tags">
                            {gen.topic && <span className="meta-tag"><Tag size={11} /> {gen.topic}</span>}
                            {gen.content_type && <span className="meta-tag">Format: {gen.content_type}</span>}
                            {gen.cta && <span className="meta-tag">CTA: {gen.cta}</span>}
                          </div>

                          {gen.image_concept && (
                            <div className="image-concept-box">
                              <strong>Visual Concept:</strong> {gen.image_concept}
                            </div>
                          )}
                          {(gen.source_context?.evidence?.post_ids?.length ?? 0) > 0 && <div className="context-indicator">Based on {gen.source_context?.evidence?.post_ids?.length} source posts · evidence IDs saved with this generation</div>}
                          {gen.source_context?.rationale && <div className="image-concept-box"><strong>Why this is relevant:</strong> {gen.source_context.rationale}</div>}

                          <div className="gen-actions-bar">
                            <button
                              className="secondary-btn"
                              onClick={() => copyToClipboard(gen.id, gen.generation_type === 'IDEA' ? gen.generated_idea || '' : gen.full_copy || '')}
                            >
                              {isCopied ? <Check size={14} className="text-success" /> : <Copy size={14} />}
                              <span>{isCopied ? 'Copied!' : 'Copy Text'}</span>
                            </button>
                            <button
                              className="secondary-btn"
                              onClick={() => handleRegenerate(gen.id)}
                            >
                              <RotateCw size={14} />
                              <span>Regenerate Variation</span>
                            </button>
                            {gen.source_context?.workflow_mode === 'MARKETING_OPPORTUNITIES' && <button className="secondary-btn" onClick={() => {
                              setWorkflowMode('CREATE_CONTENT');
                              setContextType('marketing_opportunity');
                              setContextValue(gen.topic || 'Selected marketing opportunity');
                              setContextGenerationId(gen.id);
                            }}><FileText size={14} /><span>Create content from this opportunity</span></button>}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default ProjectGenerate;
