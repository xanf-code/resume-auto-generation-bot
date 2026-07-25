import { useEffect, useState } from 'react';
import { AlertsBell } from './AlertsBell';
import { useStore } from '../../store';
import { requestPermission } from '../../lib/notify';

type Health = 'unknown' | 'ready' | 'nokey' | 'down';

const HEALTH_META: Record<Health, { color: string; label: string }> = {
  unknown: { color: 'var(--color-ink-faint)', label: 'Connecting' },
  ready: { color: 'var(--color-pass)', label: 'Desk open' },
  nokey: { color: 'var(--color-accent)', label: 'No API key' },
  down: { color: 'var(--color-fail)', label: 'Offline' },
};

function useHealth(): Health {
  const [health, setHealth] = useState<Health>('unknown');

  useEffect(() => {
    let active = true;
    const ping = async () => {
      try {
        const res = await fetch('/api/healthz');
        if (!res.ok) throw new Error('bad status');
        const data = (await res.json()) as { api_key_present?: boolean };
        if (active) setHealth(data.api_key_present ? 'ready' : 'nokey');
      } catch {
        if (active) setHealth('down');
      }
    };
    ping();
    const timer = setInterval(ping, 20000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  return health;
}

export function TopBar() {
  const openModal = useStore((s) => s.openNewJobModal);
  const health = useHealth();
  const meta = HEALTH_META[health];

  const handleNewJob = () => {
    requestPermission();
    openModal();
  };

  return (
    <header className="flex items-center justify-between px-6 h-16 border-b border-rule bg-paper shrink-0">
      <div className="flex flex-col">
        <span className="font-serif text-[22px] font-semibold leading-none tracking-tight text-ink">
          Résumé Desk<span className="text-accent">.</span>
        </span>
      </div>

      <div className="flex items-center gap-5">
        <span className="flex items-center gap-2" title={meta.label}>
          <span
            className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ backgroundColor: meta.color }}
          />
          <span className="text-[11px] text-ink-faint hidden sm:inline">{meta.label}</span>
        </span>
        <AlertsBell />
        <button
          onClick={handleNewJob}
          className="text-[13px] font-medium text-paper bg-accent hover:bg-accent-deep px-4 h-9 rounded-[3px] transition-colors"
        >
          ＋ New résumé
        </button>
      </div>
    </header>
  );
}
