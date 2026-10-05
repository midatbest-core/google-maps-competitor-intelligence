
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Dashboard from './pages/Dashboard';
import CreateProject from './pages/CreateProject';
import ProjectDashboard from './pages/ProjectDashboard';
import ProjectCompetitors from './pages/ProjectCompetitors';
import ProjectDiscovery from './pages/ProjectDiscovery';
import ProjectScraping from './pages/ProjectScraping';
import ProjectPosts from './pages/ProjectPosts';
import ProjectStrategy from './pages/ProjectStrategy';
import ProjectGenerate from './pages/ProjectGenerate';
import ProjectGenerations from './pages/ProjectGenerations';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/projects/new" element={<CreateProject />} />
          <Route path="/projects/:projectId" element={<ProjectDashboard />} />
          <Route path="/projects/:projectId/competitors" element={<ProjectCompetitors />} />
          <Route path="/projects/:projectId/discovery" element={<ProjectDiscovery />} />
          <Route path="/projects/:projectId/scraping" element={<ProjectScraping />} />
          <Route path="/projects/:projectId/posts" element={<ProjectPosts />} />
          <Route path="/projects/:projectId/strategy" element={<ProjectStrategy />} />
          <Route path="/projects/:projectId/generate" element={<ProjectGenerate />} />
          <Route path="/projects/:projectId/generations" element={<ProjectGenerations />} />
          {/* Placeholders for project modules */}
          <Route path="/projects/:projectId/*" element={<ProjectDashboard />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
