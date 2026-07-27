interface Props {
  onCompile: () => void;
  onSave: () => void;
  onDownload: () => void;
  compiling: boolean;
  saving: boolean;
}

export function EditorToolbar({
  onCompile,
  onSave,
  onDownload,
  compiling,
  saving,
}: Props) {
  const busy = compiling || saving;
  return (
    <div className="flex items-center justify-between gap-2 px-3 sm:px-5 py-2.5 sm:py-3 border-b border-rule bg-paper shrink-0">
      <span className="eyebrow truncate">LaTeX Editor</span>
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={onDownload}
          disabled={busy}
          className="text-[12px] text-ink-soft border border-rule hover:border-ink-faint hover:text-ink px-2.5 sm:px-3 min-h-9 h-9 rounded-[3px] transition-colors disabled:opacity-50"
        >
          <span className="sm:hidden">PDF</span>
          <span className="hidden sm:inline">Download PDF</span>
        </button>
        <button
          onClick={onCompile}
          disabled={busy}
          className="text-[12px] text-ink-soft border border-rule hover:border-ink-faint hover:text-ink px-2.5 sm:px-3 min-h-9 h-9 rounded-[3px] transition-colors disabled:opacity-50"
        >
          {compiling ? 'Compiling…' : 'Compile'}
        </button>
        <button
          onClick={onSave}
          disabled={busy}
          className="text-[12px] font-medium text-paper bg-accent hover:bg-accent-deep px-3 sm:px-3.5 min-h-9 h-9 rounded-[3px] transition-colors disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  );
}
