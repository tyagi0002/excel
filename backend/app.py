from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json
import uuid
import os
from datetime import datetime
from typing import Optional
import uvicorn

from models import Interview, Question, create_tables
from services import LLMService, AudioService, QuestionService

# Initialize FastAPI app
app = FastAPI(
    title="Excel AI Mock Interviewer",
    description="AI-powered Excel skills assessment platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize services
try:
    llm_service = LLMService()
    audio_service = AudioService()
    question_service = QuestionService()
except Exception as e:
    print(f"Warning: Failed to initialize some services: {e}")
    print("Make sure you have set your OPENAI_API_KEY in .env file")

# In-memory storage (replace with database in production)
interviews = {}
questions = {}

@app.on_event("startup")
async def startup():
    create_tables()
    print("🚀 Excel AI Mock Interviewer started!")
    print("📚 API Documentation: http://localhost:8000/docs")

@app.get("/")
async def root():
    return {"message": "Excel AI Mock Interviewer API", "status": "running"}

@app.post("/api/interview/start")
async def start_interview(data: dict):
    """Start a new interview session"""
    try:
        session_id = str(uuid.uuid4())
        user_name = data.get("name", "Anonymous")
        experience = data.get("experience", "beginner")
        
        # Create interview session
        interview = Interview(
            session_id=session_id,
            user_name=user_name,
            experience_level=experience,
            status="in_progress",
            started_at=datetime.now()
        )
        interviews[session_id] = interview
        
        # Get first question
        first_question = question_service.get_first_question(experience)
        question_id = str(uuid.uuid4())
        
        question = Question(
            id=question_id,
            session_id=session_id,
            text=first_question["text"],
            category=first_question["category"],
            difficulty=first_question["difficulty"],
            expected_answer=first_question["expected_answer"]
        )
        questions[question_id] = question
        
        return {
            "session_id": session_id,
            "question": {
                "id": question_id,
                "text": first_question["text"],
                "category": first_question["category"]
            },
            "message": "Interview started successfully"
        }
        
    except Exception as e:
        print(f"Error starting interview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start interview: {str(e)}")

@app.post("/api/interview/submit")
async def submit_answer(
    session_id: str = Form(...),
    question_id: str = Form(...),
    answer_text: str = Form(default=""),  # Make it optional with default
    audio_file: Optional[UploadFile] = File(None)
):
    """Submit answer for evaluation"""
    try:
        # Debugging logs
        print(f"Received submission - Session ID: {session_id}")
        print(f"Question ID: {question_id}")
        print(f"Answer text length: {len(answer_text) if answer_text else 0}")
        print(f"Audio file received: {audio_file is not None}")
        
        if audio_file:
            print(f"Audio file details - Filename: {audio_file.filename}, Content-Type: {audio_file.content_type}")
            print(f"Audio file size: {audio_file.size if hasattr(audio_file, 'size') else 'Unknown'}")
            
        # Validate session and question
        if session_id not in interviews:
            raise HTTPException(status_code=404, detail="Interview session not found")
        
        if question_id not in questions:
            raise HTTPException(status_code=404, detail="Question not found")
        
        interview = interviews[session_id]
        question = questions[question_id]
        
        # Process audio if provided
        final_answer = answer_text or ""
        transcription_attempted = False
        
        if audio_file and audio_file.filename:
            try:
                print("Processing audio file...")
                
                # Check if audio service is available
                if hasattr(audio_service, 'transcribe_audio') and audio_service.is_available():
                    transcription_attempted = True
                    
                    # Transcribe audio
                    transcribed_text = await audio_service.transcribe_audio(audio_file)
                    print(f"Transcription result: {transcribed_text}")
                    
                    if transcribed_text and transcribed_text.strip():
                        final_answer = transcribed_text.strip()
                        print(f"Using transcribed answer: {final_answer}")
                    else:
                        print("No transcription result")
                        if not final_answer:
                            final_answer = "[Audio uploaded but transcription failed - please provide text answer]"
                        
                else:
                    print("Audio transcription service not available")
                    if not final_answer:
                        final_answer = "[Audio uploaded but transcription service unavailable - please provide text answer]"
                    
            except Exception as audio_error:
                print(f"Audio transcription failed: {audio_error}")
                print(f"Audio error type: {type(audio_error)}")
                # If transcription was attempted but failed, and no text provided, give helpful message
                if transcription_attempted and not final_answer:
                    final_answer = "[Audio transcription failed - please try again or provide text answer]"
        
        # Validate that we have some form of answer
        if not final_answer or not final_answer.strip():
            raise HTTPException(
                status_code=400, 
                detail="No answer provided. Please provide either text or clear audio recording."
            )
        
        print(f"Final answer to evaluate: {final_answer}")
        
        # Evaluate answer
        try:
            evaluation = await llm_service.evaluate_answer(
                question.text,
                final_answer,
                question.expected_answer,
                question.category
            )
            print(f"Evaluation result: {evaluation}")
        except Exception as eval_error:
            print(f"Evaluation failed: {eval_error}")
            # Provide fallback evaluation
            evaluation = {
                "score": 3,
                "feedback": "Your answer has been received. Due to a processing issue, detailed evaluation is temporarily unavailable.",
                "strengths": ["Answer provided"],
                "improvements": ["Please try again if you experience issues"]
            }
        
        # Update question with answer and score
        question.user_answer = final_answer
        question.score = evaluation.get("score", 0)
        question.feedback = evaluation.get("feedback", "")
        
        # Update interview progress
        interview.total_questions += 1
        interview.total_score += evaluation.get("score", 0)
        
        # Determine next step
        if interview.total_questions >= 10:  # End after 10 questions
            interview.status = "completed"
            interview.completed_at = datetime.now()
            interview.final_score = interview.total_score / interview.total_questions if interview.total_questions > 0 else 0
            
            return {
                "evaluation": evaluation,
                "interview_complete": True,
                "final_score": interview.final_score,
                "total_questions": interview.total_questions,
                "message": "Interview completed successfully"
            }
        
        # Get next question
        current_difficulty = question.difficulty
        next_difficulty = current_difficulty + 1 if evaluation.get("score", 0) >= 3 else current_difficulty
        
        try:
            next_question_data = question_service.get_next_question(next_difficulty, question.category)
        except Exception as q_error:
            print(f"Error getting next question: {q_error}")
            next_question_data = None
        
        if next_question_data:
            next_question_id = str(uuid.uuid4())
            next_question = Question(
                id=next_question_id,
                session_id=session_id,
                text=next_question_data["text"],
                category=next_question_data["category"],
                difficulty=next_question_data["difficulty"],
                expected_answer=next_question_data["expected_answer"]
            )
            questions[next_question_id] = next_question
            
            return {
                "evaluation": evaluation,
                "next_question": {
                    "id": next_question_id,
                    "text": next_question_data["text"],
                    "category": next_question_data["category"]
                },
                "interview_complete": False,
                "message": "Answer submitted successfully"
            }
        
        # End interview if no more questions
        interview.status = "completed"
        interview.completed_at = datetime.now()
        interview.final_score = interview.total_score / interview.total_questions if interview.total_questions > 0 else 0
        
        return {
            "evaluation": evaluation,
            "interview_complete": True,
            "final_score": interview.final_score,
            "message": "Interview completed - no more questions available"
        }
        
    except HTTPException as http_error:
        print(f"HTTPException: {http_error.detail}")
        raise http_error
    except Exception as e:
        print(f"Unexpected error in submit_answer: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to process answer: {str(e)}")

@app.get("/api/interview/report/{session_id}")
async def get_report(session_id: str):
    """Get interview report"""
    try:
        if session_id not in interviews:
            raise HTTPException(status_code=404, detail="Interview session not found")
        
        interview = interviews[session_id]
        session_questions = [q for q in questions.values() if q.session_id == session_id]
        
        if not session_questions:
            raise HTTPException(status_code=404, detail="No questions found for this session")
        
        # Generate detailed report
        try:
            report = await llm_service.generate_report(interview, session_questions)
        except Exception as report_error:
            print(f"Report generation failed: {report_error}")
            report = "Report generation temporarily unavailable. Please try again later."
        
        return {
            "session_id": session_id,
            "user_name": interview.user_name,
            "final_score": interview.final_score,
            "total_questions": interview.total_questions,
            "report": report,
            "questions": [
                {
                    "text": q.text,
                    "user_answer": q.user_answer or "No answer provided",
                    "score": q.score,
                    "feedback": q.feedback,
                    "category": q.category
                }
                for q in session_questions
            ],
            "status": interview.status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "llm": hasattr(llm_service, 'client'),
            "audio": hasattr(audio_service, 'whisper_model') if hasattr(audio_service, 'whisper_model') else False,
            "questions": len(question_service.questions) > 0 if hasattr(question_service, 'questions') else False
        },
        "active_sessions": len(interviews)
    }

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)