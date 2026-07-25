"""Resume scoring system using structured LLM evaluation.

Takes a PDF resume, extracts text, and runs it through two-phase evaluation:
1. System prompt: Technical recruiter evaluation
2. Criteria prompt: Software Intern position scoring

Returns a structured JSON score with breakdown and final aggregate.
"""
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.pipeline.llm import parse_scoring
from config.settings import require_api_key


# --- Pydantic schema for the LLM response -------------------------------------
class CategoryScore(BaseModel):
    """Individual category score with evidence."""
    score: int
    max: int
    evidence: str


class BonusPoints(BaseModel):
    """Bonus points breakdown."""
    total: int
    breakdown: str


class Deductions(BaseModel):
    """Deductions breakdown."""
    total: int
    reasons: str


class Scores(BaseModel):
    """All four category scores."""
    self_projects: CategoryScore
    production: CategoryScore
    technical_skills: CategoryScore
    resume_visual_aesthetics: CategoryScore

class ResumeScore(BaseModel):
    """Complete resume evaluation schema."""
    scores: Scores
    bonus_points: BonusPoints
    deductions: Deductions
    key_strengths: list[str]
    areas_for_improvement: list[str]


# --- Prompts (frozen as constants) --------------------------------------------
SYSTEM_PROMPT = """You are an expert technical recruiter evaluating resumes. Provide accurate, objective evaluations based on the given criteria.

**CRITICAL: You are NOT writing a resume summary. You are SCORING a resume for a job application.**

**CRITICAL FAIRNESS REQUIREMENTS:**
**SCORES MUST NEVER DEPEND ON THE FOLLOWING FACTORS:**
- Candidate's name, gender, or any personal demographic information
- College, university, or educational institution name
- CGPA, GPA, or academic grades
- City, location, or geographical information
- Any personal characteristics unrelated to technical skills and experience

**EVALUATION MUST BE BASED ONLY ON:**
- Technical skills and programming languages
- Project complexity and real-world impact
- Work experience and production-level contributions
- Technical communication and documentation abilities
- Problem-solving and algorithmic thinking demonstrated in projects

**MANDATORY: You MUST always fill ALL FOUR categories: self_projects, production, technical_skills, resume_visual_aesthetics.**

- For self_projects: Analyze the 'projects' section and any personal, hackathon, or side projects. **CRITICAL PROJECT EVALUATION**: Assess project complexity and impact, not just quantity. Simple tutorial projects (todo lists, calculators, basic CRUD apps, weather apps, note-taking apps) should receive LOW SCORES (1-9 points) or trigger deductions. **MANDATORY: For self projects that are basic CRUD applications, give NO POINTS (0 points).** Complex projects with real-world impact, advanced architecture, or contributions to popular open source projects should receive HIGH SCORES (20-30 points). Apply 2-5 point deductions for resumes with only simple tutorial projects. **PROJECT LINK REQUIREMENTS**: Projects without active links, GitHub repositories, or live demos should receive significantly lower scores. Apply 3-5 point deductions for each project without any GitHub link, live demo, or active URL. Projects with only GitHub links (no live demo) should receive 2-3 point deductions. Projects with broken or inactive links should receive 1-2 point deductions. Projects without links are difficult to verify and demonstrate lack of transparency and professionalism.

- For production: Analyze the 'work' and 'volunteer' sections for any real-world, internship, or production experience. If there is any work, internship, or volunteer experience, you MUST score this category and provide evidence. **SPECIAL CONSIDERATION FOR STARTUP EXPERIENCE**: Give extra points for founder roles, co-founder positions, or early-stage engineer roles (first 10-20 employees) at startups, as these demonstrate exceptional initiative, technical leadership, and ability to build products from scratch.

- For technical_skills: Analyze the 'skills', 'languages', and any evidence of technical breadth or problem-solving in projects, work, or competitions. You MUST score this category and provide evidence.

- For resume_visual_aesthetics: Assess formatting quality, structure, and
  scannability from the parsed resume data. This category rewards a clean,
  consistent, single-page-appropriate layout and penalizes clutter,
  inconsistency, and structural noise. Score 0-10 using the rubric below.
  You are grading STRUCTURAL HYGIENE as a proxy for visual quality - you do
  not have the rendered image, so infer from the data you have.

  SCORING BANDS:
    9-10 - Clean and consistent. Standard sections present and logically
           ordered (Experience → Projects → Skills/Education as appropriate).
           Bullets are uniformly formatted, concise, and roughly even in
           length. No wall-of-text bullets. Dates present and consistently
           formatted. Content volume fits one page (see length heuristic).
    6-8  - Mostly clean with minor issues: one or two overlong bullets,
           slightly inconsistent date formatting, or a section ordering that
           is serviceable but not ideal.
    3-5  - Noticeable problems: several overlong or ragged bullets, missing
           or inconsistent dates, cluttered skills dump (30+ comma-listed
           tools), or content volume that clearly overflows one page.
    0-2  - Poor structure: no clear section headers, bullets missing entirely
           (paragraph blobs), severe length overflow, or chaotic ordering
           that would fail an ATS parse.

CRITICAL: You MUST respond with the EXACT JSON structure specified in the prompt. Do not change category names, add extra fields, or modify the structure. The response must include ALL required fields: scores (with self_projects, production, technical_skills, resume_visual_aesthetics), bonus_points, deductions, key_strengths, areas_for_improvement.

**IMPORTANT LIST CONSTRAINTS:**
- key_strengths: Provide 1-5 items (maximum 5 key strengths)
- areas_for_improvement: Provide 1-3 items (maximum 3 areas for improvement)

**IMPORTANT SCORE CONSTRAINTS:**
- Evidence fields cannot be empty string
- All category scores must be >= 0 (cannot be negative)
- **CATEGORY SCORE LIMITS** (CANNOT be exceeded under any circumstances):
  - self_projects: 0-35 points (maximum 35)
  - production: 0-40 points (maximum 40)
  - technical_skills: 0-15 points (maximum 15)
  - resume_visual_aesthetics: 0-10 points (maximum 10)
- Bonus points total must be <= 20 (maximum 20 points)
- **CRITICAL**: The total bonus points cannot exceed 20 points under any circumstances
- **OVERALL SCORE LIMIT**: The total score (categories + bonus - deductions) cannot exceed 120 points

IMPORTANT: Always check the structured 'profiles' section in the resume data before applying deductions for missing portfolio links. Only apply deductions if profiles are genuinely missing from the structured data. When blog data is provided in the resume text (look for '=== BLOG DATA ===' section), analyze the technical blog posts, writing quality, topics covered, and frequency of posting to assess the candidate's technical communication skills and knowledge sharing abilities. High-quality technical blogs with regular posting and diverse technical topics should receive bonus points. **CRITICAL PROJECT ASSESSMENT**: When evaluating projects, prioritize complexity and real-world impact over quantity. Simple tutorial projects should receive low scores and may trigger deductions. A single complex project is worth more than multiple simple ones. **CRITICAL FAIRNESS**: Ignore all personal demographic information, educational institution names, academic grades, and geographical location when scoring. Focus solely on technical skills, project quality, and professional experience. CRITICAL: You MUST respond with valid JSON that includes ALL required fields (scores, bonus_points, deductions, key_strengths, areas_for_improvement). The response must be valid JSON that matches the exact structure specified. Do not omit any fields or add extra fields."""


