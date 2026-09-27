import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
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

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return <div style={{ color: 'white', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: '#0f172a' }}>Loading...</div>;
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          } />
          <Route path="/projects/new" element={
            <ProtectedRoute>
              <CreateProject />
            </ProtectedRoute>
          } />
          <Route path="/projects/:projectId" element={
            <ProtectedRoute>
              <ProjectDashboard />
            </ProtectedRoute>
          } />
          <Route path="/projects/:projectId/competitors" element={
            <ProtectedRoute>
              <ProjectCompetitors />
            </ProtectedRoute>
          } />
          <Route path="/projects/:projectId/discovery" element={
            <ProtectedRoute>
              <ProjectDiscovery />
            </ProtectedRoute>
          } />
          <Route path="/projects/:projectId/scraping" element={
            <ProtectedRoute>
              <ProjectScraping />
            </ProtectedRoute>
          } />
          <Route path="/projects/:projectId/posts" element={
            <ProtectedRoute>
              <ProjectPosts />
            </ProtectedRoute>
          } />
          <Route path="/projects/:projectId/strategy" element={
            <ProtectedRoute>
              <ProjectStrategy />
            </ProtectedRoute>
          } />
          <Route path="/projects/:projectId/generate" element={
            <ProtectedRoute>
              <ProjectGenerate />
            </ProtectedRoute>
          } />
          <Route path="/projects/:projectId/generations" element={
            <ProtectedRoute>
              <ProjectGenerations />
            </ProtectedRoute>
          } />
          {/* Placeholders for project modules */}
          <Route path="/projects/:projectId/*" element={
            <ProtectedRoute>
              <ProjectDashboard />
            </ProtectedRoute>
          } />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
