import { useState, useEffect } from 'react';
import { getProjects } from '../api';
import { useNavigate } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import './Dashboard.css';

interface Project {
  id: string;
  name: string;
  description?: string;
}

const Dashboard = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      setLoading(true);
      const res = await getProjects();
      setProjects(res.data);
    } catch (err) {
      setError('Unable to load projects. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppLayout>
      <header className="topbar">
        <h1>Dashboard Overview</h1>
      </header>
      
      <div className="content-area">
        <div className="welcome-card mb-6">
          <h2>Welcome back!</h2>
          <p>Select a project to view intelligence data, or create a new one.</p>
          <button className="primary-btn mt-4" onClick={() => navigate('/projects/new')}>Create New Project</button>
        </div>
          
          <h2 className="section-title mt-6">Your Projects</h2>
          
          {loading && <div className="state-message">Loading projects...</div>}
          {error && <div className="state-message error">{error}</div>}
          
          {!loading && !error && projects.length === 0 && (
            <div className="empty-state">
              <p>No projects yet. Create your first project to get started.</p>
              <button className="secondary-btn mt-4" onClick={() => navigate('/projects/new')}>Create Project</button>
            </div>
          )}
          
          {!loading && !error && projects.length > 0 && (
            <div className="projects-grid mt-4">
              {projects.map(p => (
                <div key={p.id} className="project-card" onClick={() => navigate(`/projects/${p.id}`)}>
                  <h3>{p.name}</h3>
                  {p.description && <p>{p.description}</p>}
                  <button className="open-btn">Open Project &rarr;</button>
                </div>
              ))}
            </div>
          )}
      </div>
    </AppLayout>
  );
};

export default Dashboard;
