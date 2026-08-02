"""PipelineState - the shared TypedDict flowing through the LangGraph.

``total=False`` so partial states are valid: each node fills in the fields for
its lifecycle stage without needing to populate the whole dict.
"""
from typing import TypedDict

from src.pipeline.schemas import (
    IdentityLedger,
    InventedTool,
    JDVector,
    PanelScore,
    ProjectBullets,
    ReframingTarget,
    ResumeStruct,
    SelectedProject,
    SkillDump,
    WriterOutput,
)
from src.pipeline.tuning import PipelineTuning


class PipelineState(TypedDict, total=False):
    """State passed between pipeline nodes, grouped by lifecycle stage."""

    # --- inputs ---------------------------------------------------------------
    resume_tex_raw: str
    jd_raw: str
    enable_scoring: bool
    # Per-run tuning knobs (threshold, floor, loop/retry budgets, rubric
    # weights). Absent → nodes fall back to PipelineTuning.defaults() via
    # get_tuning(), which mirrors the config.settings constants.
    tuning: "PipelineTuning"
    # Per-resume bullet shape selection. None / absent → default rotation over
    # all four shapes. One name → use only that shape. Subset → rotate within it.
    bullet_shapes: list[str] | None
    # Per-resume bullet budget. Each element is the exact count required for
    # the role at that index (role_bullet_counts[0] → role index 0, etc.).
    # None / absent → DEFAULT_ROLE_BULLET_COUNTS ([4, 4]).
    role_bullet_counts: list[int] | None
    # Retrieved-examples prompt block (Phase 4's retrieval output, already
    # labelled). Absent/None → the Writer's PROVEN EXAMPLES section is omitted.
    proven_examples: str | None

    # --- extraction -----------------------------------------------------------
    resume_struct: ResumeStruct
    identity_ledger: IdentityLedger
    jd_vector: JDVector
    # JD Tagger's domain tags for this run (0-3, from DOMAIN_VOCAB). Feeds
    # ``envelope_for()`` so the Writer and Skeptic share one enforceable
    # fabrication vocabulary instead of un-enforced prose. Set once by
    # ``analyze_jd``, invariant across revisions.
    jd_domains: list[str]
    gap_targets: list[ReframingTarget]

    # --- writer ---------------------------------------------------------------
    writer_output: WriterOutput
    latex_rendered: str

    # --- compile --------------------------------------------------------------
    compile_ok: bool
    compile_errors: str

    # --- eval -----------------------------------------------------------------
    panel_scores: list[PanelScore]
    # Exact-match memoization for the recruiter panel: the rendered LaTeX last
    # scored, and the scores it produced. When a later iteration's
    # latex_rendered is byte-identical (the writer converged/plateaued),
    # recruiter_panel reuses these instead of re-running all four persona
    # calls. MUST be declared here - LangGraph silently drops updates to
    # channels absent from this schema (see length_violations history above).
    panel_cache_latex: str
    panel_cache_scores: list[PanelScore]
    aggregate_score: float
    passed: bool
    # Ranked revision directives distilled by the aggregator.
    revision_notes: list[str]

    # --- length gate ----------------------------------------------------------
    # Recorded by ``check_bullet_lengths``; a non-empty list routes back to the
    # writer (within the length-retry budget). Absent/empty means every bullet
    # is in-band. MUST be declared here - LangGraph silently drops updates to
    # channels that are not part of the state schema, which would make the gate
    # a no-op.
    length_violations: list[str]
    # Recorded alongside length_violations by ``check_bullet_lengths`` when one
    # or more roles have the wrong bullet count. Routes back to the writer via
    # the same retry mechanism as length violations. MUST be declared here.
    count_violations: list[str]
    # Per-iteration length-retry counter. Reset in ``bookkeep_node`` alongside
    # ``compile_retries`` so each revision iteration gets a fresh budget.
    length_retries: int

    # --- compile-loop / identity bookkeeping ----------------------------------
    # Recorded by ``identity_check_node``; a non-empty list routes back to the
    # writer. Absent/empty means the render is clean.
    identity_violations: list[str]
    # Per-iteration compile-retry counter, separate from ``iteration`` so a
    # compile bounce never consumes a revision iteration.
    compile_retries: int
    # Global identity-retry counter. Incremented each time identity_check_node
    # detects violations; NOT reset on clean passes (global budget, not per-iter).
    identity_retries: int

    # --- skills (generated once, before the writer loop) ---------------------
    # Produced by ``generate_skills`` and stable across all revision iterations.
    # MUST be declared here - LangGraph silently drops updates to channels absent
    # from the state schema.
    skill_dump: SkillDump

    # --- projects (selected once, written once, locked thereafter) -----------
    # ``selected_projects`` is set by project_select_node (fires once in the linear
    # spine before the writer loop). ``project_bullets`` is extracted from
    # writer_output.projects by check_bullet_lengths on the first pass and never
    # overwritten again. MUST be declared here - LangGraph silently drops updates
    # to channels absent from this schema.
    selected_projects: list[SelectedProject]
    project_bullets: list[ProjectBullets]
    # Writer's fabrication ledger, locked once by check_bullet_lengths on the
    # clean first pass, invariant thereafter (same lock as project_bullets
    # above). MUST be declared here - LangGraph silently drops updates to
    # channels absent from this schema.
    invented_stack: list[InventedTool]

    # --- bookkeeping ----------------------------------------------------------
    iteration: int
    best_score: float
    best_latex: str
    # Single-source-of-truth routing decision written by ``bookkeep_node``;
    # ``route_after_aggregator`` reads it verbatim instead of re-deriving
    # pass/fail/cap-hit from ``passed``/``iteration`` independently. MUST be
    # declared here - LangGraph silently drops updates to channels absent
    # from this schema (same trap as skill_dump / length_violations above).
    route: str
    # PDF path corresponding to the best-scoring draft. Tracked alongside
    # best_latex so emit can copy the correct file even after later iterations
    # overwrite pdf_path.
    best_pdf_path: str
    pdf_path: str

    # --- emit -----------------------------------------------------------------
    # True when the loop terminated by hitting MAX_ITERATIONS without passing;
    # the emitter surfaces the best-scoring draft with a warning.
    cap_hit: bool
    # Set by the emit node once outputs are written (terminal signal + paths).
    emitted: bool
    output_pdf: str
    output_report: str
    # Path to skills.json. MUST be declared - LangGraph silently drops updates to
    # channels absent from this schema (same trap as skill_dump / length_violations).
    output_skills: str
    # Seeded by the CLI so the emit node knows where to write.
    out_dir: str
    # When False the emit node skips writing score_report.json and skills.json
    # to disk (web path: data is already in-memory; no durable local files needed).
    emit_write_files: bool
    # Stem of the JD file path (e.g. "amazon_sde" from "examples/amazon_sde.txt").
    # Used by emit to name the output PDF after the JD.
    jd_name: str
    # Markdown scoring report generated by score_report_node after PDF emission.
    score_report_md: str | None
