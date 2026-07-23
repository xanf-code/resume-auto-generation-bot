"""Tectonic subprocess compile — no shell, no shell-escape.

Writes the ``.tex`` to a working directory and runs ``tectonic -X compile``
with an argument list (never a shell string). On failure, error lines are
parsed out of tectonic's stderr for the writer bounce. ``FileNotFoundError``
(tectonic not installed) and ``TimeoutExpired`` are handled gracefully into the
errors list rather than raised.
"""
import os
import subprocess  # nosec B404 - fixed argv, no shell, controlled inputs
import tempfile

# Production default compile timeout in seconds. The smoke test may override
# this for the first-run package fetch, but production stays at 60.
DEFAULT_TIMEOUT = 60

_TEX_FILENAME = "resume.tex"
_PDF_FILENAME = "resume.pdf"


def _parse_errors(stderr: str) -> list[str]:
    """Extract human-readable error lines from tectonic stderr.

    Keeps lines that look like errors (``error:`` markers or LaTeX line
    references) so the writer receives targeted feedback.
    """
    errors: list[str] = []
    for line in stderr.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if "error:" in lowered or stripped.startswith("l.") or "! " in stripped:
            errors.append(stripped)
    return errors


def compile_tex(
    tex_source: str,
    workdir: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[bool, str | None, list[str]]:
    """Compile LaTeX source to PDF via tectonic.

    Args:
        tex_source: The LaTeX document text.
        workdir: Directory to compile in. If ``None``, a fresh temp dir is
            created (and left on disk so the caller can inspect the PDF).
        timeout: Seconds before the compile is killed. Defaults to 60.

    Returns:
        ``(ok, pdf_path, errors)``. On success ``(True, <pdf path>, [])``. On
        any failure ``(False, None, [<error strings>])``.
    """
    tmpdir = workdir if workdir is not None else tempfile.mkdtemp(prefix="resume_")
    os.makedirs(tmpdir, exist_ok=True)

    tex_path = os.path.join(tmpdir, _TEX_FILENAME)
    with open(tex_path, "w", encoding="utf-8") as fh:
        fh.write(tex_source)

    try:
        result = subprocess.run(  # nosec B603 - fixed argv, shell=False
            ["tectonic", "-X", "compile", tex_path],
            cwd=tmpdir,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return (False, None, ["tectonic executable not found on PATH."])
    except subprocess.TimeoutExpired:
        return (
            False,
            None,
            [f"tectonic compile timed out after {timeout}s."],
        )

    pdf_path = os.path.join(tmpdir, _PDF_FILENAME)
    if result.returncode == 0 and os.path.isfile(pdf_path):
        return (True, pdf_path, [])

    errors = _parse_errors(result.stderr or "")
    if not errors:
        errors = [
            f"tectonic exited with code {result.returncode} and no PDF was "
            f"produced."
        ]
    return (False, None, errors)
