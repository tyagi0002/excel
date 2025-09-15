import React, { useState, useRef } from 'react';

const AudioRecorder = ({ onSubmit, disabled }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const [answerText, setAnswerText] = useState('');
  const [recordingTime, setRecordingTime] = useState(0);
  
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100,
        }
      });
      
      // Use a more compatible audio format
      const options = {
        mimeType: 'audio/webm;codecs=opus'
      };
      
      // Fallback for browsers that don't support webm
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options.mimeType = 'audio/wav';
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
          options.mimeType = ''; // Use browser default
        }
      }
      
      const mediaRecorder = new MediaRecorder(stream, options);
      
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = () => {
        console.log('Recording stopped, chunks:', chunksRef.current.length);
        
        if (chunksRef.current.length > 0) {
          // Determine the correct MIME type for the blob
          let mimeType = mediaRecorder.mimeType || 'audio/wav';
          console.log('Creating blob with MIME type:', mimeType);
          
          const audioBlob = new Blob(chunksRef.current, { type: mimeType });
          console.log('Audio blob created:', audioBlob.size, 'bytes');
          setAudioBlob(audioBlob);
        } else {
          console.warn('No audio data recorded');
          alert('No audio data was recorded. Please try again.');
        }
        
        stream.getTracks().forEach(track => track.stop());
      };
      
      mediaRecorder.onerror = (event) => {
        console.error('MediaRecorder error:', event.error);
        alert('Recording error occurred. Please try again.');
        setIsRecording(false);
      };
      
      mediaRecorder.start(1000); // Collect data every second
      setIsRecording(true);
      
      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
      
    } catch (error) {
      console.error('Failed to start recording:', error);
      let errorMessage = 'Failed to access microphone. ';
      
      if (error.name === 'NotAllowedError') {
        errorMessage += 'Please allow microphone access and try again.';
      } else if (error.name === 'NotFoundError') {
        errorMessage += 'No microphone found. Please check your device.';
      } else {
        errorMessage += 'Please check permissions and try again.';
      }
      
      alert(errorMessage);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      
      if (timerRef.current) {
        clearInterval(timerRef.current);
        setRecordingTime(0);
      }
    }
  };

  const handleSubmit = async () => {
    // Validate input
    const hasText = answerText && answerText.trim().length > 0;
    const hasAudio = audioBlob && audioBlob.size > 0;
    
    if (!hasText && !hasAudio) {
      alert('Please provide an answer by typing text or recording audio.');
      return;
    }
    
    let audioFile = null;
    if (hasAudio) {
      try {
        // Create a proper File object with correct MIME type
        const mimeType = audioBlob.type || 'audio/wav';
        const extension = mimeType.includes('webm') ? 'webm' : 'wav';
        
        audioFile = new File([audioBlob], `answer.${extension}`, { 
          type: mimeType,
          lastModified: new Date().getTime()
        });
        
        console.log('Audio file created:', {
          name: audioFile.name,
          size: audioFile.size,
          type: audioFile.type
        });
        
      } catch (error) {
        console.error('Error creating audio file:', error);
        alert('Error processing audio. Please try recording again.');
        return;
      }
    }

    try {
      // Call the parent's onSubmit function
      await onSubmit(answerText.trim() || "", audioFile);
      
      // Clear form after successful submission
      setAnswerText('');
      setAudioBlob(null);
      
    } catch (error) {
      console.error('Submit error in AudioRecorder:', error);
      // Don't clear form on error so user can retry
    }
  };

  const clearRecording = () => {
    setAudioBlob(null);
    console.log('Recording cleared');
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="audio-recorder">
      <div className="recording-section">
        <h3>🎤 Record Your Answer</h3>
        
        <div className="recording-controls">
          {!isRecording && !audioBlob && (
            <button 
              onClick={startRecording} 
              className="record-btn start"
              disabled={disabled}
            >
              🎤 Start Recording
            </button>
          )}
          
          {isRecording && (
            <div className="recording-active">
              <button onClick={stopRecording} className="record-btn stop">
                ⏹️ Stop Recording
              </button>
              <div className="recording-timer">🔴 {formatTime(recordingTime)}</div>
              <div className="recording-indicator">Recording in progress...</div>
            </div>
          )}
          
          {audioBlob && (
            <div className="recording-complete">
              <div className="audio-info">
                ✅ Recording completed ({Math.round(audioBlob.size / 1024)}KB)
              </div>
              <audio 
                controls 
                src={URL.createObjectURL(audioBlob)}
                style={{ width: '100%', marginTop: '10px' }}
              />
              <button onClick={clearRecording} className="clear-btn">
                🗑️ Delete Recording
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="text-section">
        <h3>✏️ Or Type Your Answer</h3>
        <textarea
          value={answerText}
          onChange={(e) => setAnswerText(e.target.value)}
          placeholder="Type your answer here... (or record audio above)"
          rows="4"
          disabled={disabled}
          style={{ width: '100%', resize: 'vertical' }}
        />
        <div className="char-count">
          {answerText.length} characters
        </div>
      </div>

      <div className="submit-section">
        <button 
          onClick={handleSubmit}
          disabled={disabled || (!answerText.trim() && !audioBlob)}
          className="submit-btn"
        >
          {disabled ? 'Submitting...' : '📤 Submit Answer'}
        </button>
        
        {answerText.trim() && audioBlob && (
          <p className="submission-note">
            ℹ️ Both text and audio provided. Audio will be prioritized for transcription.
          </p>
        )}
      </div>
    </div>
  );
};

export default AudioRecorder;