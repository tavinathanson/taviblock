// Global variable for block status, default to blocked
let blockStatus = true;
const BLOCK_RULE_ID = 1;

// Function to update the dynamic rule based on current status
function updateDynamicRule() {
  if (blockStatus) {
    // Add rule to block mail.google.com if not already active
    chrome.declarativeNetRequest.updateDynamicRules({
      addRules: [{
        "id": BLOCK_RULE_ID,
        "priority": 1,
        "action": { "type": "block" },
        "condition": {
          "urlFilter": "mail.google.com",
          "resourceTypes": [
            "main_frame", "sub_frame", "script", "xmlhttprequest",
            "image", "media", "font", "object", "ping", "csp_report", "other"
          ]
        }
      }],
      removeRuleIds: []
    }, () => {
      console.log("Dynamic block rule added for mail.google.com");
    });
  } else {
    // Remove rule if unblocked
    chrome.declarativeNetRequest.updateDynamicRules({
      addRules: [],
      removeRuleIds: [BLOCK_RULE_ID]
    }, () => {
      console.log("Dynamic block rule removed (mail.google.com unblocked)");
    });
  }
}

// Query native messaging host for current block status and update rules accordingly
function updateBlockStatus() {
  const port = chrome.runtime.connectNative("com.example.gmailblockstatus");
  port.onMessage.addListener((response) => {
    if (response && response.status) {
      blockStatus = (response.status === "blocked");
      console.log("Gmail block status updated:", blockStatus);
      updateDynamicRule();
    }
    port.disconnect();
  });
  port.postMessage({ command: "getStatus" });
}

// Initial update and then update every 30 seconds
updateBlockStatus();
setInterval(updateBlockStatus, 30000);
