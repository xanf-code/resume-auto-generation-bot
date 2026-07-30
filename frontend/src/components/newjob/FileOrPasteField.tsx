import { useState, useRef } from 'react';

interface Props {
  label: string;
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  accept?: string;
  /** Textarea rows; use a taller value for the primary (resume) field. */
  rows?: number;
}

// A .tex resume or a job description is a few KB; anything past this is almost
// certainly the wrong file (a PDF, an image), and reading it as text is pointless.
const MAX_FILE_BYTES = 2 * 1024 * 1024;

export function FileOrPasteField({
  label,
  value,
  onChange,
  placeholder,
  accept = '.tex,.txt',
  rows = 6,
}: Props) {
  const [fileError, setFileError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    // Reset the input so choosing the same file again always re-fires onChange.
    e.target.value = '';
    if (!file) return;
    setFileError(null);

    if (file.size > MAX_FILE_BYTES) {
      setFileError('That file is over 2 MB - paste the text instead.');
      return;
    }

    const reader = new FileReader();
    reader.onload = (ev) => {
      const content = (ev.target?.result as string) ?? '';
      // An empty read (an empty file, or a binary that decoded to nothing) would
      // otherwise leave the field looking untouched - name the problem instead.
      if (content.trim() === '') {
        setFileError('That file was empty - choose another, or paste the text.');
        return;
      }
      onChange(content);
    };
    reader.onerror = () => {
      setFileError("That file couldn't be read. Try another, or paste the text.");
    };
    reader.readAsText(file);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    // Reuse the file input path via a synthetic DataTransfer isn't reliable;
    // read the dropped file the same way as the picker.
    setFileError(null);
    if (file.size > MAX_FILE_BYTES) {
      setFileError('That file is over 2 MB - paste the text instead.');
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      const content = (ev.target?.result as string) ?? '';
      if (content.trim() === '') {
        setFileError('That file was empty - choose another, or paste the text.');
        return;
      }
      onChange(content);
    };
    reader.onerror = () => {
      setFileError("That file couldn't be read. Try another, or paste the text.");
    };
    reader.readAsText(file);
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <label className="eyebrow">{label}</label>
        <div className="flex items-center gap-2.5">
          {value.trim() !== '' && (
            <span className="font-mono text-[11px] text-ink-faint tabular-nums">
              {value.length.toLocaleString()} chars
            </span>
          )}
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="text-[11px] px-2.5 py-0.5 rounded-[2px] border border-rule text-ink-soft hover:border-accent/50 hover:text-accent transition-colors"
          >
            Load file
          </button>
          <input
            ref={inputRef}
            type="file"
            accept={accept}
            onChange={handleFile}
            className="hidden"
            aria-label={`Load file for ${label}`}
          />
        </div>
      </div>

      <textarea
        value={value}
        onChange={(e) => {
          setFileError(null);
          onChange(e.target.value);
        }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
        placeholder={placeholder}
        rows={rows}
        className="w-full bg-paper-raised border border-rule text-ink font-mono text-[12.5px] leading-relaxed p-3 rounded-[3px] resize-y focus:outline-none focus:border-accent/60 placeholder:text-ink-faint"
      />
      {fileError && <p className="text-[12px] text-fail">{fileError}</p>}
    </div>
  );
}
