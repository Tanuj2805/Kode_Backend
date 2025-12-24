from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")

# User Models
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class OTPLoginRequest(BaseModel):
    email: EmailStr

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str = Field(..., min_length=6)

class UserResponse(BaseModel):
    id: str = Field(alias="_id")
    username: str
    email: str
    token: Optional[str] = None

    class Config:
        populate_by_name = True

# Code Models
class CodeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=20)  # Limited to 20 chars
    language: str = Field(..., pattern="^(python|javascript|java|cpp|go|c|rust|php|ruby|bash)$")
    code: str = Field(..., max_length=50000)
    description: Optional[str] = Field(default="", max_length=500)
    input: Optional[str] = ""
    folderPath: Optional[str] = Field(default="", max_length=200)

class CodeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    language: Optional[str] = Field(None, pattern="^(python|javascript|java|cpp|go|c|rust|php|ruby|bash)$")
    code: Optional[str] = Field(None, max_length=50000)
    description: Optional[str] = Field(None, max_length=500)
    input: Optional[str] = None
    lastOutput: Optional[str] = None
    folderPath: Optional[str] = Field(None, max_length=200)

class CodeResponse(BaseModel):
    id: str = Field(alias="_id")
    user: str
    title: str
    language: str
    code: str
    description: str
    input: str
    lastOutput: str
    folderPath: Optional[str] = ""
    lastRunAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        populate_by_name = True

# Folder Models
class FolderCreate(BaseModel):
    path: str = Field(..., min_length=1, max_length=200)

class FolderResponse(BaseModel):
    id: str = Field(alias="_id")
    user: str
    path: str
    createdAt: datetime

    class Config:
        populate_by_name = True

# Execute Models
class ExecuteRequest(BaseModel):
    language: str = Field(..., pattern="^(python|javascript|java|cpp|go|c|rust|php|ruby|bash)$")
    code: str = Field(..., max_length=50000)
    input: Optional[str] = ""

class ExecuteResponse(BaseModel):
    success: bool
    output: str
    error: Optional[str] = None

# Solution Models
class SolutionCreate(BaseModel):
    problem_id: int
    language: str
    title: str = Field(..., min_length=1, max_length=200)
    explanation: str = Field(..., min_length=10)
    code: str = Field(..., max_length=50000)
    time_complexity: Optional[str] = Field(default="", max_length=100)
    space_complexity: Optional[str] = Field(default="", max_length=100)

class SolutionResponse(BaseModel):
    id: str = Field(alias="_id")
    problem_id: int
    user_id: str
    username: str
    language: str
    title: str
    explanation: str
    code: str
    time_complexity: str
    space_complexity: str
    upvotes: int
    downvotes: int
    created_at: datetime
    is_verified: bool = False

    class Config:
        populate_by_name = True

class SolutionVote(BaseModel):
    solution_id: str
    vote_type: str = Field(..., pattern="^(upvote|downvote)$")

# Interview Experience Models
class InterviewExperienceCreate(BaseModel):
    company: str = Field(..., min_length=1, max_length=100)
    job_role: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=100)
    years_of_experience: int = Field(..., ge=0, le=50)
    salary: Optional[str] = Field(default=None, max_length=100)  # Optional salary field (e.g., "$120,000 - $150,000")
    linkedin_profile: Optional[str] = Field(default=None, max_length=500)
    interview_date: str  # Format: "Month Year" e.g., "October 2024"
    difficulty: str = Field(..., pattern="^(Easy|Medium|Hard)$")
    rounds: list[str] = Field(..., min_items=1)
    questions_asked: str = Field(..., min_length=50)
    overall_experience: str = Field(..., min_length=100)
    tips: Optional[str] = Field(default="", max_length=5000)
    offer_received: bool = False
    is_anonymous: bool = False

