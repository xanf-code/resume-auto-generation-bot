let audioCtx: AudioContext | null = null;

export function preloadChime(): void {
  // AudioContext is created lazily on first user interaction to comply with
  // browser autoplay policies. Calling this warms up the reference.
  if (typeof AudioContext !== 'undefined' && !audioCtx) {
    try {
      audioCtx = new AudioContext();
    } catch {
      // Not supported in this environment
    }
  }
}

export function playChime(): void {
  if (typeof AudioContext === 'undefined') return;

  try {
    if (!audioCtx) {
      audioCtx = new AudioContext();
    }

    const ctx = audioCtx;
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();

    oscillator.connect(gain);
    gain.connect(ctx.destination);

    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(880, ctx.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.3);

    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);

    oscillator.start(ctx.currentTime);
    oscillator.stop(ctx.currentTime + 0.5);
  } catch {
    // Audio not available
  }
}
