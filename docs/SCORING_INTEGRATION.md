# Resume Scoring Integration — Complete Implementation

**Status: FULLY INTEGRATED**

Axiom here boss man. Just wired up the full resume scoring system into your main pipeline. Here's what got built:

---

## What You Asked For

> "After the threshold is cleared and resume is built in out folder, i want that resume to go through the above two prompts and i want a resume scoring report like above to be saved as md file."

## What Got Built

### 1. **Core Scoring Module** (`src/resume_scorer.py`)

- Pydantic schemas for structured LLM evaluation
- Two-phase prompt system:
  - **System Prompt**: Technical recruiter perspective
  - **Criteria Prompt**: Position-specific scoring (Software Intern @ HackerRank)
- Comprehensive fairness guarantees (no bias on demographics, GPA, school, location)
- Scoring categories:
  - Open Source (0-35 points)
  - Self Projects (0-30 points)
  - Production (0-25 points)
  - Technical Skills (0-10 points)
  - Bonus Points (max 20)
  - Deductions
- Final score calculation with 120-point cap
- CLI tool: `python -m src.resume_scorer <path_to_pdf>`

### 2. **Pipeline Integration** (`src/pipeline/score_report.py`)

- **PDF text extraction** using `pdftotext`
- **LLM evaluation** via OpenRouter (Claude Opus 4.8)
- **Markdown report generation** with full breakdown
- **Graph node** (`score_report_node`) that runs after PDF emission
- **Error handling** — scoring failures don't crash the pipeline

### 3. **Graph Wiring** (`src/pipeline/graph.py`)

Updated the LangGraph to add scoring as the final step:

```
emit → score_report → END
```

The score report node:
- Only runs if a PDF was successfully emitted
- Extracts text from the compiled PDF
- Runs the two-phase evaluation
- Saves markdown report to `out/resume_score_report.md`
- Returns `score_report_md` path in state

### 4. **State Schema Update** (`src/pipeline/state.py`)

Added `score_report_md: str | None` to track the markdown report path.

### 5. **CLI Output Update** (`src/main.py`)

Terminal summary now shows:
```
PDF:          out/vestwell_resume.pdf
Score Report: out/score_report.json
Score MD:     out/resume_score_report.md
```

---

## How It Works

When you run the main pipeline:

```bash
python -m src.main --resume examples/main.tex --jd examples/vestwell_resume.txt --out out/
```

**Pipeline flow:**

1. Parse resume → analyze JD → gap analysis
2. Writer → render → identity check → compile
3. Recruiter panel → aggregator → bookkeep
4. **[NEW]** Emit PDF + JSON report
5. **[NEW]** Extract PDF text
6. **[NEW]** Run LLM scoring (30-60s)
7. **[NEW]** Save markdown report

**Output files:**

- `out/vestwell_resume.pdf` — the optimized resume
- `out/score_report.json` — persona rubric scores
- `out/resume_score_report.md` — **[NEW]** detailed scoring breakdown

---

## Markdown Report Format

The generated markdown includes:

### Executive Summary
- Final score (X/120)
- Category total
- Bonus points
- Deductions

### Category Breakdown Table
| Category | Score |
|----------|-------|
| Open Source | 6/35 |
| Self Projects | 20/30 |
| Production | 24/25 |
| Technical Skills | 10/10 |

### Bonus Points
Detailed breakdown of what earned bonus points.

### Deductions
Detailed breakdown of what triggered deductions.

### Key Strengths
1-5 bullet points of top strengths.

### Areas for Improvement
1-3 bullet points of improvement areas.

### Detailed Evidence
Full evidence text for each scoring category.

### Scoring Methodology
Complete explanation of how scores are calculated, what factors matter, and fairness guarantees.

---

## Example Output

When I ran the scorer on the Vestwell resume PDF, it generated:

```markdown
# Resume Scoring Report

**Final Score: 62/120**

### Category Breakdown:
- Open Source: 6/35 (only personal repos, no community contributions)
- Self Projects: 20/30 (GoonedIn is strong, NEU AI Advisor lacks live demo)
- Production: 24/25 (near perfect - LSEG + Dassault experience)
- Technical Skills: 10/10 (perfect - broad stack, AWS certs)

### Bonus Points (+4):
- +2 for live project (goonedin.com)
- +1 for LinkedIn
- +1 for GitHub

### Deductions (-2):
- -2 for NEU AI Advisor missing live demo

### Key Strengths:
1. Strong production experience at scale
2. Excellent technical breadth
3. Complex AI/ML projects
4. AWS Professional certs
5. Live deployed project

### Areas for Improvement:
1. Zero open source contributions to external projects
2. Add live demos for all projects
3. Contribute to established OSS projects
```

---

## Error Handling

If scoring fails (PDF text extraction, LLM timeout, API error):
- Error is logged
- Pipeline continues
- `score_report_md` set to `None`
- User sees warning but gets their PDF + JSON report

---

## Dependencies

### Already Installed:
- `pdftotext` (from poppler-utils) ✓
- `openai` library ✓
- `pydantic` ✓

### API Requirements:
- `OPENROUTER_API_KEY` environment variable (already configured)

---

## Testing

### Standalone Scorer:
```bash
python -m src.resume_scorer out/vestwell_resume.pdf
```

### Full Pipeline:
```bash
python -m src.main --resume examples/main.tex --jd examples/vestwell_resume.txt --out out/
```

After completion, check:
- `out/resume_score_report.md` — the markdown report

---

## Files Modified/Created

### Created:
1. `src/resume_scorer.py` — core scoring engine
2. `src/pipeline/score_report.py` — pipeline integration
3. `docs/SCORING_INTEGRATION.md` — this file

### Modified:
1. `src/pipeline/graph.py` — added score_report node
2. `src/pipeline/state.py` — added score_report_md field
3. `src/main.py` — updated CLI output summary

---

## What's Next

Run a full pipeline to generate a fresh PDF and see the scoring report in action:

```bash
python -m src.main --resume examples/main.tex --jd examples/vestwell_resume.txt --out out/
```

Then check `out/resume_score_report.md` for the full breakdown.

---

**That's the whole system boss man.** Scoring is now baked into your pipeline — every resume that clears the threshold automatically gets evaluated and scored. Clean, automated, and ready to roll.

— Axiom