CRITERIA_PROMPT_TEMPLATE = """You are evaluating a resume for a Software Intern position at HackerRank. Analyze the resume data and provide scores based on these criteria:

**MANDATORY: You MUST always fill ALL FOUR categories: self_projects, production, technical_skills, resume_visual_aesthetics.**

## CRITICAL FAIRNESS REQUIREMENTS
**SCORES MUST NEVER DEPEND ON:**
- Candidate's name, gender, or personal demographic information
- College, university, or educational institution name
- CGPA, GPA, or academic grades
- City, location, or geographical information
- Any personal characteristics unrelated to technical skills and experience

**EVALUATION MUST BE BASED ONLY ON:**
- Technical skills and programming languages
- Project complexity and real-world impact
- Open source contributions and community involvement
- Work experience and production-level contributions
- Technical communication and documentation abilities
- Problem-solving and algorithmic thinking demonstrated in projects

## ANALYSIS INSTRUCTIONS
- Analyze the structured resume data (basics, work, volunteer, projects, skills, etc.)
- Use blog data (if provided in === BLOG DATA === section) for technical communication assessment

## SCORING CRITERIA

### Self Projects (0-35 points)
**HIGH SCORES (30-35 points):**
- Complex projects with real-world impact
- Advanced architecture, multiple technologies
- User adoption or production-level deployment
- Projects demonstrating deep technical expertise

**MEDIUM SCORES (15-29 points):**
- Projects with some complexity, good documentation
- Multiple features or moderate technical challenge
- Well-structured codebases

**LOW SCORES (1-14 points):**
- Simple tutorial projects (todo lists, calculators, basic CRUD apps, weather apps, note-taking apps, recipe apps, exercise apps)
- Basic sentiment analysis using standard libraries (NLTK, scikit-learn)
- Classroom assignments or projects with minimal technical complexity

**ZERO SCORES (0 points):**
- No projects or only extremely basic projects that demonstrate no technical skills

**PROJECT LINK REQUIREMENTS:**
- **NO LINKS**: Projects without URLs or live demos should receive 30-50% lower scores
- **INACTIVE LINKS**: Projects with broken links should receive 20-30% lower scores
- **LIVE DEMO BONUS**: Projects with working live demos should receive 10-20% higher scores

### Production (0-40 points)
- Analyze the 'work' and 'volunteer' sections for real-world, internship, or production experience
- **SPECIAL CONSIDERATION**: Give extra points for founder roles, co-founder positions, or early-stage engineer roles (first 10-20 employees) at startups

### Technical Skills (0-15 points)
- Analyze the 'skills', 'languages', and evidence of technical breadth or problem-solving in projects, work, or competitions

### Resume Visual Aesthetics (0-10 points)
- Assess formatting quality, structure, and scannability from the parsed resume data

## PROJECT COMPLEXITY ASSESSMENT

**Simple/Basic Projects (Low Impact):**
- Todo list applications, calculators, basic CRUD applications
- Weather apps using public APIs, note-taking applications
- Simple portfolio websites, basic form applications
- "Hello World" applications, classroom assignment projects
- Tutorial-based projects, recipe sharing applications
- Exercise/health apps using public APIs
- Basic sentiment analysis using standard libraries
- Simple e-commerce applications, basic social media clones

**Complex/Advanced Projects (High Impact):**
- Full-stack applications with multiple features
- Projects with user authentication and databases
- Machine learning or AI applications
- Real-time applications (chat, streaming, etc.)
- Mobile applications with native features
- Projects with microservices architecture
- Contributions to popular open source projects
- Projects with significant user adoption
- Projects solving real-world problems
- Projects demonstrating advanced algorithms or data structures

## BONUS POINTS (Maximum total: 20 points)
- +5-8 points for startup founder/co-founder experience
- +3-5 points for early-stage engineer experience (first 10-20 employees at a startup)
- +3-5 points for portfolio website with live demos
- +2-3 points for LinkedIn profile with strong presence
- +2-4 points for high-quality technical blogs (if blog data provided)
- +1-3 points for relevant certifications (AWS, GCP, etc.)

**CRITICAL**: The total bonus points cannot exceed 20 points under any circumstances.

## DEDUCTIONS
**For Simple Projects:**
- -2 to -5 points if resume contains only simple tutorial projects
- -1 to -3 points for each simple project beyond the first one
- -1 point for projects with generic names like "Calculator", "Todo App", "Weather App"
- -2 points if all projects are classroom assignments or tutorial-based

**For Projects Without Links:**
- -3 to -5 points for each project without any GitHub link, live demo, or active URL
- -2 to -3 points for each project with only GitHub link but no live demo
- -1 to -2 points for each project with broken or inactive links

**CRITICAL ENFORCEMENT:**
- For candidates with only simple tutorial-based projects, self_projects score should NEVER exceed 14 points

## CRITICAL REQUIREMENTS
1. You MUST respond with ONLY the JSON structure below - no summary, no other fields
2. You MUST fill ALL FOUR score categories: self_projects, production, technical_skills, resume_visual_aesthetics
3. You MUST provide evidence for each score
4. You MUST NOT add any other fields like "summary", "skills", "experience", etc.
5. You MUST NOT change the field names or structure

**IMPORTANT LIST CONSTRAINTS:**
- key_strengths: Provide 1-5 items (maximum 5 key strengths)
- areas_for_improvement: Provide 1-3 items (maximum 3 areas for improvement)

**IMPORTANT SCORE CONSTRAINTS:**
- Evidence fields cannot be empty string
- All category scores must be >= 0 (cannot be negative)
- **CATEGORY SCORE LIMITS** (CANNOT be exceeded under any circumstances):
  - self_projects: 0-35 points (maximum 35)
  - production: 0-40 points (maximum 40)
  - technical_skills: 0-15 points (maximum 15)
  - resume_visual_aesthetics: 0-10 points (maximum 10)

## RESUME DATA

{text_content}
"""

