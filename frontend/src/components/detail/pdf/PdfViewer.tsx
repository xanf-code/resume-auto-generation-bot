import { useEffect, useMemo, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

interface Props {
  blob: Blob;
}

const PAGE_GUTTER = 48; // horizontal padding around the page in the scroll area
const MIN_PAGE_WIDTH = 240;
const MAX_PAGE_WIDTH = 720;

export function PdfViewer({ blob }: Props) {
  const [numPages, setNumPages] = useState<number>(0);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Uint8Array | null>(null);
  const [failed, setFailed] = useState(false);
  const [pageWidth, setPageWidth] = useState(332);
  const viewportRef = useRef<HTMLDivElement>(null);

  // Feed pdf.js the raw bytes instead of a blob: URL — the URL path sends the
  // blob through pdf.js's network stream, which chokes on header construction.
  useEffect(() => {
    let active = true;
    setFailed(false);
    setData(null);
    setPage(1);
    blob
      .arrayBuffer()
      .then((buf) => {
        if (active) setData(new Uint8Array(buf));
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [blob]);

  // Scale the proof page with the pane so collapsing side rails actually
  // gives the PDF the reclaimed width (not just empty gutter).
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const measure = () => {
      const next = Math.round(
        Math.min(
          MAX_PAGE_WIDTH,
          Math.max(MIN_PAGE_WIDTH, el.clientWidth - PAGE_GUTTER),
        ),
      );
      setPageWidth((prev) => (prev === next ? prev : next));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const file = useMemo(() => (data ? { data } : null), [data]);

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between px-5 py-3 border-b border-rule bg-paper shrink-0">
        <span className="eyebrow">Proof</span>
        <div className="flex items-center gap-3 font-mono text-[12px] text-ink-faint">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="disabled:opacity-25 hover:text-ink transition-colors"
            aria-label="Previous page"
          >
            ‹
          </button>
          <span className="tabular-nums">
            {page} / {numPages || '·'}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(numPages, p + 1))}
            disabled={page >= numPages}
            className="disabled:opacity-25 hover:text-ink transition-colors"
            aria-label="Next page"
          >
            ›
          </button>
        </div>
      </div>
      <div
        ref={viewportRef}
        className="flex-1 min-h-0 overflow-auto flex justify-center bg-paper-sunk py-6"
      >
        {failed ? (
          <p className="font-serif italic text-[14px] leading-relaxed text-fail mt-8 max-w-[240px] text-center px-4">
            This proof couldn't be read. Recompile to pull a fresh one.
          </p>
        ) : (
          <Document
            file={file}
            onLoadSuccess={({ numPages: n }) => setNumPages(n)}
            onLoadError={() => setFailed(true)}
            loading={
              <span className="font-serif italic text-[14px] text-ink-faint mt-8">
                Developing…
              </span>
            }
            error={
              <p className="font-serif italic text-[14px] leading-relaxed text-fail mt-8 max-w-[240px] text-center px-4">
                This proof couldn't be read. Recompile to pull a fresh one.
              </p>
            }
          >
            <div className="shadow-[0_2px_16px_rgba(28,27,25,0.12)]">
              <Page pageNumber={page} width={pageWidth} />
            </div>
          </Document>
        )}
      </div>
    </div>
  );
}
