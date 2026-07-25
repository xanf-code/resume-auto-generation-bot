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
          <span className="eyebrow">Preview</span>
        </div>
        <div className="flex-1 flex items-center justify-center px-8 text-center">
          <p className="font-serif italic text-[15px] leading-relaxed text-ink-faint max-w-[220px]">
            {running
              ? 'The preview will be available once the resume is generated.'
              : 'Compile to see a preview.'}
          </p>
        </div>
      </div>
    );
  }

  return <PdfViewer blob={pdfBlob} />;
}
