import { JobStream, type StreamStatus } from './JobStream';
import type { ProgressEvent } from './events';

type EventHandler = (event: ProgressEvent) => void;
type StatusHandler = (status: StreamStatus) => void;

export class StreamManager {
  private streams = new Map<string, JobStream>();

  start(
    jobId: string,
    onEvent: EventHandler,
    onStatus: StatusHandler = () => {},
  ): void {
    if (this.streams.has(jobId)) return;

    // The stream owns its own reconnection (EventSource retries natively). We keep
    // the handle for the life of the job and only drop it on an explicit stop, so
    // a transient blip never orphans a live connection or spawns a duplicate.
    const stream = new JobStream(jobId, onEvent, () => {}, onStatus);

    this.streams.set(jobId, stream);
  }

  stop(jobId: string): void {
    const stream = this.streams.get(jobId);
    if (stream) {
      stream.close();
      this.streams.delete(jobId);
    }
  }

  stopAll(): void {
    for (const stream of this.streams.values()) {
      stream.close();
    }
    this.streams.clear();
  }

  isActive(jobId: string): boolean {
    return this.streams.has(jobId);
  }
}
