import { PdfViewer } from './PdfViewer';

interface Props {
  pdfBlob: Blob | null;
  running?: boolean;
}

export function PdfPane({ pdfBlob, running = false }: Props) {
  if (!pdfBlob) {
    return (
      <div className="flex flex-col h-full">
        <div className="px-5 py-3 border-b border-rule bg-paper shrink-0">
          <span className="eyebrow">Proof</span>
        </div>
        <div className="flex-1 flex items-center justify-center px-8 text-center">
          <p className="font-serif italic text-[15px] leading-relaxed text-ink-faint max-w-[220px]">
            {running
              ? 'The proof is pulled once the press finishes its run.'
              : 'Compile the manuscript to pull a fresh proof.'}
          </p>
        </div>
      </div>
    );
  }

  return <PdfViewer blob={pdfBlob} />;
}
