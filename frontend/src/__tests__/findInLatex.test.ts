import { describe, it, expect } from 'vitest';
import { findInLatex } from '../lib/findInLatex';

const SAMPLE = String.raw`
\section{Experience}
\subsection{Acme Corp — Software Engineer}
\begin{itemize}
  \item Built APIs in Python \& Go for 2M users
  \item Owned the C++ runtime on Linux
\end{itemize}
`;

describe('findInLatex', () => {
  it('finds an exact literal substring', () => {
    const m = findInLatex(SAMPLE, 'Software Engineer');
    expect(m).not.toBeNull();
    expect(SAMPLE.slice(m!.from, m!.to)).toBe('Software Engineer');
  });

  it('finds text that was LaTeX-escaped in the source', () => {
    const m = findInLatex(SAMPLE, 'Python & Go');
    expect(m).not.toBeNull();
    expect(SAMPLE.slice(m!.from, m!.to)).toBe('Python \\& Go');
  });

  it('matches across collapsed whitespace', () => {
    const m = findInLatex(SAMPLE, 'Built APIs in Python');
    expect(m).not.toBeNull();
    expect(SAMPLE.slice(m!.from, m!.to)).toContain('Built APIs in Python');
  });

  it('is case-insensitive when needed', () => {
    const m = findInLatex(SAMPLE, 'acme corp');
    expect(m).not.toBeNull();
    expect(SAMPLE.slice(m!.from, m!.to).toLowerCase()).toBe('acme corp');
  });

  it('rejects queries that are too short', () => {
    expect(findInLatex(SAMPLE, 'A')).toBeNull();
    expect(findInLatex(SAMPLE, '  ')).toBeNull();
  });

  it('returns null when nothing matches', () => {
    expect(findInLatex(SAMPLE, 'Totally Missing Phrase')).toBeNull();
  });
});
