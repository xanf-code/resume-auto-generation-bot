import { isProgressEvent, isTerminalStage } from './events';
import type { ProgressEvent } from './events';

type EventHandler = (event: ProgressEvent) => void;
type ErrorHandler = (err: Event) => void;
export type StreamStatus = 'open' | 'reconnecting' | 'closed';
type StatusHandler = (status: StreamStatus) => void;

// The backend sends *named* SSE events (`event: progress|done|failed`), which
// EventSource.onmessage does NOT receive - that only fires for unnamed frames.
// We must register a listener per named event.
const NAMED_EVENTS = ['progress', 'done', 'failed'] as const;

export class JobStream {
  private source: EventSource;
  private onEvent: EventHandler;
  private onError: ErrorHandler;
  private onStatus: StatusHandler;
  private closed = false;

  constructor(
    jobId: string,
    onEvent: EventHandler,
    onError: ErrorHandler = () => {},
    onStatus: StatusHandler = () => {},
  ) {
    this.onEvent = onEvent;
    this.onError = onError;
    this.onStatus = onStatus;
    this.source = new EventSource(`/api/jobs/${jobId}/events`);

    const handle = (msg: MessageEvent) => {
      try {
        const parsed = JSON.parse(msg.data) as unknown;
        if (!isProgressEvent(parsed)) return;
        this.onEvent(parsed);
        if (isTerminalStage(parsed.stage)) {
          this.close();
        }
      } catch {
        // ignore malformed frames
      }
    };

    for (const name of NAMED_EVENTS) {
      this.source.addEventListener(name, handle as EventListener);
    }
    // Fallback for any unnamed frames.
    this.source.onmessage = handle;

    this.source.onopen = () => {
      if (!this.closed) this.onStatus('open');
    };

    this.source.onerror = (e) => {
      if (this.closed) return;
      // EventSource auto-reconnects on its own: readyState CONNECTING means the
      // browser is still retrying (don't tear it down); CLOSED means it gave up.
      // Surface both so the UI can show a reconnecting state and reconcile the
      // job's real status out-of-band rather than freezing on stale progress.
      if (this.source.readyState === EventSource.CLOSED) {
        this.onStatus('closed');
      } else {
        this.onStatus('reconnecting');
      }
      this.onError(e);
    };
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.onStatus('closed');
    this.source.close();
  }
}
