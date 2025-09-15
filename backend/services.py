import os
import tempfile
from fastapi import UploadFile
import asyncio
from typing import Optional, List, Dict, Any
import logging
import random

# Try to import optional dependencies
try:
    import assemblyai as aai
    ASSEMBLYAI_AVAILABLE = True
except ImportError:
    ASSEMBLYAI_AVAILABLE = False
    print("AssemblyAI not available - audio transcription disabled")

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Gemini not available - using fallback evaluation")

logger = logging.getLogger(__name__)

class AudioService:
    def __init__(self):
        """Initialize the audio service with AssemblyAI"""
        self.transcriber = None
        
        if not ASSEMBLYAI_AVAILABLE:
            print("AudioService: AssemblyAI not installed - audio transcription disabled")
            return
        
        try:
            # Load API key from environment
            api_key = os.getenv('ASSEMBLYAI_API_KEY')
            if not api_key:
                print("ASSEMBLYAI_API_KEY not found in environment variables")
                print("To enable audio: Set ASSEMBLYAI_API_KEY environment variable")
                return
            
            # Configure AssemblyAI
            aai.settings.api_key = api_key
            
            # Create transcriber with configuration
            config = aai.TranscriptionConfig(
                speech_model=aai.SpeechModel.universal,
                language_code="en"
            )
            self.transcriber = aai.Transcriber(config=config)
            print("AssemblyAI transcriber initialized successfully")
            
        except Exception as e:
            print(f"Failed to initialize AssemblyAI: {e}")
            self.transcriber = None
    
    async def transcribe_audio(self, audio_file: UploadFile) -> Optional[str]:
        """
        Transcribe audio file to text using AssemblyAI
        """
        if not self.transcriber:
            print("AssemblyAI transcriber not available - returning fallback message")
            return "[Audio transcription temporarily disabled - please use text input]"
        
        if not audio_file or not audio_file.filename:
            logger.error("No audio file provided")
            return None
        
        temp_file_path = None
        try:
            # Read the file content
            file_content = await audio_file.read()
            print(f"Read {len(file_content)} bytes from audio file")
            
            if len(file_content) == 0:
                print("Audio file is empty")
                return None
            
            # Create a temporary file
            file_extension = self._get_file_extension(audio_file.filename, audio_file.content_type)
            
            with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(file_content)
                temp_file.flush()
            
            print(f"Created temporary file: {temp_file_path}")
            
            # Transcribe using AssemblyAI
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._transcribe_file, temp_file_path
            )
            
            if result:
                print(f"Transcription successful: {result[:100]}...")
                return result
            else:
                print("No text in transcription result")
                return None
                
        except Exception as e:
            print(f"Audio transcription failed: {e}")
            return None
        
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    print(f"Cleaned up temporary file: {temp_file_path}")
                except Exception as cleanup_error:
                    print(f"Failed to clean up temp file: {cleanup_error}")
    
    def _transcribe_file(self, file_path: str) -> Optional[str]:
        """Transcribe audio file using AssemblyAI"""
        try:
            print(f"Starting AssemblyAI transcription of: {file_path}")
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Temporary file not found: {file_path}")
            
            # Transcribe the audio file
            transcript = self.transcriber.transcribe(file_path)
            
            # Check transcription status
            if transcript.status == aai.TranscriptStatus.error:
                raise RuntimeError(f"Transcription failed: {transcript.error}")
            elif transcript.status == aai.TranscriptStatus.completed:
                print("AssemblyAI transcription completed successfully")
                return transcript.text.strip() if transcript.text else None
            else:
                print(f"Unexpected transcription status: {transcript.status}")
                return None
                
        except Exception as e:
            print(f"AssemblyAI transcription error: {e}")
            raise e
    
    def _get_file_extension(self, filename: str, content_type: str) -> str:
        """Get appropriate file extension"""
        if filename and '.' in filename:
            return os.path.splitext(filename)[1].lower()
        
        if content_type:
            if 'webm' in content_type:
                return '.webm'
            elif 'wav' in content_type:
                return '.wav'
            elif 'mp3' in content_type:
                return '.mp3'
            elif 'mp4' in content_type:
                return '.mp4'
            elif 'm4a' in content_type:
                return '.m4a'
        
        return '.wav'
    
    def is_available(self) -> bool:
        """Check if the audio service is available"""
        return self.transcriber is not None


