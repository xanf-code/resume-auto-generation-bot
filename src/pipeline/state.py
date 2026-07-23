"""PipelineState — the shared TypedDict flowing through the LangGraph.

``total=False`` so partial states are valid: each node fills in the fields for
its lifecycle stage without needing to populate the whole dict.
"""
from typing import TypedDict

from src.pipeline.schemas import (
    IdentityLedger,
    JDVector,
    PanelScore,
    ReframingTarget,
    ResumeStruct,
    WriterOutput,
)


class PipelineState(TypedDict, total=False):
    """State passed between pipeline nodes, grouped by lifecycle stage."""

    # --- inputs ---------------------------------------------------------------
    resume_tex_raw: str
    jd_raw: str

    # --- extraction -----------------------------------------------------------
    resume_struct: ResumeStruct
    identity_ledger: IdentityLedger
    jd_vector: JDVector
    gap_targets: list[ReframingTarget]

    # --- writer ---------------------------------------------------------------
    writer_output: WriterOutput
    latex_rendered: str

    # --- compile --------------------------------------------------------------
    compile_ok: bool
    compile_errors: str

    # --- eval -----------------------------------------------------------------
    panel_scores: list[PanelScore]
    aggregate_score: float
    passed: bool
    # Ranked revision directives distilled by the aggregator. Widened from
    # ``str`` to ``list[str]`` in Phase 6 to match the aggregator's output; the
    # Writer renders either shape (a lone legacy string is still accepted).
    revision_notes: list[str]

    # --- compile-loop / identity bookkeeping ----------------------------------
    # Recorded by ``identity_check_node``; a non-empty list routes back to the
    # writer. Absent/empty means the render is clean.
    identity_violations: list[str]
    # Per-iteration compile-retry counter, separate from ``iteration`` so a
    # compile bounce never consumes a revision iteration.
    compile_retries: int

    # --- bookkeeping ----------------------------------------------------------
    iteration: int
    best_score: float
    best_latex: str
    pdf_path: str

    # --- emit -----------------------------------------------------------------
    # True when the loop terminated by hitting MAX_ITERATIONS without passing;
    # the emitter surfaces the best-scoring draft with a warning.
    cap_hit: bool
    # Set by the emit node once outputs are written (terminal signal + paths).
    emitted: bool
    output_pdf: str
    output_report: str
    # Seeded by the CLI so the emit node knows where to write.
    out_dir: str
