// Ask the browser to reduce speaker feedback and background noise. These are
// preferences: unsupported devices may ignore them, and headphones are still
// the most reliable way to prevent echo-triggered interruptions.
export function createDailyTransport(DailyTransport) {
  return new DailyTransport({
    inputSettings: {audio: {settings: {echoCancellation: true, noiseSuppression: true}}}
  });
}

// Initialize the microphone before creating a billable cloud session. If the
// user cancels while a permission prompt is open, discard late results.
export async function connectClient(current, {cloud, requestData, isCurrent, timeoutMs = 45000}) {
  const disconnect = () => current.disconnect().catch(() => {});
  const attempt = (async () => {
    await current.initDevices();
    if (!isCurrent()) { await disconnect(); return; }
    if (cloud) {
      const connection = await current.startBot({endpoint: '/api/widget/session', requestData});
      if (!isCurrent()) { await disconnect(); return; }
      await current.connect(connection);
    } else {
      await current.connect({webrtcRequestParams: {endpoint: '/api/offer', requestData}});
    }
    if (!isCurrent()) await disconnect();
  })();
  let timer;
  try {
    await Promise.race([attempt, new Promise((_, reject) => {
      timer = setTimeout(() => reject(Error('Connection timed out. Check microphone permission and try again.')), timeoutMs);
    })]);
  } finally { clearTimeout(timer); }
}
