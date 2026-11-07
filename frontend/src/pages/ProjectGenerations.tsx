import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import { getGenerations } from '../api';
import type { GeneratedContentResponse } from '../api';
import './ProjectGenerations.css';

const ProjectGenerations: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  
  const [generations, setGenerations] = useState<GeneratedContentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (projectId) {
      loadHistory();
    }
  }, [projectId]);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const res = await getGenerations(projectId!);
      setGenerations(res.data);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axErr = err as { response?: { data?: { detail?: string } } };
        setError(axErr.response?.data?.detail || 'Failed to load generation history');
      } else {
        setError('Failed to load generation history');
      }
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <AppLayout projectId={projectId}>
      <div className="history-container">
        <div className="history-header">
          <h2>Generation History</h2>
          <p>Review and copy past AI-generated ideas and content.</p>
          <div className="header-actions">
            <Link to={`/projects/${projectId}/generate`} className="btn-primary">Generate New</Link>
          </div>
        </div>

        {loading ? (
          <div className="loading-state">Loading history...</div>
        ) : error ? (
          <div className="error-message">{error}</div>
        ) : generations.length === 0 ? (
          <div className="empty-state">
            <p>No content generated yet.</p>
            <Link to={`/projects/${projectId}/generate`} className="btn-primary">Create your first post</Link>
          </div>
        ) : (
          <div className="history-grid">
            {generations.map(gen => (
              <div key={gen.id} className={`history-card status-${gen.status.toLowerCase()}`}>
                <div className="card-top">
                  <span className="gen-type">{gen.generation_type}</span>
                  <span className={`status-badge ${gen.status.toLowerCase()}`}>{gen.status.replace('_', ' ')}</span>
                  <span className="gen-date">{new Date(gen.created_at).toLocaleDateString()}</span>
                </div>
                
                <div className="card-content">
                  {gen.status === 'SUCCESS' ? (
                    <div className="content-preview">
                      {gen.generation_type === 'IDEA' ? gen.generated_idea : gen.full_copy}
                    </div>
                  ) : gen.status === 'REJECTED_DUPLICATE' ? (
                    <div className="error-preview">
                      Duplicate protection rejected this generation.
                    </div>
                  ) : gen.status === 'FAILED' ? (
                    <div className="error-preview">
                      Generation failed.
                    </div>
                  ) : (
                    <div className="processing-preview">
                      Processing...
                    </div>
                  )}
                </div>

                <div className="card-meta">
                  {gen.topic && <span>Topic: {gen.topic}</span>}
                  {gen.content_type && <span>Type: {gen.content_type}</span>}
                </div>

                <div className="card-actions">
                  {gen.status === 'SUCCESS' && (
                    <button 
                      className="btn-secondary btn-sm"
                      onClick={() => copyToClipboard(gen.generation_type === 'IDEA' ? gen.generated_idea || '' : gen.full_copy || '')}
                    >
                      Copy
                    </button>
                  )}
                  {gen.status === 'REJECTED_DUPLICATE' && (
                    <Link to={`/projects/${projectId}/generate?regenerate=${gen.id}`} className="btn-secondary btn-sm">
                      Retry
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default ProjectGenerations;
