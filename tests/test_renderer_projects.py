"""Tests for patch_project_bullets() in the renderer.

The project patcher must obey the SAME integrity guarantee as patch_bullets:
surgically replace only the heading text, href, and itemize contents of each
project entry. Every other byte - spacing commands, comments, blank lines -
is preserved verbatim from the original template.
"""
import pytest

from src.compiler.renderer import patch_project_bullets, latex_escape
from src.pipeline.schemas import ProjectBullets, SelectedProject

TEX_WITH_PROJECTS = r"""
\section*{Experience}
\textbf{Software Engineer,} {Acme} -- Boston, MA \hfill June 2025 -- Jan 2026 \\
\vspace{-9pt}
\begin{itemize}
  \item Experience bullet must not be touched
\end{itemize}

% projects section
\section*{Projects}
\textbf{OldProject} \hfill \href{https://old.com/}{old.com} \\
\vspace{-9pt}
\begin{itemize}
  \item Old bullet one
  \item Old bullet two
  \item Old bullet three
\end{itemize}

\textbf{OldProject2} \hfill \href{https://old2.com/}{GitHub} \\
\vspace{-9pt}
\begin{itemize}
  \item Old bullet A
  \item Old bullet B
\end{itemize}

\vspace{-18.5pt}

\section*{Skills}
\textbf{Language:} Python
"""

TEX_WITHOUT_PROJECTS = r"""
\section*{Experience}
\textbf{Engineer,} {Acme} \hfill 2023 \\

\section*{Skills}
\textbf{Language:} Python
"""


def _selected() -> list[SelectedProject]:
    return [
        SelectedProject(rank=1, id="goonedin", context="...", link="https://goonedin.vercel.app/", bullet_count=3),
        SelectedProject(rank=2, id="spendai", context="...", link="https://github.com/spendai", bullet_count=2),
    ]


def _project_bullets() -> list[ProjectBullets]:
    return [
        ProjectBullets(rank=1, heading="Real-Time Job Aggregation Engine", bullets=["Bullet one", "Bullet two", "Bullet three"]),
        ProjectBullets(rank=2, heading="AI Financial Audit Platform", bullets=["Bullet A", "Bullet B"]),
    ]


