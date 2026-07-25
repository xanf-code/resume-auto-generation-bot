import { useStore } from '../../store';

export function AlertsBell() {
  const count = useStore((s) => s.notifications.length);
  const clear = useStore((s) => s.clearNotifications);

  return (
    <button
      onClick={clear}
      className="relative text-ink-faint hover:text-ink transition-colors p-1"
      aria-label="Notifications"
      title={count > 0 ? `${count} alert${count === 1 ? '' : 's'} — click to clear` : 'No alerts'}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
      {count > 0 && (
        <span className="absolute -top-0.5 -right-0.5 bg-accent text-paper text-[10px] leading-none min-w-4 h-4 px-1 flex items-center justify-center rounded-full font-semibold">
          {count}
        </span>
      )}
    </button>
  );
}
