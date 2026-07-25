import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import { EditorView, lineNumbers, highlightActiveLine } from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import { history, historyKeymap } from '@codemirror/commands';
import { keymap } from '@codemirror/view';
import { StreamLanguage } from '@codemirror/language';
import { stex } from '@codemirror/legacy-modes/mode/stex';
import { EditorToolbar } from './EditorToolbar';
import { compileLatex } from '../../../api/compile';
import { getJobPdf } from '../../../api/jobs';
import { downloadBlob } from '../../../lib/download';
import { findInLatex } from '../../../lib/findInLatex';
import { toast } from 'sonner';

interface Props {
  jobId: string;
  initialLatex: string;
  onPdfReady?: (blob: Blob) => void;
}

export type LatexEditorHandle = {
  /** Scroll to and select the best match for PDF text. Returns false if none. */
  jumpToText: (query: string) => boolean;
};

// Light "paper" theme — mono is legitimate here because this is code.
const paperTheme = EditorView.theme(
  {
    '&': { backgroundColor: '#fdfbf6', color: '#1c1b19', height: '100%' },
    '.cm-content': {
      fontFamily: 'JetBrains Mono, monospace',
      fontSize: '12.5px',
      caretColor: '#c0362c',
      padding: '8px 0',
    },
    '.cm-gutters': {
      backgroundColor: '#f3eee4',
      borderRight: '1px solid #e4ddd0',
      color: '#a99f8d',
    },
    '.cm-activeLine': { backgroundColor: 'rgba(192,54,44,0.045)' },
    '.cm-activeLineGutter': { backgroundColor: 'rgba(192,54,44,0.05)', color: '#8a8177' },
    '.cm-cursor': { borderLeftColor: '#c0362c', borderLeftWidth: '2px' },
    '.cm-selectionBackground, .cm-content ::selection': {
      backgroundColor: 'rgba(192,54,44,0.14)',
    },
    '&.cm-focused .cm-selectionBackground': { backgroundColor: 'rgba(192,54,44,0.16)' },
  },
  { dark: false },
);

export const LatexEditor = forwardRef<LatexEditorHandle, Props>(function LatexEditor(
  { jobId, initialLatex, onPdfReady },
  ref,
) {
  const editorRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const [compiling, setCompiling] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  useImperativeHandle(
    ref,
    () => ({
      jumpToText(query: string) {
        const view = viewRef.current;
        if (!view) return false;
        const match = findInLatex(view.state.doc.toString(), query);
        if (!match) {
          toast.message('No matching LaTeX for that text');
          return false;
        }
        view.dispatch({
          selection: { anchor: match.from, head: match.to },
          effects: EditorView.scrollIntoView(match.from, { y: 'center' }),
        });
        view.focus();
        return true;
      },
    }),
    [],
  );

  // Fetch the already-compiled PDF on mount so the preview is immediately available.
  useEffect(() => {
    getJobPdf(jobId)
      .then((blob) => onPdfReady?.(blob))
      .catch(() => {/* no PDF yet — pane stays empty until user compiles */});
  }, [jobId]);

  useEffect(() => {
    if (!editorRef.current) return;

    const state = EditorState.create({
      doc: initialLatex,
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        history(),
        keymap.of(historyKeymap),
        StreamLanguage.define(stex),
        paperTheme,
        EditorView.lineWrapping,
      ],
    });

    const view = new EditorView({ state, parent: editorRef.current });
    viewRef.current = view;

    return () => {
      view.destroy();
      viewRef.current = null;
    };
  }, []);

  const getLatex = () => viewRef.current?.state.doc.toString() ?? initialLatex;

  const handleCompile = async () => {
    setCompiling(true);
    setErrors([]);
    const latex = getLatex();
    try {
      const result = await compileLatex(latex);
      if (result.ok) {
        onPdfReady?.(result.blob);
        toast.success('Compiled — proof updated');
      } else {
        setErrors(result.errors);
        toast.error('Compile failed — see the marks below');
      }
    } catch {
      // A network failure would otherwise leave the button stuck on "Compiling…".
      toast.error('Could not reach the press. Check the connection and try again.');
    } finally {
      setCompiling(false);
    }
  };

  const handleDownload = async () => {
    try {
      const blob = await getJobPdf(jobId);
      downloadBlob(blob, `${jobId}.pdf`);
    } catch {
      toast.error('PDF not available yet');
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-paper-raised">
      <EditorToolbar
        onCompile={handleCompile}
        onDownload={handleDownload}
        compiling={compiling}
      />
      <div ref={editorRef} className="flex-1 min-h-0 overflow-auto" />
      {errors.length > 0 && (
        <div className="border-t-2 border-fail bg-[#fbeeec] p-3 max-h-36 overflow-y-auto shrink-0">
          <span className="eyebrow" style={{ color: 'var(--color-fail)' }}>
            Compiler marks
          </span>
          <div className="mt-1.5 flex flex-col gap-1">
            {errors.map((e, i) => (
              <div key={i} className="text-[12px] font-mono text-fail leading-snug">
                {e}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});
