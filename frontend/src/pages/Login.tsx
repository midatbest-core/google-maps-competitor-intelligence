import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import api, { getDemoStatus, demoLogin } from '../api';
import './Login.css';

const Login = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [demoEnabled, setDemoEnabled] = useState(false);
  const [demoSubmitting, setDemoSubmitting] = useState(false);
  const { login } = useAuth();

  useEffect(() => {
    getDemoStatus()
      .then((res) => {
        if (res.data?.enabled) {
          setDemoEnabled(true);
        }
      })
      .catch(() => {
        setDemoEnabled(false);
      });
  }, []);

  const handleDemoLogin = async () => {
    try {
      setDemoSubmitting(true);
      setError('');
      const response = await demoLogin();
      login(response.data.access_token);
      window.location.href = '/dashboard';
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Demo login failed');
    } finally {
      setDemoSubmitting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      if (isLogin) {
        const response = await api.post('/auth/login', { email, password });
        login(response.data.access_token);
        window.location.href = '/dashboard';
      } else {
        await api.post('/auth/register', { email, password, full_name: fullName });
        // Automatically login after register
        const loginRes = await api.post('/auth/login', { email, password });
        login(loginRes.data.access_token);
        window.location.href = '/dashboard';
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'An error occurred');
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h1>{isLogin ? 'Welcome Back' : 'Create Account'}</h1>
        <p className="subtitle">Sign in to your Maps Intelligence dashboard</p>
        
        {error && <div className="error-message">{error}</div>}
        
        <form onSubmit={handleSubmit}>
          {!isLogin && (
            <div className="form-group">
              <label>Full Name</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="John Doe"
              />
            </div>
          )}
          
          <div className="form-group">
            <label>Email Address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>
          
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>
          
          <button type="submit" className="submit-btn">
            {isLogin ? 'Sign In' : 'Register'}
          </button>
        </form>

        {demoEnabled && (
          <div className="demo-login-section">
            <div className="demo-divider">
              <span>Live Demonstration</span>
            </div>
            <button
              type="button"
              className="demo-login-btn"
              onClick={handleDemoLogin}
              disabled={demoSubmitting}
            >
              <span className="demo-icon">⚡</span>
              <span>{demoSubmitting ? 'Accessing Demo...' : 'Admin Quick Login'}</span>
            </button>
            <p className="demo-disclaimer">
              Demo Access • Pre-configured Workspace
            </p>
          </div>
        )}
        
        <p className="toggle-text">
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <span onClick={() => setIsLogin(!isLogin)} className="toggle-link">
            {isLogin ? 'Sign up' : 'Log in'}
          </span>
        </p>
      </div>
    </div>
  );
};

export default Login;
