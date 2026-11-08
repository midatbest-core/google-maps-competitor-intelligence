import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
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
import ProjectReviews from './pages/ProjectReviews';
import ProjectIntelligence from './pages/ProjectIntelligence';
import ProjectStrategy from './pages/ProjectStrategy';
import ProjectGenerate from './pages/ProjectGenerate';
import ProjectGenerations from './pages/ProjectGenerations';

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
            <Route path="/projects/:projectId/reviews" element={<ProjectReviews />} />
            <Route path="/projects/:projectId/intelligence" element={<ProjectIntelligence />} />
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
