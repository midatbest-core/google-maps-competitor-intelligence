import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { startGeneration, regenerateContent } from '../api';
import type { GenerationRequest, GeneratedContentResponse } from '../api';
import ReviewIntelligence from '../components/ReviewIntelligence';
import './ProjectGenerate.css';

const ProjectGenerate: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();

  // Inputs
  const [generationType, setGenerationType] = useState<'IDEA' | 'FULL'>('IDEA');
  const [topic, setTopic] = useState(searchParams.get('topic') || '');
  const [keyword, setKeyword] = useState(searchParams.get('keyword') || '');
  const [contentType, setContentType] = useState(searchParams.get('content_type') || '');
  const [instruction, setInstruction] = useState('');

  // UI State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Results
  const [generations, setGenerations] = useState<GeneratedContentResponse[]>([]);

  // Periodically check status if there are QUEUED/RUNNING tasks
  useEffect(() => {
    let interval: ReturnType<typeof window.setInterval>;
    const activeTasks = generations.some(g => g.status === 'QUEUED' || g.status === 'RUNNING');
    
    if (activeTasks) {
      interval = setInterval(async () => {
        // Just refresh the whole history endpoint for simplicity, or we can fetch individually.
        // Actually since we don't have getGenerations here yet, let's just fetch the specific ones
        // but to avoid complexity we can just wait or do individual polls.
        // I will do a quick refresh of active tasks using getGeneration in a loop.
        try {
          const updatedGens = await Promise.all(generations.map(async (g) => {
            if (g.status === 'QUEUED' || g.status === 'RUNNING') {
              const { getGeneration } = await import('../api');
              const res = await getGeneration(projectId!, g.id);
              return res.data;
            }
            return g;
          }));
          setGenerations(updatedGens);
        } catch (err: unknown) {
          // preserve existing flow, do not crash or spam
        }
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [generations, projectId]);


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    const payload: GenerationRequest = {
      generation_type: generationType,
      topic: topic || undefined,
      content_type: contentType || undefined,
      keywords: keyword ? [keyword] : undefined,
      campaign_context: instruction || undefined,
      count: generationType === 'IDEA' ? 3 : 1, // Generate 3 ideas, or 1 full post
    };

    try {
      const res = await startGeneration(projectId!, payload);
      // Prepend to current session generations
      setGenerations([...res.data, ...generations]);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axErr = err as { response?: { data?: { detail?: string } } };
        setError(axErr.response?.data?.detail || 'Failed to start generation');
      } else {
        setError('Failed to start generation');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegenerate = async (contentId: string, reason: string = '') => {
    try {
      const res = await regenerateContent(projectId!, contentId, { regeneration_reason: reason });
      setGenerations([res.data, ...generations]);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axErr = err as { response?: { data?: { detail?: string } } };
        setError(axErr.response?.data?.detail || 'Failed to regenerate content');
      } else {
        setError('Failed to regenerate content');
      }
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    // Simple visual feedback could be added here
  };

  return (
    <AppLayout projectId={projectId}>
      <div className="generate-container">
        <div className="generate-header">
          <h2>Generation Studio</h2>
          <p>Create content backed by your project's intelligence context.</p>
          <div className="header-actions">
            <Link to={`/projects/${projectId}/generations`} className="btn-secondary">View History</Link>
          </div>
        </div>

        <div className="studio-layout">
          {/* Form Column */}
          <div className="studio-form-col" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {projectId && <ReviewIntelligence projectId={projectId} />}
            <form onSubmit={handleSubmit} className="generate-form">
              <div className="form-group">
                <label>Generation Mode</label>
                <div className="mode-toggle">
                  <button 
                    type="button"
                    className={`mode-btn ${generationType === 'IDEA' ? 'active' : ''}`}
                    onClick={() => setGenerationType('IDEA')}
                  >
                    Brainstorm Ideas
                  </button>
                  <button 
                    type="button"
                    className={`mode-btn ${generationType === 'FULL' ? 'active' : ''}`}
                    onClick={() => setGenerationType('FULL')}
                  >
                    Full Update Post
                  </button>
                </div>
              </div>

              <div className="form-group">
                <label>Topic</label>
                <input 
                  type="text" 
                  value={topic} 
                  onChange={e => setTopic(e.target.value)} 
                  placeholder="e.g. Weekend Dining (Optional)"
                />
              </div>

              <div className="form-group">
                <label>Target Keyword</label>
                <input 
                  type="text" 
                  value={keyword} 
                  onChange={e => setKeyword(e.target.value)} 
                  placeholder="e.g. family dinner (Optional)"
                />
              </div>

              <div className="form-group">
                <label>Content Format</label>
                <input 
                  type="text" 
                  value={contentType} 
                  onChange={e => setContentType(e.target.value)} 
                  placeholder="e.g. Offer (Optional)"
                />
              </div>

              <div className="form-group">
                <label>Instructions & Context</label>
                <textarea 
                  rows={4}
                  value={instruction} 
                  onChange={e => setInstruction(e.target.value)} 
                  placeholder="e.g. We are offering a 20% discount on family dinners this weekend..."
                />
              </div>

              {error && <div className="error-message">{error}</div>}

              <button type="submit" className="btn-primary submit-btn" disabled={isSubmitting}>
                {isSubmitting ? 'Starting...' : `Generate ${generationType === 'IDEA' ? 'Ideas' : 'Content'}`}
              </button>
            </form>
          </div>

          {/* Results Column */}
          <div className="studio-results-col">
            {generations.length === 0 ? (
              <div className="empty-results">
                Generations will appear here.
              </div>
            ) : (
              <div className="results-feed">
                {generations.map(gen => (
                  <div key={gen.id} className={`generation-card status-${gen.status.toLowerCase()}`}>
                    
                    <div className="gen-header">
                      <span className="gen-type">{gen.generation_type}</span>
                      <span className={`status-badge ${gen.status.toLowerCase()}`}>{gen.status.replace('_', ' ')}</span>
                    </div>

                    {(gen.status === 'QUEUED' || gen.status === 'RUNNING') && (
                      <div className="gen-loading">
                        <div className="spinner"></div>
                        <span>Processing with AI...</span>
                      </div>
                    )}

                    {gen.status === 'FAILED' && (
                      <div className="gen-error">
                        <strong>Error:</strong> {gen.error_message}
                      </div>
                    )}

                    {gen.status === 'REJECTED_DUPLICATE' && (
                      <div className="gen-duplicate">
                        <p><strong>Content Rejected:</strong> {gen.error_message}</p>
                        <p>This content was too similar to existing material. Duplicate protection blocked it.</p>
                        <button className="btn-secondary btn-sm" onClick={() => handleRegenerate(gen.id, "Generate something different. Previous attempt was a duplicate.")}>
                          Regenerate Difference
                        </button>
                      </div>
                    )}

                    {gen.status === 'SUCCESS' && (
                      <div className="gen-success">
                        {gen.generation_type === 'IDEA' ? (
                          <div className="content-body idea-body">
                            {gen.generated_idea}
                          </div>
                        ) : (
                          <div className="content-body full-body">
                            {gen.full_copy}
                          </div>
                        )}

                        <div className="content-meta">
                          {gen.topic && <span className="meta-tag">Topic: {gen.topic}</span>}
                          {gen.content_type && <span className="meta-tag">Type: {gen.content_type}</span>}
                          {gen.cta && <span className="meta-tag">CTA: {gen.cta}</span>}
                        </div>

                        {gen.keywords && gen.keywords.length > 0 && (
                          <div className="content-keywords">
                            <strong>Keywords:</strong> {gen.keywords.join(', ')}
                          </div>
                        )}
                        
                        {gen.image_concept && (
                          <div className="content-image-concept">
                            <strong>Image Concept:</strong> {gen.image_concept}
                          </div>
                        )}

                        <div className="gen-actions">
                          <button className="btn-secondary btn-sm" onClick={() => copyToClipboard(gen.generation_type === 'IDEA' ? gen.generated_idea || '' : gen.full_copy || '')}>
                            Copy Content
                          </button>
                          <button className="btn-secondary btn-sm" onClick={() => handleRegenerate(gen.id)}>
                            Regenerate
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default ProjectGenerate;
