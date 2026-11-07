import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import '../pages/Dashboard.css';

interface AppLayoutProps {
  children: ReactNode;
  projectId?: string;
}

const AppLayout = ({ children, projectId }: AppLayoutProps) => {
  const location = useLocation();
  const { user, logout } = useAuth();

  return (
    <div className="dashboard-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <Link to="/dashboard" style={{ textDecoration: 'none' }}>
            <h2>MapsIntel</h2>
          </Link>
        </div>
        <nav className="sidebar-nav">
          <Link to="/dashboard" className={`nav-item ${location.pathname === '/dashboard' ? 'active' : ''}`}>
            Dashboard
          </Link>
          <Link to="/projects/new" className={`nav-item ${location.pathname === '/projects/new' ? 'active' : ''}`}>
            New Project
          </Link>

          {projectId && (
            <>
              <div className="nav-divider" style={{ margin: '16px 0', borderTop: '1px solid rgba(255,255,255,0.1)' }}></div>
              <div style={{ padding: '0 16px 8px', fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px' }}>
                Project
              </div>
              <Link to={`/projects/${projectId}`} className={`nav-item ${location.pathname === `/projects/${projectId}` ? 'active' : ''}`}>
                Summary
              </Link>
              <Link to={`/projects/${projectId}/competitors`} className={`nav-item ${location.pathname.includes('/competitors') ? 'active' : ''}`}>
                Competitors
              </Link>
              <Link to={`/projects/${projectId}/discovery`} className={`nav-item ${location.pathname.includes('/discovery') ? 'active' : ''}`}>
                Discovery
              </Link>
              <Link to={`/projects/${projectId}/scraping`} className={`nav-item ${location.pathname.includes('/scraping') ? 'active' : ''}`}>
                Scraping
              </Link>

              <div className="nav-divider" style={{ margin: '16px 0', borderTop: '1px solid rgba(255,255,255,0.1)' }}></div>
              <div style={{ padding: '0 16px 8px', fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px' }}>
                Intelligence
              </div>
              <Link to={`/projects/${projectId}/posts`} className={`nav-item ${location.pathname.includes('/posts') ? 'active' : ''}`}>
                Business Posts
              </Link>
              <Link to={`/projects/${projectId}/reviews`} className={`nav-item ${location.pathname.includes('/reviews') ? 'active' : ''}`}>
                Customer Reviews
              </Link>
              <Link to={`/projects/${projectId}/intelligence`} className={`nav-item ${location.pathname.includes('/intelligence') ? 'active' : ''}`}>
                Combined Intelligence
              </Link>
              <Link to={`/projects/${projectId}/strategy`} className={`nav-item ${location.pathname.includes('/strategy') ? 'active' : ''}`}>
                Content Strategy
              </Link>

              <div className="nav-divider" style={{ margin: '16px 0', borderTop: '1px solid rgba(255,255,255,0.1)' }}></div>
              <div style={{ padding: '0 16px 8px', fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px' }}>
                Studio
              </div>
              <Link to={`/projects/${projectId}/generate`} className={`nav-item ${location.pathname.includes('/generate') && !location.pathname.includes('/generations') ? 'active' : ''}`}>
                Generate Content
              </Link>
              <Link to={`/projects/${projectId}/generations`} className={`nav-item ${location.pathname.includes('/generations') ? 'active' : ''}`}>
                History
              </Link>
            </>
          )}
        </nav>

        <div style={{ marginTop: 'auto', flexShrink: 0, padding: '16px', borderTop: '1px solid rgba(255,255,255,0.08)', background: '#13151a' }}>
          {user ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontSize: '12px', color: '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user.email}
              </div>
              <button
                onClick={logout}
                style={{
                  background: 'transparent',
                  border: '1px solid #334155',
                  color: '#cbd5e1',
                  borderRadius: '4px',
                  padding: '6px 10px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                Sign Out
              </button>
            </div>
          ) : (
            <Link
              to="/login"
              style={{
                display: 'block',
                textAlign: 'center',
                padding: '8px',
                background: '#334155',
                color: '#f8fafc',
                borderRadius: '6px',
                fontSize: '13px',
                textDecoration: 'none',
              }}
            >
              Sign In
            </Link>
          )}
        </div>
      </aside>

      <main className="main-content">
        {children}
      </main>
    </div>
  );
};

export default AppLayout;
