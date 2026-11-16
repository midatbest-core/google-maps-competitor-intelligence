import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import CreateProject from './pages/CreateProject';
import ProjectDashboard from './pages/ProjectDashboard';
import ProjectCompetitors from './pages/ProjectCompetitors';
import ProjectDiscovery from './pages/ProjectDiscovery';
import ProjectScraping from './pages/ProjectScraping';
import ProjectPosts from './pages/ProjectPosts';
// Temporarily hidden: Combined Intelligence Engine (restore by uncommenting import and route element)
// import ProjectIntelligence from './pages/ProjectIntelligence';
import ProjectStrategy from './pages/ProjectStrategy';
import ProjectGenerate from './pages/ProjectGenerate';
import ProjectGenerations from './pages/ProjectGenerations';

const ProjectReviewsRedirect = () => {
  const { projectId } = useParams<{ projectId: string }>();
  return <Navigate to={`/projects/${projectId}/posts`} replace />;
};

const ProjectIntelligenceRedirect = () => {
  const { projectId } = useParams<{ projectId: string }>();
  return <Navigate to={`/projects/${projectId}`} replace />;
};

function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/projects/new" element={<CreateProject />} />
            <Route path="/projects/:projectId" element={<ProjectDashboard />} />
            <Route path="/projects/:projectId/competitors" element={<ProjectCompetitors />} />
            <Route path="/projects/:projectId/discovery" element={<ProjectDiscovery />} />
            <Route path="/projects/:projectId/scraping" element={<ProjectScraping />} />
            <Route path="/projects/:projectId/posts" element={<ProjectPosts />} />
            <Route path="/projects/:projectId/reviews" element={<ProjectReviewsRedirect />} />
            {/* Temporarily redirect direct URL access to project overview */}
            <Route path="/projects/:projectId/intelligence" element={<ProjectIntelligenceRedirect />} />
            <Route path="/projects/:projectId/strategy" element={<ProjectStrategy />} />
            <Route path="/projects/:projectId/generate" element={<ProjectGenerate />} />
            <Route path="/projects/:projectId/generations" element={<ProjectGenerations />} />
            <Route path="/projects/:projectId/*" element={<ProjectDashboard />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
}

export default App;
