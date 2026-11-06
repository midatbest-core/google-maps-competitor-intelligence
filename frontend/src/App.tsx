
import { lazy, Suspense, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/auth';
import ToastHost from './components/ToastHost';

const Login = lazy(() => import('./pages/Login'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const CreateProject = lazy(() => import('./pages/CreateProject'));
const ProjectDashboard = lazy(() => import('./pages/ProjectDashboard'));
const ProjectCompetitors = lazy(() => import('./pages/ProjectCompetitors'));
const ProjectDiscovery = lazy(() => import('./pages/ProjectDiscovery'));
const ProjectScraping = lazy(() => import('./pages/ProjectScraping'));
const ProjectPosts = lazy(() => import('./pages/ProjectPosts'));
const ProjectStrategy = lazy(() => import('./pages/ProjectStrategy'));
const ProjectGenerate = lazy(() => import('./pages/ProjectGenerate'));
const ProjectGenerations = lazy(() => import('./pages/ProjectGenerations'));

const PageSkeleton = () => (
  <div className="page-skeleton" aria-label="Loading page">
    <div className="skeleton skeleton-heading" />
    <div className="skeleton-grid">
      <div className="skeleton skeleton-card" />
      <div className="skeleton skeleton-card" />
      <div className="skeleton skeleton-card" />
    </div>
  </div>
);

const ProtectedRoute = ({ children }: { children: ReactNode }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return <PageSkeleton />;
  }

  return user ? children : <Navigate to="/login" replace />;
};

const PublicOnlyRoute = ({ children }: { children: ReactNode }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return <PageSkeleton />;
  }

  return user ? <Navigate to="/dashboard" replace /> : children;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <ToastHost />
        <Suspense fallback={<PageSkeleton />}>
        <Routes>
          <Route path="/login" element={<PublicOnlyRoute><Login /></PublicOnlyRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/projects/new" element={<ProtectedRoute><CreateProject /></ProtectedRoute>} />
          <Route path="/projects/:projectId" element={<ProtectedRoute><ProjectDashboard /></ProtectedRoute>} />
          <Route path="/projects/:projectId/competitors" element={<ProtectedRoute><ProjectCompetitors /></ProtectedRoute>} />
          <Route path="/projects/:projectId/discovery" element={<ProtectedRoute><ProjectDiscovery /></ProtectedRoute>} />
          <Route path="/projects/:projectId/scraping" element={<ProtectedRoute><ProjectScraping /></ProtectedRoute>} />
          <Route path="/projects/:projectId/posts" element={<ProtectedRoute><ProjectPosts /></ProtectedRoute>} />
          <Route path="/projects/:projectId/strategy" element={<ProtectedRoute><ProjectStrategy /></ProtectedRoute>} />
          <Route path="/projects/:projectId/generate" element={<ProtectedRoute><ProjectGenerate /></ProtectedRoute>} />
          <Route path="/projects/:projectId/generations" element={<ProtectedRoute><ProjectGenerations /></ProtectedRoute>} />
          <Route path="/projects/:projectId/*" element={<ProtectedRoute><ProjectDashboard /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
