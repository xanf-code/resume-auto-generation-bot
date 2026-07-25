import { useState, useRef } from 'react';

interface Props {
  label: string;
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  accept?: string;
}

// A .tex résumé or a job description is a few KB; anything past this is almost
// certainly the wrong file (a PDF, an image), and reading it as text is pointless.
const MAX_FILE_BYTES = 2 * 1024 * 1024;

export function FileOrPasteField({ label, value, onChange, placeholder, accept = '.tex,.txt' }: Props) {
  const [mode, setMode] = useState<'paste' | 'file'>('paste');
  const [fileError, setFileError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    // Reset the input so choosing the same file again always re-fires onChange.
    e.target.value = '';
    if (!file) return;
    setFileError(null);

    if (file.size > MAX_FILE_BYTES) {
      setFileError('That file is over 2 MB — paste the text instead.');
      return;
    }

    const reader = new FileReader();
    reader.onload = (ev) => {
      const content = (ev.target?.result as string) ?? '';
      // An empty read (an empty file, or a binary that decoded to nothing) would
      // otherwise leave the field looking untouched — name the problem instead.
      if (content.trim() === '') {
        setFileError('That file was empty — choose another, or paste the text.');
        return;
      }
      onChange(content);
    };
    reader.onerror = () => {
      setFileError("That file couldn't be read. Try another, or paste the text.");
    };
    reader.readAsText(file);
  };

  const tab = (m: 'paste' | 'file', text: string) => (
    <button
      type="button"
      onClick={() => setMode(m)}
      className={`px-2.5 py-0.5 rounded-[2px] border transition-colors ${
        mode === m
          ? 'border-accent/50 text-accent bg-accent-wash'
          : 'border-transparent text-ink-faint hover:text-ink-soft'
      }`}
    >
      {text}
    </button>
  );

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <label className="eyebrow">{label}</label>
        <div className="flex gap-1 text-[11px]">
          {tab('paste', 'Paste')}
          {tab('file', 'File')}
        </div>
      </div>

      {mode === 'paste' ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={6}
          className="w-full bg-paper-raised border border-rule text-ink font-mono text-[12.5px] leading-relaxed p-3 rounded-[3px] resize-y focus:outline-none focus:border-accent/60 placeholder:text-ink-faint"
        />
      ) : (
        <>
          <div
            className="border border-dashed border-rule hover:border-accent/50 p-6 text-center cursor-pointer rounded-[3px] transition-colors bg-paper-raised"
            onClick={() => inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept={accept}
              onChange={handleFile}
              className="hidden"
            />
            <span className="text-[13px] text-ink-soft">
              {value ? (
                <span className="text-pass">✓ Loaded — {value.length.toLocaleString()} characters</span>
              ) : (
                'Click to choose a file'
              )}
            </span>
          </div>
          {fileError && <p className="text-[12px] text-fail">{fileError}</p>}
        </>
      )}
    </div>
  );
}
