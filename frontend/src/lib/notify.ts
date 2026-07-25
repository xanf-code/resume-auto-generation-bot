export function requestPermission(): void {
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission().catch(() => {});
  }
}

export function showNotification(title: string, body: string, tag: string): void {
  if (!('Notification' in window)) return;
  if (Notification.permission !== 'granted') return;
  if (!document.hidden) return;
  new Notification(title, { body, tag });
}

export function completionAlert(
  jobId: string,
  label: string,
  score?: number,
): void {
  const body = score !== undefined ? `${label} — score ${score}` : label;
  showNotification('resume-bot', body, jobId);
}
