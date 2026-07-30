interface Props {
  jobCount: number;
  onOpenModal: () => void;
}

export function AbEmptyState({ jobCount, onOpenModal }: Props) {
  const provenance =
    jobCount > 0
      ? `${jobCount} of your resumes on file — padded with invented fixtures if the bracket needs more.`
      : 'No resumes on file yet — the bracket fills entirely with invented fixtures until you add one.';

  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-6 sm:px-8">
      <span className="eyebrow">A/B testing</span>
      <p className="mt-2 font-serif text-[22px] sm:text-[26px] leading-snug text-ink max-w-md">
        Run your resumes through a single-elimination bracket.
      </p>
      <p className="mt-3 text-[14px] text-ink-soft max-w-md leading-relaxed">
        Pick a panel of judges, set the chalk-to-chaos dial, and watch scores race
        round by round until one resume is crowned champion.
      </p>
      <button
        onClick={onOpenModal}
        className="mt-6 text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-4 min-h-11 h-11 sm:h-9 sm:min-h-9 rounded-[3px] transition-colors"
      >
        Create A/B test
      </button>
      <p className="mt-4 text-[11px] text-ink-faint font-mono max-w-sm leading-relaxed">
        {provenance}
      </p>
    </div>
  );
}
