import { useState } from 'react';
import { useAuth } from '../context/auth';
import api, { getApiErrorMessage, notifyError } from '../api';
import './Login.css';

const Login = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      const message = 'Password must be at least 8 characters.';
      setError(message);
      notifyError(message);
      return;
    }

    try {
      setSubmitting(true);
      if (isLogin) {
        const response = await api.post('/auth/login', { email, password });
        await login(response.data.access_token);
        window.location.href = '/dashboard';
      } else {
        await api.post('/auth/register', { email, password, full_name: fullName });
        // Automatically login after register
        const loginRes = await api.post('/auth/login', { email, password });
        await login(loginRes.data.access_token);
        window.location.href = '/dashboard';
      }
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Unable to authenticate'));
    } finally {
      setSubmitting(false);
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
              minLength={8}
              required
            />
            <small className="field-hint">Use at least 8 characters.</small>
          </div>
          
          <button type="submit" className="submit-btn" disabled={submitting}>
            {submitting ? 'Please wait…' : (isLogin ? 'Sign In' : 'Register')}
          </button>
        </form>
        
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
