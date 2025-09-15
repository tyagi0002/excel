import React, { useState } from 'react';
import Interview from './Interview';
import './App.css';

function App() {
  const [currentView, setCurrentView] = useState('home');
  const [sessionData, setSessionData] = useState(null);

  const startInterview = (data) => {
    setSessionData(data);
    setCurrentView('interview');
  };

  const showReport = () => {
    setCurrentView('report');
  };

  const goHome = () => {
    setCurrentView('home');
    setSessionData(null);
  };

  if (currentView === 'interview') {
    return (
      <div className="App">
        <Interview 
          sessionData={sessionData}
          onComplete={showReport}
          onHome={goHome}
        />
      </div>
    );
  }

  if (currentView === 'report') {
    return (
      <div className="App">
        <InterviewReport sessionId={sessionData?.session_id} onHome={goHome} />
      </div>
    );
  }

  return (
    <div className="App">
      <header className="App-header">
        <h1>🧮 Excel AI Mock Interviewer</h1>
        <p>Test your Excel skills with our AI-powered interviewer</p>
        <InterviewSetup onStart={startInterview} />
      </header>
    </div>
  );
}

const InterviewSetup = ({ onStart }) => {
  const [name, setName] = useState('');
  const [experience, setExperience] = useState('beginner');
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    if (!name.trim()) {
      alert('Please enter your name');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/interview/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, experience })
      });

      if (!response.ok) {
        throw new Error('Failed to start interview');
      }

      const data = await response.json();
      onStart(data);
    } catch (error) {
      console.error('Failed to start interview:', error);
      alert('Failed to start interview. Please check if the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="interview-setup">
      <div className="form-group">
        <label>Your Name:</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter your full name"
        />
      </div>

      <div className="form-group">
        <label>Excel Experience:</label>
        <select value={experience} onChange={(e) => setExperience(e.target.value)}>
          <option value="beginner">Beginner (0-1 years)</option>
          <option value="intermediate">Intermediate (1-3 years)</option>
          <option value="advanced">Advanced (3+ years)</option>
        </select>
      </div>

      <button 
        onClick={handleStart} 
        disabled={loading || !name.trim()}
        className="start-btn"
      >
        {loading ? '🔄 Starting...' : '🚀 Start Interview'}
      </button>
    </div>
  );
};

const InterviewReport = ({ sessionId, onHome }) => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  React.useEffect(() => {
    fetchReport();
  }, [sessionId]);

  const fetchReport = async () => {
    try {
      const response = await fetch(`/api/interview/report/${sessionId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch report');
      }
      const data = await response.json();
      setReport(data);
    } catch (error) {
      console.error('Failed to fetch report:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="loading"><div className="spinner"></div><p>Generating your report...</p></div>;

  if (!report) return <div className="error">Failed to load report. Please try again.</div>;

  return (
    <div className="interview-report">
      <h2>📊 Interview Report</h2>
      <div className="report-summary">
        <h3>Summary</h3>
        <p><strong>Name:</strong> {report.user_name}</p>
        <p><strong>Final Score:</strong> {report.final_score?.toFixed(1) || 'N/A'}/5.0</p>
        <p><strong>Questions Answered:</strong> {report.total_questions}</p>
      </div>
      
      <div className="report-details">
        <h3>Detailed Report</h3>
        <div className="report-content">{report.report}</div>
      </div>

      <div className="report-questions">
        <h3>Question Breakdown</h3>
        {report.questions?.map((q, index) => (
          <div key={index} className="question-summary">
            <h4>Question {index + 1}: {q.category}</h4>
            <p><strong>Q:</strong> {q.text}</p>
            <p><strong>Your Answer:</strong> {q.user_answer || 'No answer provided'}</p>
            <p><strong>Score:</strong> {q.score}/5</p>
            <p><strong>Feedback:</strong> {q.feedback}</p>
          </div>
        ))}
      </div>

      <button onClick={onHome} className="home-btn">🏠 Back to Home</button>
    </div>
  );
};

export default App;