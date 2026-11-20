// An optional, short-lived session prepared only after a visitor opens the widget.
// Microphone permission and device access still happen only on Connect.
export class SessionPreparation {
  constructor(start, ttlMs = 20000) {
    this.startSession = start;
    this.ttlMs = ttlMs;
    this.pending = null;
  }

  start(data) {
    if (this.pending) return;
    const controller = new AbortController();
    const entry = {controller, promise: null, timer: null};
    entry.promise = Promise.resolve().then(() => this.startSession(data, controller.signal)).catch(() => null);
    entry.timer = setTimeout(() => { if (this.pending === entry) this.cancel(); }, this.ttlMs);
    this.pending = entry;
  }

  take() {
    const entry = this.pending;
    if (!entry) return null;
    this.pending = null;
    clearTimeout(entry.timer);
    return entry.promise;
  }

  cancel() {
    const entry = this.pending;
    if (!entry) return;
    this.pending = null;
    clearTimeout(entry.timer);
    entry.controller.abort();
  }
}
