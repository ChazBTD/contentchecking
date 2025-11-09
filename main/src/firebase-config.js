// firebase-config.js
export const firebaseConfig = {
  apiKey: "522ca07d6214564d525b754b7032bb66262ae165",
  projectId: "contentcheck-d12fe",
};

export const COLLECTION_NAME = "urls";

// Persist a stable machine id the first time, reuse thereafter
export async function getMachineId() {
  const { machineId } = await chrome.storage.local.get("machineId");
  if (machineId) return machineId;
  const newId = crypto.randomUUID();           // one-time
  await chrome.storage.local.set({ machineId: newId });
  return newId;
}