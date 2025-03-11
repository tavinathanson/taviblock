// Global variable for block status, default to blocked
let blockStatus = true;
const BLOCK_RULE_ID = 1;

// Function to update the dynamic rule based on current status
function updateDynamicRule() {
  if (blockStatus) {
    chrome.declarativeNetRequest.updateDynamicRules({
      removeRuleIds: [BLOCK_RULE_ID],
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
      }]
    }, () => {
      console.log("Dynamic block rule updated for mail.google.com");
    });
  } else {
    chrome.declarativeNetRequest.updateDynamicRules({
      removeRuleIds: [BLOCK_RULE_ID],
      addRules: []
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
