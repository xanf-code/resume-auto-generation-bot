import { useState } from 'react';

interface Props {
  text: string;
}

export function CopyButton({ text }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <button
      onClick={handleCopy}
      className={`text-[11px] border rounded-[2px] px-2 py-0.5 transition-colors ${
        copied
          ? 'text-pass border-pass/40'
          : 'text-ink-faint border-rule hover:text-accent hover:border-accent/40'
      }`}
      aria-label="Copy to clipboard"
    >
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}