class InterviewExperienceResponse(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    username: str
    company: str
    job_role: str
    location: str
    years_of_experience: int
    salary: Optional[str] = None  # Optional salary field
    linkedin_profile: Optional[str] = None
    interview_date: str
    difficulty: str
    rounds: list[str]
    questions_asked: str
    overall_experience: str
    tips: str
    offer_received: bool
    is_anonymous: bool = False
    helpful_count: int
    created_at: datetime

    class Config:
        populate_by_name = True

class InterviewExperienceHelpful(BaseModel):
    experience_id: str

# Problem with Company Tags Model
class ProblemWithCompany(BaseModel):
    id: int
    title: str
    difficulty: str
    category: str
    companies: list[str] = []
    description: str

# Submission Models (for existing problems.py route)
class SubmissionCreate(BaseModel):
    problem_id: int
    language: str
    code: str = Field(..., max_length=50000)

class TestCaseResult(BaseModel):
    test_number: int
    passed: bool
    input: str
    expected: str
    actual: Optional[str] = None
    error: Optional[str] = None
    runtime_ms: int

class SubmissionResponse(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    username: str
    problem_id: int
    language: str
    code: str
    status: str
    passed_tests: int
    total_tests: int
    runtime_ms: int
    memory_kb: int
    points: int
    submitted_at: datetime
    test_results: list[dict] = []  # Changed to list[dict] for better compatibility

    class Config:
        populate_by_name = True

class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    problems_solved: int
    total_submissions: int
    acceptance_rate: float
    points: int
    last_submission: Optional[datetime] = None

# ============================================
# DYNAMIC PROBLEM MANAGEMENT MODELS
# ============================================

class ProblemExample(BaseModel):
    input: str
    output: str
    explanation: Optional[str] = ""

class TestCase(BaseModel):
    input: str
    expected: str
    hidden: bool = False  # Hidden test cases not shown to users

class StarterCode(BaseModel):
    python: str = ""
    javascript: str = ""
    java: str = ""
    cpp: str = ""
    go: str = ""

class SampleTestCase(BaseModel):
    input: str
    expected: str

class ProblemCreate(BaseModel):
    problem_id: int
    title: str = Field(..., min_length=1, max_length=200)
    difficulty: str = Field(..., pattern="^(Easy|Medium|Hard)$")
    category: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=10)
    examples: list[ProblemExample] = []
    constraints: list[str] = []
    input_format: str = ""
    output_format: str = ""
    sample_test_case: Optional[SampleTestCase] = None
    starter_code: Optional[StarterCode] = None
    hints: list[str] = []
    test_cases: list[TestCase] = []
    time_limit: int = Field(default=5000, ge=1000, le=30000)  # 1-30 seconds
    memory_limit: int = Field(default=128000, ge=64000, le=512000)  # 64MB-512MB
    points: int = Field(default=100, ge=10, le=1000)
    tags: list[str] = []
    companies: list[str] = []
    status: str = Field(default="active", pattern="^(active|draft|archived)$")

class ProblemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    difficulty: Optional[str] = Field(None, pattern="^(Easy|Medium|Hard)$")
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, min_length=10)
    examples: Optional[list[ProblemExample]] = None
    constraints: Optional[list[str]] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    sample_test_case: Optional[SampleTestCase] = None
    starter_code: Optional[StarterCode] = None
    hints: Optional[list[str]] = None
    test_cases: Optional[list[TestCase]] = None
    time_limit: Optional[int] = Field(None, ge=1000, le=30000)
    memory_limit: Optional[int] = Field(None, ge=64000, le=512000)
    points: Optional[int] = Field(None, ge=10, le=1000)
    tags: Optional[list[str]] = None
    companies: Optional[list[str]] = None
    status: Optional[str] = Field(None, pattern="^(active|draft|archived)$")

class ProblemResponse(BaseModel):
    id: str = Field(alias="_id")
    problem_id: int
    title: str
    difficulty: str
    category: str
    description: str
    examples: list[ProblemExample]
    constraints: list[str]
    input_format: str
    output_format: str
    sample_test_case: Optional[SampleTestCase]
    starter_code: Optional[StarterCode]
    hints: list[str]
    time_limit: int
    memory_limit: int
    points: int
    total_submissions: int
    accepted_submissions: int
    tags: list[str]
    companies: list[str]
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True

class ProblemListItem(BaseModel):
    id: str = Field(alias="_id")
    problem_id: int
    title: str
    difficulty: str
    category: str
    description: str
    points: int
    total_submissions: int
    accepted_submissions: int
    tags: list[str]

    class Config:
        populate_by_name = True

# Weekly Challenge Models
class WeeklyChallengeQuestion(BaseModel):
    question_number: int
    title: str
    description: str
    difficulty: str  # Easy, Medium, Hard
    examples: list[ProblemExample]
    constraints: Optional[str] = ""
    input_format: Optional[str] = ""
    output_format: Optional[str] = ""
    starter_code: Optional[StarterCode]
    hints: list[str] = []
    test_cases: list[TestCase]
    time_limit: int = 5000  # ms
    memory_limit: int = 128000  # KB
    points: int = 10

class WeeklyChallengeCreate(BaseModel):
    week_number: int
    year: int
    title: str
    description: str
    start_date: datetime
    end_date: datetime
    questions: list[WeeklyChallengeQuestion]
    status: str = "upcoming"  # upcoming, active, completed
    contest_type: str = "weekly"  # Added for contest type separation

class WeeklyChallengeResponse(BaseModel):
    id: str = Field(alias="_id")
    week_number: int
    year: int
    title: str
    description: str
    start_date: datetime
    end_date: datetime
    questions: list[WeeklyChallengeQuestion]
    status: str
    contest_type: str = "weekly"  # Added for contest type separation
    total_participants: int = 0
    created_at: datetime

    class Config:
        populate_by_name = True

class WeeklyChallengeSubmissionRequest(BaseModel):
    """Request model for submitting a weekly challenge solution"""
    code: str = Field(..., max_length=50000)
    language: str

class WeeklyChallengeSubmission(BaseModel):
    user_id: str
    username: str
    challenge_id: str
    week_number: int
    year: int
    question_number: int
    code: str
    language: str
    status: str  # Accepted, Wrong Answer, etc.
    passed_tests: int
    total_tests: int
    points_earned: int
    submitted_at: datetime

class WeeklyChallengeProgress(BaseModel):
    user_id: str
    username: str
    challenge_id: str
    week_number: int
    year: int
    questions_solved: list[int]  # List of question numbers solved
    total_points: int
    rank: Optional[int] = None
    completed_at: Optional[datetime] = None

class WeeklyStreak(BaseModel):
    user_id: str
    username: str
    current_streak: int = 0
    longest_streak: int = 0
    weeks_participated: list[str] = []  # Format: "2025-W44"
    contests_participated: list[str] = []  # Contest IDs for streak tracking
    total_challenges_completed: int = 0
    last_participation: Optional[datetime] = None
    last_challenge_id: Optional[str] = None  # Added for contest-based streak logic
