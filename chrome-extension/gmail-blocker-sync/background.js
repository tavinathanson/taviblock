// Global variable to hold the current block status (default to blocked)
let blockStatus = true;

// Query the native messaging host for current status
function updateBlockStatus() {
  const port = chrome.runtime.connectNative("com.example.gmailblockstatus");
  port.onMessage.addListener((response) => {
    if (response && response.status) {
      blockStatus = (response.status === "blocked");
      console.log("Gmail block status updated:", blockStatus);
    }
    port.disconnect();
  });
  port.postMessage({ command: "getStatus" });
}

// Initial update and then update every 30 seconds
updateBlockStatus();
setInterval(updateBlockStatus, 30000);

// Intercept requests to mail.google.com and cancel if blockStatus is true
chrome.webRequest.onBeforeRequest.addListener(
  function(details) {
    if (blockStatus) {
      console.log("Blocking Gmail request:", details.url);
      return { cancel: true };
    }
  },
  { urls: ["*://mail.google.com/*"] },
  ["blocking"]
);
