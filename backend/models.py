from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import sqlite3
import os

@dataclass
class Interview:
    session_id: str
    user_name: str
    experience_level: str
    status: str = "in_progress"
    total_questions: int = 0
    total_score: float = 0.0
    final_score: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

@dataclass
class Question:
    id: str
    session_id: str
    text: str
    category: str
    difficulty: int
    expected_answer: str
    user_answer: Optional[str] = None
    score: float = 0.0
    feedback: str = ""

def create_tables():
    """Create database tables (SQLite for simplicity)"""
    conn = sqlite3.connect('interviews.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interviews (
            session_id TEXT PRIMARY KEY,
            user_name TEXT,
            experience_level TEXT,
            status TEXT,
            total_questions INTEGER DEFAULT 0,
            total_score REAL DEFAULT 0.0,
            final_score REAL DEFAULT 0.0,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            text TEXT,
            category TEXT,
            difficulty INTEGER,
            expected_answer TEXT,
            user_answer TEXT,
            score REAL DEFAULT 0.0,
            feedback TEXT,
            FOREIGN KEY (session_id) REFERENCES interviews (session_id)
        )
    ''')
    
    conn.commit()
    conn.close()