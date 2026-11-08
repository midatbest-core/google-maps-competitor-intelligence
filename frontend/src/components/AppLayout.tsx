import { useState, useEffect, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard,
  Users,
  Compass,
  Database,
  FileText,
  MessageSquareHeart,
  Sparkles,
  Target,
  Wand2,
  History,
  Menu,
  X,
  LogOut,
  ChevronRight,
  MapPin,
  FolderPlus
} from 'lucide-react';
import '../pages/Dashboard.css';

interface AppLayoutProps {
  children: ReactNode;
  projectId?: string;
  projectName?: string;
}

const AppLayout = ({ children, projectId, projectName }: AppLayoutProps) => {
  const location = useLocation();
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  const navItemClass = (path: string, exact: boolean = false) => {
    const isActive = exact ? location.pathname === path : location.pathname.includes(path);
    return `modern-nav-item ${isActive ? 'active' : ''}`;
  };

  return (
    <div className="dashboard-layout">
      {/* Mobile Header Bar */}
      <div className="mobile-header">
        <button
          className="mobile-menu-btn"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle navigation menu"
        >
          {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
        <Link to="/dashboard" className="mobile-brand">
          <MapPin size={20} className="brand-icon" />
          <span>MapsIntel</span>
        </Link>
        {projectId && (
          <span className="mobile-project-badge" title={projectName}>
            {projectName || 'Project'}
          </span>
        )}
      </div>

      {/* Mobile Drawer Backdrop */}
      {mobileMenuOpen && (
        <div
          className="mobile-backdrop"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Main Sidebar */}
      <aside className={`sidebar ${mobileMenuOpen ? 'mobile-open' : ''}`}>
        <div className="sidebar-brand">
          <Link to="/dashboard" className="brand-logo">
            <div className="brand-icon-box">
              <MapPin size={20} />
            </div>
            <div className="brand-text">
              <h2>MapsIntel</h2>
              <span className="brand-subtitle">Competitor Radar</span>
            </div>
          </Link>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-group-title">WORKSPACE</div>
          <Link to="/dashboard" className={navItemClass('/dashboard', true)}>
            <LayoutDashboard size={18} />
            <span>Dashboard</span>
          </Link>
          <Link to="/projects/new" className={navItemClass('/projects/new', true)}>
            <FolderPlus size={18} />
            <span>New Project</span>
          </Link>

          {projectId && (
            <>
              {/* SETUP & ROSTER */}
              <div className="nav-group-title">SETUP & ROSTER</div>
              <Link to={`/projects/${projectId}`} className={navItemClass(`/projects/${projectId}`, true)}>
                <LayoutDashboard size={18} />
                <span>Overview</span>
              </Link>
              <Link to={`/projects/${projectId}/competitors`} className={navItemClass(`/projects/${projectId}/competitors`)}>
                <Users size={18} />
                <span>Competitor Roster</span>
              </Link>
              <Link to={`/projects/${projectId}/discovery`} className={navItemClass(`/projects/${projectId}/discovery`)}>
                <Compass size={18} />
                <span>Discovery Scout</span>
                <span className="nav-badge-scout">SCOUT</span>
              </Link>

              {/* DATA PIPELINE */}
              <div className="nav-group-title">DATA PIPELINE</div>
              <Link to={`/projects/${projectId}/scraping`} className={navItemClass(`/projects/${projectId}/scraping`)}>
                <Database size={18} />
                <span>Scraping Pipeline</span>
              </Link>

              {/* AUDIT & INTELLIGENCE */}
              <div className="nav-group-title">INTELLIGENCE</div>
              <Link to={`/projects/${projectId}/posts`} className={navItemClass(`/projects/${projectId}/posts`)}>
                <FileText size={18} />
                <span>Business Posts</span>
              </Link>
              <Link to={`/projects/${projectId}/reviews`} className={navItemClass(`/projects/${projectId}/reviews`)}>
                <MessageSquareHeart size={18} />
                <span>Customer Reviews</span>
              </Link>
              <Link to={`/projects/${projectId}/intelligence`} className={navItemClass(`/projects/${projectId}/intelligence`)}>
                <Sparkles size={18} />
                <span>Combined Intel</span>
              </Link>
              <Link to={`/projects/${projectId}/strategy`} className={navItemClass(`/projects/${projectId}/strategy`)}>
                <Target size={18} />
                <span>Content Strategy</span>
              </Link>

              {/* STUDIO */}
              <div className="nav-group-title">STUDIO</div>
              <Link
                to={`/projects/${projectId}/generate`}
                className={`modern-nav-item ${location.pathname.includes('/generate') && !location.pathname.includes('/generations') ? 'active' : ''}`}
              >
                <Wand2 size={18} />
                <span>Generate Content</span>
              </Link>
              <Link to={`/projects/${projectId}/generations`} className={navItemClass(`/projects/${projectId}/generations`)}>
                <History size={18} />
                <span>Generation History</span>
              </Link>
            </>
          )}
        </nav>

        {/* User Footer */}
        <div className="sidebar-footer">
          {user ? (
            <div className="user-profile-box">
              <div className="user-avatar-pill">
                {(user.email || 'U')[0].toUpperCase()}
              </div>
              <div className="user-meta">
                <span className="user-email-text" title={user.email}>{user.email}</span>
                <span className="user-role-badge">Online</span>
              </div>
              <button
                onClick={logout}
                className="user-logout-icon-btn"
                title="Sign out"
                aria-label="Sign out"
              >
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <Link to="/login" className="login-link-btn">
              Sign In <ChevronRight size={14} />
            </Link>
          )}
        </div>
      </aside>

      {/* Main Page Content */}
      <main className="main-content">
        {children}
      </main>
    </div>
  );
};

export default AppLayout;