@dataclass
class ScoringResult:
    """Final scoring result with aggregate calculation."""
    raw_score: ResumeScore
    category_total: int
    final_score: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        scores_obj = self.raw_score.scores
        return {
            "category_scores": {
                "self_projects": {
                    "score": scores_obj.self_projects.score,
                    "max": scores_obj.self_projects.max,
                    "evidence": scores_obj.self_projects.evidence,
                },
                "production": {
                    "score": scores_obj.production.score,
                    "max": scores_obj.production.max,
                    "evidence": scores_obj.production.evidence,
                },
                "technical_skills": {
                    "score": scores_obj.technical_skills.score,
                    "max": scores_obj.technical_skills.max,
                    "evidence": scores_obj.technical_skills.evidence,
                },
                "resume_visual_aesthetics": {
                    "score": scores_obj.resume_visual_aesthetics.score,
                    "max": scores_obj.resume_visual_aesthetics.max,
                    "evidence": scores_obj.resume_visual_aesthetics.evidence,
                },
            },
            "bonus_points": {
                "total": self.raw_score.bonus_points.total,
                "breakdown": self.raw_score.bonus_points.breakdown,
            },
            "deductions": {
                "total": self.raw_score.deductions.total,
                "reasons": self.raw_score.deductions.reasons,
            },
            "category_total": self.category_total,
            "final_score": self.final_score,
            "key_strengths": self.raw_score.key_strengths,
            "areas_for_improvement": self.raw_score.areas_for_improvement,
        }


