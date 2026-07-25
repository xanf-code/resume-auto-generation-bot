/**
 * Locate PDF-visible text inside a LaTeX source string.
 *
 * Reverse SyncTeX without a .synctex.gz — resumes are mostly literal body
 * text, so a text-layer match is accurate enough for jump-to-source.
 */

export interface LatexMatch {
  from: number;
  to: number;
}

/** Mirror of src/compiler/renderer.py::latex_escape for special chars. */
const LATEX_ESCAPE: Record<string, string> = {
  '\\': '\\textbackslash{}',
  '&': '\\&',
  '%': '\\%',
  '#': '\\#',
  _: '\\_',
  $: '\\$',
  '{': '\\{',
  '}': '\\}',
  '~': '\\textasciitilde{}',
  '^': '\\textasciicircum{}',
};

function latexEscape(s: string): string {
  return [...s].map((ch) => LATEX_ESCAPE[ch] ?? ch).join('');
}

function normalizeWs(s: string): string {
  return s.replace(/\s+/g, ' ').trim();
}

/** Case-insensitive indexOf; returns start index or -1. */
function indexOfCI(haystack: string, needle: string): number {
  return haystack.toLowerCase().indexOf(needle.toLowerCase());
}

/**
 * Find the best occurrence of ``query`` (PDF text) in ``source`` (LaTeX).
 * Prefers an exact match, then a LaTeX-escaped form, then a loose
 * whitespace/case-insensitive scan. Returns null when nothing usable matches.
 */
export function findInLatex(source: string, query: string): LatexMatch | null {
  const q = normalizeWs(query);
  // Single glyphs and punctuation are too ambiguous to jump on.
  if (q.length < 2) return null;

  const direct = source.indexOf(q);
  if (direct >= 0) return { from: direct, to: direct + q.length };

  const escaped = latexEscape(q);
  if (escaped !== q) {
    const escIdx = source.indexOf(escaped);
    if (escIdx >= 0) return { from: escIdx, to: escIdx + escaped.length };
  }

  const ci = indexOfCI(source, q);
  if (ci >= 0) return { from: ci, to: ci + q.length };

  // Collapse runs of whitespace in the source and map back to original offsets.
  const compact: { ch: string; orig: number }[] = [];
  let prevSpace = false;
  for (let i = 0; i < source.length; i++) {
    const ch = source[i];
    if (/\s/.test(ch)) {
      if (!prevSpace && compact.length > 0) {
        compact.push({ ch: ' ', orig: i });
        prevSpace = true;
      }
      continue;
    }
    compact.push({ ch, orig: i });
    prevSpace = false;
  }
  const compactStr = compact.map((c) => c.ch).join('');
  const needle = q.toLowerCase();
  const hit = compactStr.toLowerCase().indexOf(needle);
  if (hit < 0) return null;

  const from = compact[hit].orig;
  const last = compact[hit + q.length - 1];
  const to = last.orig + 1;
  return { from, to };
}
