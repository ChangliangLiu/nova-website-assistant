// Access the microphone only when Connect is pressed. Discard late results if
// the user cancels while a permission prompt or a session request is open.
export async function connectClient(current, {cloud, requestData, isCurrent, prepared = null, timeoutMs = 45000}) {
  const disconnect = () => current.disconnect().catch(() => {});
  const attempt = (async () => {
    await current.initDevices();
    if (!isCurrent()) { await disconnect(); return; }
    if (cloud) {
      let connection = prepared ? await prepared : null;
      if (!isCurrent()) { await disconnect(); return; }
      if (!connection) connection = await current.startBot({endpoint: '/api/widget/session', requestData});
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
