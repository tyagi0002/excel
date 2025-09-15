import React, { useState, useEffect } from 'react';
import AudioRecorder from './AudioRecorder';

const Interview = ({ sessionData, onComplete, onHome }) => {
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [questionNumber, setQuestionNumber] = useState(1);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (sessionData && sessionData.question) {
      setCurrentQuestion(sessionData.question);
    }
  }, [sessionData]);

  const submitAnswer = async (answerText, audioFile) => {
    if (!currentQuestion) {
      alert('No question available to answer');
      return;
    }

    setLoading(true);
    setError(null);
    
    try {
      const formData = new FormData();
      formData.append('session_id', sessionData.session_id);
      formData.append('question_id', currentQuestion.id);
      
      // Always append answer_text, even if empty
      formData.append('answer_text', answerText || '');
      
      if (audioFile) {
        console.log('Appending audio file:', {
          name: audioFile.name,
          size: audioFile.size,
          type: audioFile.type
        });
        formData.append('audio_file', audioFile);
      }

      console.log("Submitting form data:", {
        session_id: sessionData.session_id,
        question_id: currentQuestion?.id,
        answer_text: answerText || "",
        hasAudio: !!audioFile,
        audioSize: audioFile?.size || 0
      });

      const response = await fetch('/api/interview/submit', {
        method: 'POST',
        body: formData,
        // Don't set Content-Type header - let browser set it with boundary for FormData
      });

      console.log('Response status:', response.status);
      console.log('Response headers:', Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        let errorMessage = 'Failed to submit answer';
        try {
          const errorData = await response.json();
          console.error('Error response:', errorData);
          errorMessage = errorData.detail || errorData.error || errorMessage;
        } catch (parseError) {
          console.error('Could not parse error response:', parseError);
          const textError = await response.text();
          console.error('Raw error response:', textError);
          errorMessage = `Server error (${response.status}): ${textError}`;
        }
        
        setError(errorMessage);
        alert(`Error: ${errorMessage}`);
        throw new Error(errorMessage);
      }

      const result = await response.json();
      console.log('Success response:', result);
      
      if (!result.evaluation) {
        console.warn('No evaluation in response:', result);
        throw new Error('Invalid response format - missing evaluation');
      }
      
      setFeedback(result.evaluation);
      setShowFeedback(true);

      // Show feedback for 3 seconds, then proceed
      setTimeout(() => {
        if (result.interview_complete) {
          console.log('Interview completed');
          onComplete();
        } else if (result.next_question) {
          console.log('Moving to next question:', result.next_question);
          setCurrentQuestion(result.next_question);
          setQuestionNumber(prev => prev + 1);
          setFeedback(null);
          setShowFeedback(false);
        } else {
          console.warn('Unexpected response structure:', result);
          setError('Unexpected response from server');
        }
      }, 3000);

    } catch (error) {
      console.error('Failed to submit answer:', error);
      setError(error.message || 'Network error occurred');
      
      // Don't show alert if we already showed one above
      if (!error.message?.includes('Server error')) {
        alert('Failed to submit answer. Please check your connection and try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="interview-loading">
        <div className="spinner"></div>
        <p>Evaluating your answer...</p>
        <small>This may take a few moments</small>
      </div>
    );
  }

  if (error) {
    return (
      <div className="interview-error">
        <h2>❌ Error</h2>
        <p>{error}</p>
        <button onClick={() => setError(null)} className="retry-btn">
          Try Again
        </button>
        <button onClick={onHome} className="home-btn">
          🏠 Return Home
        </button>
      </div>
    );
  }

  if (showFeedback && feedback) {
    return (
      <div className="feedback-display">
        <h2>📝 Answer Evaluation</h2>
        <div className="score-display">
          <div className="score">Score: {feedback.score}/5</div>
          <div className="score-bar">
            <div 
              className="score-fill" 
              style={{ width: `${(feedback.score / 5) * 100}%` }}
            ></div>
          </div>
        </div>
        
        <div className="feedback-text">{feedback.feedback}</div>
        
        {feedback.strengths && feedback.strengths.length > 0 && (
          <div className="strengths">
            <h4>✅ Strengths:</h4>
            <ul>
              {feedback.strengths.map((strength, index) => (
                <li key={index}>{strength}</li>
              ))}
            </ul>
          </div>
        )}
        
        {feedback.improvements && feedback.improvements.length > 0 && (
          <div className="improvements">
            <h4>🎯 Areas for Improvement:</h4>
            <ul>
              {feedback.improvements.map((improvement, index) => (
                <li key={index}>{improvement}</li>
              ))}
            </ul>
          </div>
        )}
        
        <div className="feedback-footer">
          <div className="progress-dots">
            {[...Array(10)].map((_, i) => (
              <span 
                key={i} 
                className={`dot ${i < questionNumber ? 'completed' : ''}`}
              ></span>
            ))}
          </div>
          <p className="next-message">Next question coming up...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="interview-active">
      <div className="interview-header">
        <button onClick={onHome} className="home-link">🏠 Home</button>
        <div className="question-progress">
          <h2>Question {questionNumber} of 10</h2>
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${(questionNumber / 10) * 100}%` }}
            ></div>
          </div>
        </div>
      </div>

      {currentQuestion && (
        <div className="question-display">
          <div className="question-category">{currentQuestion.category}</div>
          <h3 className="question-text">{currentQuestion.text}</h3>
        </div>
      )}

      <AudioRecorder onSubmit={submitAnswer} disabled={loading} />

      <div className="interview-tips">
        <h4>💡 Tips:</h4>
        <ul>
          <li>Speak clearly and explain your thinking process</li>
          <li>Provide specific examples when possible</li>
          <li>Take your time to think before answering</li>
          <li>You can use either voice recording or text input</li>
          <li>Audio responses are automatically transcribed</li>
        </ul>
      </div>

      {/* Debug info in development */}
      {process.env.NODE_ENV === 'development' && (
        <div className="debug-info" style={{ 
          marginTop: '20px', 
          padding: '10px', 
          backgroundColor: '#f0f0f0', 
          fontSize: '12px' 
        }}>
          <strong>Debug Info:</strong><br/>
          Session ID: {sessionData?.session_id}<br/>
          Question ID: {currentQuestion?.id}<br/>
          Question Number: {questionNumber}
        </div>
      )}
    </div>
  );
};

export default Interview;