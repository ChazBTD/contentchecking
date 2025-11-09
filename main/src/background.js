import { firebaseConfig, getMachineId } from "./firebase-config.js";

console.log("Background script loaded!");

async function getActiveTabUrl() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab?.url || "";
  if (!/^https?:\/\//.test(url)) {
    console.log("Not an http(s) tab:", url);
    return null;
  }
  return url;
}

async function logUrlToFirestore(url) {
  try {
    const base = `https://firestore.googleapis.com/v1/projects/${firebaseConfig.projectId}/databases/(default)/documents`;

    // target doc: workerstatus / workerstatus
    const coll  = encodeURIComponent("workerstatus");
    const docId = encodeURIComponent("workerstatus");

    // fields to write
    const now = new Date().toISOString(); // current timestamp
    const fields = {
      link:              { stringValue: url },
      ID:                { stringValue: "JohnA" },
      "team role":       { stringValue: "software developer" },
      action_timestamp:  { timestampValue: now } // <-- new timestamp field
    };

    // Build updateMask for all four fields (quote those with spaces)
    const maskParts = ["ID", "link", "`team role`", "action_timestamp"]
      .map(encodeURIComponent)
      .map(f => `updateMask.fieldPaths=${f}`)
      .join("&");

    // --- PATCH existing doc (update only these fields) ---
    let res = await fetch(
      `${base}/${coll}/${docId}?key=${firebaseConfig.apiKey}&${maskParts}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fields }),
      }
    );

    // --- If not found, POST (create with same id) ---
    if (res.status === 404) {
      res = await fetch(
        `${base}/${coll}?key=${firebaseConfig.apiKey}&documentId=${docId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ fields }),
        }
      );
    }

    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`Firestore REST ${res.status}: ${txt}`);
    }

    const doc = await res.json();
    console.log("Updated workerstatus fields:", doc.name);
    return true;

  } catch (e) {
    console.error("Firestore REST error:", e);
    const { failedLogs = [] } = await chrome.storage.local.get("failedLogs");
    failedLogs.push({ url, when: new Date().toISOString(), error: String(e) });
    await chrome.storage.local.set({ failedLogs });
    return false;
  }
}

async function retryFailedLogs() {
  const { failedLogs = [] } = await chrome.storage.local.get("failedLogs");
  if (!failedLogs.length) return;
  const remaining = [];
  for (const item of failedLogs) {
    const ok = await logUrlToFirestore(item.url);
    if (!ok) remaining.push(item);
  }
  await chrome.storage.local.set({ failedLogs: remaining });
  console.log(`Retry done. Remaining: ${remaining.length}`);
}

async function checkAndLogUrl() {
  const url = await getActiveTabUrl();
  if (url) await logUrlToFirestore(url);
}

// store recent redirects to avoid loops
const recentRedirects = new Map(); // tabId -> timestamp

async function checkActionAndRedirect(tabId, tabUrl) {
  try {
    if (!tabUrl || !/^https?:\/\//i.test(tabUrl)) return;

    const splash = chrome.runtime.getURL("blocked.html");
    if (tabUrl.startsWith(splash)) return;

    const base = `https://firestore.googleapis.com/v1/projects/${firebaseConfig.projectId}/databases/(default)/documents`;
    const docPath = `${base}/${encodeURIComponent("workerstatus")}/${encodeURIComponent("workerstatus")}?key=${firebaseConfig.apiKey}`;
    const res = await fetch(docPath);
    if (!res.ok) {
      console.error("Firestore fetch failed:", res.status);
      return;
    }

    const data   = await res.json();
    const action = data.fields?.action?.stringValue;
    console.log("action =", action);

    if (!action) return;

    if (action === "block") {
      console.log("Action = block detected!");

      // debounce per tab
      const now = Date.now();
      if (now - (recentRedirects.get(tabId) || 0) < 2000) return;
      recentRedirects.set(tabId, now);

      // 1) force reload so we act immediately
      await chrome.tabs.reload(tabId);

      // 2) then redirect to splash and clear "action"
      setTimeout(async () => {
        const splashUrl = chrome.runtime.getURL("blocked.html");
        console.log("Redirecting to splash page…");
        await chrome.tabs.update(tabId, { url: splashUrl });
        await clearActionInFirestore();
      }, 800);
    }
    else if (action === "warn") {
      console.log("Action = warn detected — showing popup…");
      // needs "scripting" permission in manifest
      await chrome.scripting.executeScript({
        target: { tabId },
        func: () => alert("⚠️ Warning: Please focus on your work."),
      });
      await clearActionInFirestore();
    }
    else if (action === "accept") {
      console.log("Action = accept detected — clearing…");
      await clearActionInFirestore();
    }
  } catch (e) {
    console.error("checkActionAndRedirect error:", e);
  }
}


async function clearActionInFirestore() {
  try {
    const base = `https://firestore.googleapis.com/v1/projects/${firebaseConfig.projectId}/databases/(default)/documents`;
    const coll = encodeURIComponent("workerstatus");
    const docId = encodeURIComponent("workerstatus");
    const url  = `${base}/${coll}/${docId}?key=${firebaseConfig.apiKey}&updateMask.fieldPaths=action`;

    const res = await fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields: { action: { stringValue: "" } } }),
    });

    const txt = await res.text();
    console.log("clearActionInFirestore response:", res.status, txt);
    if (!res.ok) throw new Error(`Failed to clear action: ${res.status} ${txt}`);
  } catch (err) {
    console.error("Error clearing action in Firestore:", err);
  }
}


chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete" || !tab?.url) return;

  const url = tab.url;

  // 1) Hard block for hinge.co
  const blockedUrl = "https://hinge.co/";
  if (url.startsWith(blockedUrl)) {
    const splash = chrome.runtime.getURL("blocked.html");
    if (!url.startsWith(splash)) {
      console.log("Blocking hinge.co and redirecting to splash page…");
      chrome.tabs.update(tabId, { url: splash });
      return;
    }
  }

  // 2) Firestore-driven block
  checkActionAndRedirect(tabId, url);
});


// Also run when user switches to a tab
chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (tab?.url) checkActionAndRedirect(tabId, tab.url);
  } catch (e) {
    console.warn("onActivated get failed:", e);
  }
});


function scheduleAlarm() {
  // 🔹 Logs current tab URL every 30 seconds
  chrome.alarms.create("urlLogger", { periodInMinutes: 0.5 });
  console.log("Alarm set: urlLogger every 30 seconds");

  // 🔹 Checks Firestore action every 5 seconds
  chrome.alarms.create("actionChecker", { periodInMinutes: 1/12 });
  console.log("Alarm set: actionChecker every 5 seconds");
}



chrome.runtime.onInstalled.addListener(() => {
  console.log("onInstalled fired");
  scheduleAlarm();
  setTimeout(checkAndLogUrl, 2000);
});

chrome.runtime.onStartup.addListener(() => {
  console.log("onStartup fired");
  scheduleAlarm();
  setTimeout(checkAndLogUrl, 1000);
});

chrome.alarms.onAlarm.addListener(async (a) => {
  try {
    if (a.name === "urlLogger") {
      console.log("urlLogger tick");
      await checkAndLogUrl();
      await retryFailedLogs();
    }
    else if (a.name === "actionChecker") {
      console.log("actionChecker tick");
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab?.id && tab?.url) {
        await checkActionAndRedirect(tab.id, tab.url);
      }
    }
  } catch (err) {
    console.warn("onAlarm error:", err);
  }
});


// expose for manual testing
globalThis.logUrlToFirestore = logUrlToFirestore;
globalThis.checkAndLogUrl = checkAndLogUrl;
globalThis.retryFailedLogs = retryFailedLogs;

// ---- safe, event-driven kickoff (no top-level await) ----
chrome.runtime.onInstalled.addListener(() => {
  // optional: do a one-time log when the extension is installed/updated
  devRunOnce().catch(err => console.error('devRunOnce failed:', err));
});

// optional: also allow manual trigger from DevTools console
//   chrome.runtime.sendMessage({ type: 'manual-log' })
chrome.runtime.onMessage.addListener((msg) => {
  if (msg?.type === 'manual-log') {
    devRunOnce().catch(err => console.error('manual-log failed:', err));
  }
});

// helper that used to live at top level
async function devRunOnce() {
  const [t] = await chrome.tabs.query({ active: true, currentWindow: true });
  console.log('active url:', t?.url);
  await checkAndLogUrl();
}
chrome.action.onClicked.addListener(() => {
  checkAndLogUrl().catch(console.error);
});
