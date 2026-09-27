import type { ReactNode } from 'react';
import { useAuth } from '../context/AuthContext';
import { Link, useLocation } from 'react-router-dom';
import '../pages/Dashboard.css'; // Reusing dashboard styles for layout

interface AppLayoutProps {
  children: ReactNode;
  projectId?: string;
}

const AppLayout = ({ children, projectId }: AppLayoutProps) => {
  const { user, logout } = useAuth();
  const location = useLocation();

  return (
    <div className="dashboard-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <Link to="/dashboard" style={{textDecoration: 'none'}}><h2>MapsIntel</h2></Link>
        </div>
        <nav className="sidebar-nav">
          <Link to="/dashboard" className={`nav-item ${location.pathname === '/dashboard' ? 'active' : ''}`}>Dashboard</Link>
          <Link to="/projects/new" className={`nav-item ${location.pathname === '/projects/new' ? 'active' : ''}`}>New Project</Link>
          
          {projectId && (
            <>
              <div className="nav-divider" style={{margin: '16px 0', borderTop: '1px solid rgba(255,255,255,0.1)'}}></div>
              <div style={{padding: '0 16px 8px', fontSize: '12px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px'}}>Project</div>
              <Link to={`/projects/${projectId}`} className={`nav-item ${location.pathname === `/projects/${projectId}` ? 'active' : ''}`}>Summary</Link>
              <Link to={`/projects/${projectId}/competitors`} className={`nav-item ${location.pathname.includes('/competitors') ? 'active' : ''}`}>Competitors</Link>
              <Link to={`/projects/${projectId}/discovery`} className={`nav-item ${location.pathname.includes('/discovery') ? 'active' : ''}`}>Discovery</Link>
              <Link to={`/projects/${projectId}/scraping`} className={`nav-item ${location.pathname.includes('/scraping') ? 'active' : ''}`}>Scraping</Link>
              
              <div className="nav-divider" style={{margin: '16px 0', borderTop: '1px solid rgba(255,255,255,0.1)'}}></div>
              <div style={{padding: '0 16px 8px', fontSize: '12px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px'}}>Intelligence</div>
              <Link to={`/projects/${projectId}/posts`} className={`nav-item ${location.pathname.includes('/posts') ? 'active' : ''}`}>Posts & Intel</Link>
              <Link to={`/projects/${projectId}/strategy`} className={`nav-item ${location.pathname.includes('/strategy') ? 'active' : ''}`}>Content Strategy</Link>
              
              <div className="nav-divider" style={{margin: '16px 0', borderTop: '1px solid rgba(255,255,255,0.1)'}}></div>
              <div style={{padding: '0 16px 8px', fontSize: '12px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px'}}>Studio</div>
              <Link to={`/projects/${projectId}/generate`} className={`nav-item ${location.pathname.includes('/generate') && !location.pathname.includes('/generations') ? 'active' : ''}`}>Generate Content</Link>
              <Link to={`/projects/${projectId}/generations`} className={`nav-item ${location.pathname.includes('/generations') ? 'active' : ''}`}>History</Link>
            </>
          )}
        </nav>
        <div className="sidebar-footer">
          <div className="user-info">
            <div className="avatar">{user?.email?.[0].toUpperCase()}</div>
            <div className="user-details">
              <span className="user-name">{user?.full_name || 'User'}</span>
              <span className="user-ws">Workspace</span>
            </div>
          </div>
          <button onClick={logout} className="logout-btn">Logout</button>
        </div>
      </aside>
      
      <main className="main-content">
        {children}
      </main>
    </div>
  );
};

export default AppLayout;