class LLMService:
    def __init__(self):
        """Initialize the LLM service with Gemini"""
        self.model = None
        
        if not GEMINI_AVAILABLE:
            print("Gemini not available - using fallback evaluation")
            return
        
        try:
            # Load API key from environment
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                print("GOOGLE_API_KEY not found in environment variables")
                print("Using fallback evaluation")
                return
            
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            print("Gemini client initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Gemini client: {e}")
            self.model = None
    
    async def evaluate_answer(self, question: str, answer: str, expected_answer: str, category: str) -> Dict[str, Any]:
        """
        Evaluate user's answer using Gemini
        """
        if not self.model:
            return self._fallback_evaluation(answer)
        
        try:
            prompt = f"""
You are an Excel skills interviewer. Evaluate this candidate's answer.

Question: {question}
Category: {category}
Candidate's Answer: {answer}
Expected Answer: {expected_answer}

IMPORTANT: Respond ONLY with valid JSON in exactly this format:

{{
    "score": <number from 1 to 5>,
    "feedback": "<brief 2-3 sentence evaluation>",
    "strengths": ["<strength1>", "<strength2>"],
    "improvements": ["<improvement1>", "<improvement2>"]
}}

Rules:
- Score must be 1, 2, 3, 4, or 5 only
- Feedback must be 2-3 sentences maximum
- Strengths: 0-3 items (more for higher scores)
- Improvements: 1-3 items
- Return ONLY the JSON object, no other text

Example response:
{{
    "score": 4,
    "feedback": "Good understanding of Excel functions with correct syntax. Could benefit from explaining the rationale behind the approach.",
    "strengths": ["Correct function usage", "Proper syntax"],
    "improvements": ["Explain reasoning", "Consider alternative approaches"]
}}
"""
            
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.model.generate_content(prompt)
            )
            
            result_text = response.text.strip()
            print(f"Gemini response: {result_text[:200]}...")
            
            # Parse JSON response
            try:
                import json
                
                # Extract JSON from response
                json_start = result_text.find('{')
                json_end = result_text.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_text = result_text[json_start:json_end]
                    result = json.loads(json_text)
                    
                    # Validate and clean result
                    result["score"] = max(1, min(5, int(result.get("score", 3))))
                    result["feedback"] = str(result.get("feedback", "Good effort on your answer."))
                    
                    if "strengths" not in result or not isinstance(result["strengths"], list):
                        result["strengths"] = []
                    if "improvements" not in result or not isinstance(result["improvements"], list):
                        result["improvements"] = ["Continue practicing Excel skills"]
                    
                    print(f"Successfully parsed evaluation: Score {result['score']}/5")
                    return result
                else:
                    print("No valid JSON found in response")
                    return self._fallback_evaluation(answer)
                    
            except (json.JSONDecodeError, ValueError) as parse_error:
                print(f"Failed to parse Gemini response as JSON: {parse_error}")
                print(f"Raw response: {result_text}")
                return self._fallback_evaluation(answer)
                
        except Exception as e:
            print(f"Gemini evaluation failed: {e}")
            return self._fallback_evaluation(answer)
    
    def _fallback_evaluation(self, answer: str) -> Dict[str, Any]:
        """Fallback evaluation when Gemini is not available"""
        answer_length = len(answer.split()) if answer else 0
        
        if answer_length == 0:
            score = 1
            feedback = "No answer provided."
        elif answer_length < 5:
            score = 2
            feedback = "Brief answer provided but lacks detail."
        elif answer_length < 15:
            score = 3
            feedback = "Reasonable answer with some relevant information."
        elif answer_length < 30:
            score = 4
            feedback = "Good detailed answer with relevant explanations."
        else:
            score = 5
            feedback = "Comprehensive answer with thorough explanations."
        
        return {
            "score": score,
            "feedback": feedback,
            "strengths": ["Clear communication"] if score >= 3 else [],
            "improvements": ["Provide more specific examples", "Explain reasoning in more detail"]
        }
    
    async def generate_report(self, interview, questions) -> str:
        """Generate interview report"""
        if not self.model:
            return self._fallback_report(interview, questions)
        
        try:
            question_summaries = []
            for q in questions:
                question_summaries.append(f"Q: {q.text}\nA: {q.user_answer or 'No answer'}\nScore: {q.score}/5")
            
            questions_text = "\n\n".join(question_summaries)
            
            prompt = f"""
Generate a professional interview report for an Excel skills assessment:

Candidate: {interview.user_name}
Experience Level: {interview.experience_level}
Total Questions: {interview.total_questions}
Average Score: {interview.final_score:.1f}/5

Questions and Answers:
{questions_text}

Create a comprehensive report with:
1. Overall performance summary
2. Key strengths demonstrated
3. Areas needing improvement
4. Specific recommendations for skill development
5. Next steps for the candidate

Keep the report professional, constructive, and actionable.
"""
            
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.model.generate_content(prompt)
            )
            
            return response.text.strip()
            
        except Exception as e:
            print(f"Report generation failed: {e}")
            return self._fallback_report(interview, questions)
    
    def _fallback_report(self, interview, questions) -> str:
        """Fallback report when Gemini is not available"""
        avg_score = interview.final_score
        
        if avg_score >= 4:
            performance = "Excellent"
        elif avg_score >= 3:
            performance = "Good"
        elif avg_score >= 2:
            performance = "Fair"
        else:
            performance = "Needs Improvement"
        
        return f"""
## Interview Report for {interview.user_name}

**Overall Performance:** {performance} ({avg_score:.1f}/5.0)
**Questions Completed:** {interview.total_questions}
**Experience Level:** {interview.experience_level.title()}

### Summary
The candidate completed {interview.total_questions} questions with an average score of {avg_score:.1f}/5. 
This indicates {performance.lower()} understanding of Excel concepts and skills.

### Recommendations
- Continue practicing Excel functions and formulas
- Focus on real-world applications of Excel skills
- Consider additional training in advanced Excel features

### Next Steps
- Review areas where scores were below 3/5
- Practice with hands-on Excel exercises
- Consider pursuing Excel certification
"""