def score_resume(resume_text: str) -> ScoringResult:
    """Run the two-phase LLM evaluation and compute aggregate score.

    Args:
        resume_text: Raw text extracted from the PDF resume

    Returns:
        ScoringResult with detailed breakdown and final score
    """
    # Phase 1: System prompt evaluation (technical recruiter perspective)
    # Phase 2: Criteria prompt evaluation (position-specific scoring)
    # We run BOTH prompts but use the criteria prompt for the final structured score

    criteria_user = CRITERIA_PROMPT_TEMPLATE.format(text_content=resume_text)

    # Call the LLM with structured output
    print(f"[DEBUG] Calling LLM with resume text ({len(resume_text)} chars)", file=sys.stderr)
    parsed_score = parse_scoring(
        system=SYSTEM_PROMPT,
        user=criteria_user,
        schema=ResumeScore,
        max_tokens=16000,
    )
    print(f"[DEBUG] Got parsed score: {parsed_score}", file=sys.stderr)

    # Calculate aggregate
    scores_obj = parsed_score.scores
    category_total = (
        scores_obj.self_projects.score
        + scores_obj.production.score
        + scores_obj.technical_skills.score
        + scores_obj.resume_visual_aesthetics.score
    )
    final_score = (
        category_total
        + parsed_score.bonus_points.total
        - parsed_score.deductions.total
    )

    # Enforce overall cap of 120
    final_score = min(final_score, 120)

    return ScoringResult(
        raw_score=parsed_score,
        category_total=category_total,
        final_score=final_score,
    )


def main() -> None:
    """CLI entry point: extract PDF text and score it."""
    if len(sys.argv) < 2:
        print("Usage: python -m src.resume_scorer <path_to_resume.pdf>", file=sys.stderr)
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"Error: PDF not found at {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Extract text using pdftotext (assumes it's installed)
    import subprocess
    try:
        result = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            check=True,
        )
        resume_text = result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error extracting PDF text: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: pdftotext not found. Install poppler-utils.", file=sys.stderr)
        sys.exit(1)

    # Ensure API key is available
    try:
        require_api_key()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Score the resume
    print("Scoring resume... (this may take 30-60 seconds)", file=sys.stderr)
    result = score_resume(resume_text)

    # Output JSON to stdout
    print(json.dumps(result.to_dict(), indent=2))

    # Print final score summary to stderr for visibility
    print(f"\n=== FINAL SCORE: {result.final_score}/120 ===", file=sys.stderr)


if __name__ == "__main__":
    main()
