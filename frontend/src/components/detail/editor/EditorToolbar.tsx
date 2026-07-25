interface Props {
  onCompile: () => void;
  onDownload: () => void;
  compiling: boolean;
}

export function EditorToolbar({ onCompile, onDownload, compiling }: Props) {
  return (
    <div className="flex items-center justify-between px-5 py-3 border-b border-rule bg-paper shrink-0">
      <span className="eyebrow">Manuscript · LaTeX</span>
      <div className="flex items-center gap-2">
        <button
          onClick={onDownload}
          className="text-[12px] text-ink-soft border border-rule hover:border-ink-faint hover:text-ink px-3 h-8 rounded-[3px] transition-colors"
        >
          Download PDF
        </button>
        <button
          onClick={onCompile}
          disabled={compiling}
          className="text-[12px] font-medium text-paper bg-accent hover:bg-accent-deep px-3.5 h-8 rounded-[3px] transition-colors disabled:opacity-50"
        >
          {compiling ? 'Setting…' : 'Compile'}
        </button>
      </div>
    </div>
  );
}
