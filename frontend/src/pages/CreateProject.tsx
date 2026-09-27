import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createProject } from '../api';
import AppLayout from '../components/AppLayout';
import './CreateProject.css';

const CreateProject = () => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Project name is required');
      return;
    }
    
    try {
      setSubmitting(true);
      setError('');
      const res = await createProject({ name: name.trim(), description: description.trim() || undefined });
      navigate(`/projects/${res.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create project');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppLayout>
      <header className="topbar">
        <h1>Create New Project</h1>
      </header>
      
      <div className="content-area">
        <div className="form-container">
            <h2>Project Details</h2>
            <p className="form-subtitle">Set up a new project to start tracking competitors and content.</p>
            
            {error && <div className="state-message error">{error}</div>}
            
            <form onSubmit={handleSubmit} className="create-form">
              <div className="form-group">
                <label>Project Name *</label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="e.g. Q3 Market Expansion"
                  required
                  maxLength={100}
                />
              </div>
              
              <div className="form-group">
                <label>Description (Optional)</label>
                <textarea
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  placeholder="Briefly describe the goals of this project..."
                  rows={4}
                  maxLength={500}
                />
              </div>
              
              <div className="form-actions">
                <button type="button" className="secondary-btn" onClick={() => navigate(-1)}>Cancel</button>
                <button type="submit" className="primary-btn" disabled={submitting}>
                  {submitting ? 'Creating...' : 'Create Project'}
                </button>
              </div>
            </form>
        </div>
      </div>
    </AppLayout>
  );
};

export default CreateProject;