class TestContentReplacement:
    def test_new_headings_present(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        assert "Real-Time Job Aggregation Engine" in result
        assert "AI Financial Audit Platform" in result

    def test_old_headings_gone(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        assert "OldProject" not in result

    def test_old_bullets_gone(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        assert "Old bullet one" not in result
        assert "Old bullet A" not in result

    def test_new_bullets_present(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        for b in ("Bullet one", "Bullet two", "Bullet three", "Bullet A", "Bullet B"):
            assert b in result

    def test_new_links_present(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        assert "https://goonedin.vercel.app/" in result
        assert "https://github.com/spendai" in result

    def test_old_links_gone(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        assert "old.com" not in result
        assert "old2.com" not in result

    def test_k1_has_three_bullets(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        k1 = result[result.index("Real-Time Job"):result.index("AI Financial")]
        assert k1.count(r"\item") == 3

    def test_k2_has_two_bullets(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        k2 = result[result.index("AI Financial"):result.index(r"\section*{Skills}")]
        assert k2.count(r"\item") == 2

    def test_k1_before_k2(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        assert result.index("Real-Time Job") < result.index("AI Financial")


class TestStructuralPreservation:
    """Integrity guarantee #1: only heading/href/itemize contents change."""

    def test_preserves_projects_comment(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        assert "% projects section" in result

    def test_preserves_vspace_9pt_commands(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        # Two project entries in the template, each preceded by \vspace{-9pt},
        # plus one in the Experience section = 3 total, all preserved.
        assert result.count(r"\vspace{-9pt}") == TEX_WITH_PROJECTS.count(r"\vspace{-9pt}")

    def test_preserves_trailing_vspace(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        assert r"\vspace{-18.5pt}" in result

    def test_preserves_section_header(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        assert r"\section*{Projects}" in result

    def test_preserves_skills_section_verbatim(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        assert r"\section*{Skills}" in result
        assert r"\textbf{Language:} Python" in result

    def test_experience_section_untouched(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        assert "Experience bullet must not be touched" in result
        assert r"\textbf{Software Engineer,} {Acme} -- Boston, MA \hfill June 2025 -- Jan 2026 \\" in result

    def test_experience_section_bytes_identical(self):
        """Everything before \\section*{Projects} must be byte-identical."""
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        marker = r"\section*{Projects}"
        assert result[:result.index(marker)] == TEX_WITH_PROJECTS[:TEX_WITH_PROJECTS.index(marker)]

    def test_skills_section_bytes_identical(self):
        """Everything from \\section*{Skills} onward must be byte-identical."""
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        marker = r"\section*{Skills}"
        assert result[result.index(marker):] == TEX_WITH_PROJECTS[TEX_WITH_PROJECTS.index(marker):]


class TestEscapingAndEdgeCases:
    def test_latex_escape_applied_to_bullets(self):
        bullets = [
            ProjectBullets(rank=1, heading="K1", bullets=["Cut latency 40% via Redis", "Scaled to 1M users", "Used C# and Go"]),
            ProjectBullets(rank=2, heading="K2", bullets=["Saved $5k monthly", "Hit 99% uptime"]),
        ]
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), bullets)
        assert r"40\%" in result
        assert r"\$5k" in result
        assert r"99\%" in result

    def test_latex_escape_applied_to_heading(self):
        bullets = [
            ProjectBullets(rank=1, heading="Search & Ranking Platform", bullets=["b1", "b2", "b3"]),
            ProjectBullets(rank=2, heading="K2", bullets=["b4", "b5"]),
        ]
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), bullets)
        assert r"Search \& Ranking Platform" in result

    def test_noop_when_no_projects_section(self):
        result = patch_project_bullets(TEX_WITHOUT_PROJECTS, _selected(), _project_bullets())
        assert result == TEX_WITHOUT_PROJECTS

    def test_noop_when_no_selected_projects(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, [], _project_bullets())
        assert result == TEX_WITH_PROJECTS

    def test_noop_when_no_project_bullets(self):
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), [])
        assert result == TEX_WITH_PROJECTS

    def test_compiles_to_valid_structure(self):
        """begin/end itemize must stay balanced after patching."""
        result = patch_project_bullets(TEX_WITH_PROJECTS, _selected(), _project_bullets())
        assert result.count(r"\begin{itemize}") == result.count(r"\end{itemize}")


# A template whose Projects section uses CUSTOM formatting that differs from
# any hardcoded output format: different vspace values, an inline comment, and
# a trailing annotation on the header line. A surgical patcher preserves all of
# it; a patcher that rebuilds the section silently normalizes it away.
TEX_CUSTOM_FORMATTING = r"""
\section*{Projects}
% first project - keep this comment
\textbf{OldProject} \hfill \href{https://old.com/}{old.com} \\
\vspace{-11pt}
\begin{itemize}
  \item Old bullet one
  \item Old bullet two
  \item Old bullet three
\end{itemize}
\vspace{4pt}

\textbf{OldProject2} \hfill \href{https://old2.com/}{GitHub} \\
\vspace{-7pt}
\begin{itemize}
  \item Old bullet A
  \item Old bullet B
\end{itemize}

\section*{Skills}
\textbf{Language:} Python
"""


class TestCustomFormattingPreserved:
    """A surgical patcher must not normalize the user's own spacing choices."""

    def test_preserves_custom_vspace_11pt(self):
        result = patch_project_bullets(TEX_CUSTOM_FORMATTING, _selected(), _project_bullets())
        assert r"\vspace{-11pt}" in result

    def test_preserves_custom_vspace_7pt(self):
        result = patch_project_bullets(TEX_CUSTOM_FORMATTING, _selected(), _project_bullets())
        assert r"\vspace{-7pt}" in result

    def test_preserves_custom_vspace_4pt(self):
        result = patch_project_bullets(TEX_CUSTOM_FORMATTING, _selected(), _project_bullets())
        assert r"\vspace{4pt}" in result

    def test_preserves_inline_comment(self):
        result = patch_project_bullets(TEX_CUSTOM_FORMATTING, _selected(), _project_bullets())
        assert "% first project - keep this comment" in result

    def test_does_not_inject_foreign_vspace(self):
        """The patcher must not add spacing commands the template never had."""
        result = patch_project_bullets(TEX_CUSTOM_FORMATTING, _selected(), _project_bullets())
        assert r"\vspace{-9pt}" not in result
        assert r"\vspace{-18.5pt}" not in result

    def test_content_still_replaced(self):
        result = patch_project_bullets(TEX_CUSTOM_FORMATTING, _selected(), _project_bullets())
        assert "Real-Time Job Aggregation Engine" in result
        assert "OldProject" not in result
        assert "Old bullet one" not in result