class QuestionService:
    def __init__(self):
        """Initialize question service with predefined questions"""
        self.questions = {
            "basic": [
                {
                    "text": "What is the difference between a formula and a function in Excel?",
                    "category": "Basic Concepts",
                    "difficulty": 1,
                    "expected_answer": "A formula is an expression that calculates values, while a function is a predefined formula that performs specific calculations like SUM, AVERAGE, etc."
                },
                {
                    "text": "How do you freeze panes in Excel and why would you use this feature?",
                    "category": "Basic Features",
                    "difficulty": 1,
                    "expected_answer": "Go to View tab > Freeze Panes. This keeps certain rows or columns visible while scrolling, useful for keeping headers visible in large datasets."
                },
                {
                    "text": "Explain the difference between relative and absolute cell references.",
                    "category": "Basic Concepts",
                    "difficulty": 2,
                    "expected_answer": "Relative references (A1) change when copied to other cells. Absolute references ($A$1) stay fixed. Mixed references ($A1 or A$1) fix either row or column."
                },
                {
                    "text": "How do you create a simple sum formula for the range A1 to A10?",
                    "category": "Basic Formulas",
                    "difficulty": 1,
                    "expected_answer": "Use =SUM(A1:A10) to add all values in cells A1 through A10."
                }
            ],
            "intermediate": [
                {
                    "text": "How would you use VLOOKUP to find data from another table?",
                    "category": "Functions",
                    "difficulty": 2,
                    "expected_answer": "VLOOKUP(lookup_value, table_array, col_index_num, FALSE) searches for a value in the first column and returns a value from a specified column to the right."
                },
                {
                    "text": "What is the difference between VLOOKUP and INDEX/MATCH?",
                    "category": "Functions",
                    "difficulty": 3,
                    "expected_answer": "INDEX/MATCH is more flexible than VLOOKUP - it can look left, handles column insertions better, and is generally faster for large datasets."
                },
                {
                    "text": "How do you create and use named ranges in Excel?",
                    "category": "Advanced Features",
                    "difficulty": 2,
                    "expected_answer": "Select cells, go to Formulas tab > Define Name. Named ranges make formulas more readable and easier to maintain."
                }
            ],
            "advanced": [
                {
                    "text": "Explain how pivot tables work and when you would use them.",
                    "category": "Data Analysis",
                    "difficulty": 3,
                    "expected_answer": "Pivot tables summarize, analyze, and present data. They're used for data analysis, creating reports, and finding patterns in large datasets."
                },
                {
                    "text": "How would you use array formulas in Excel?",
                    "category": "Advanced Functions",
                    "difficulty": 4,
                    "expected_answer": "Array formulas perform calculations on arrays of data. Enter with Ctrl+Shift+Enter. Useful for complex calculations across multiple cells or ranges."
                },
                {
                    "text": "What are some ways to optimize Excel performance with large datasets?",
                    "category": "Performance",
                    "difficulty": 4,
                    "expected_answer": "Use efficient functions, avoid volatile functions, minimize array formulas, use tables instead of ranges, and consider Power Query for data transformation."
                }
            ]
        }
        
        self.used_questions = set()
        print(f"Question service initialized with {sum(len(q) for q in self.questions.values())} questions")
    
    def get_first_question(self, experience_level: str) -> Dict[str, Any]:
        """Get the first question based on experience level"""
        if experience_level.lower() == "beginner":
            questions = self.questions["basic"]
        elif experience_level.lower() == "intermediate":
            questions = self.questions["intermediate"]
        else:
            questions = self.questions["advanced"]
        
        question = random.choice(questions)
        self.used_questions.add(id(question))
        return question
    
    def get_next_question(self, difficulty: int, current_category: str) -> Optional[Dict[str, Any]]:
        """Get next question based on difficulty and performance"""
        if difficulty <= 2:
            question_pool = self.questions["basic"] + self.questions["intermediate"]
        elif difficulty <= 3:
            question_pool = self.questions["intermediate"] + self.questions["advanced"]
        else:
            question_pool = self.questions["advanced"]
        
        available_questions = [q for q in question_pool if id(q) not in self.used_questions]
        
        if not available_questions:
            self.used_questions.clear()
            available_questions = question_pool
        
        if available_questions:
            question = random.choice(available_questions)
            self.used_questions.add(id(question))
            return question
        
        return None
