import { useEffect, useRef, useState } from 'react';

interface Props {
  text: string;
}

type CopyState = 'idle' | 'copied' | 'failed';

// Clipboard access fails in ways users actually hit: navigator.clipboard is
// undefined on an insecure origin (a LAN IP served over http://), and
// writeText() rejects when permission is denied. Fall back to a hidden-textarea
// execCommand copy, and if even that fails, say so - a silent no-op reads as a
// broken button.
async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through to the legacy path */
  }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

const STYLE: Record<CopyState, string> = {
  idle: 'text-ink-faint border-rule hover:text-accent hover:border-accent/40',
  copied: 'text-pass border-pass/40',
  failed: 'text-fail border-fail/40',
};

const LABEL: Record<CopyState, string> = {
  idle: 'Copy',
  copied: 'Copied',
  failed: "Couldn't copy",
};

export function CopyButton({ text }: Props) {
  const [state, setState] = useState<CopyState>('idle');
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const handleCopy = async () => {
    const ok = await copyText(text);
    setState(ok ? 'copied' : 'failed');
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setState('idle'), 1500);
  };

  return (
    <button
      type="button"
      onClick={() => void handleCopy()}
      className={`text-[11px] border rounded-[2px] px-2 py-0.5 transition-colors ${STYLE[state]}`}
      aria-label="Copy to clipboard"
    >
      {LABEL[state]}
    </button>
  );
}
