chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === "createFolder") {
        chrome.downloads.download({
            url: 'data:text/plain,',
            filename: `${request.folderName}/.placeholder`,
            saveAs: false
        }, () => {
            sendResponse({ success: true });
        });
        return true;
    }

    if (request.type === "saveScreenshot") {
        chrome.downloads.download({
            url: request.dataUrl,
            filename: `${request.folderName}/${request.filename}`,
            saveAs: false
        });
    }

    if (request.type === "saveRecording") {
        chrome.downloads.download({
            url: request.url,
            filename: `${request.folderName}/${request.filename}`,
            saveAs: false
        });
    }

    if (request.type === "captureScreenshot") {
        chrome.tabs.get(request.tabId, function(tab) {
            if (chrome.runtime.lastError) {
                sendResponse({error: chrome.runtime.lastError.message});
                return;
            }
            
            if (tab.url.startsWith("chrome-devtools://")) {
                sendResponse({error: "Cannot capture screenshot of DevTools"});
                return;
            }
            
            chrome.tabs.captureVisibleTab(tab.windowId, {format: 'png'}, dataUrl => {
                if (chrome.runtime.lastError) {
                    sendResponse({error: chrome.runtime.lastError.message});
                } else {
                    chrome.downloads.download({
                        url: dataUrl,
                        filename: `${request.folderName}/${request.filename}`,
                        saveAs: false
                    }, downloadId => {
                        if (chrome.runtime.lastError) {
                            sendResponse({error: chrome.runtime.lastError.message});
                        } else {
                            sendResponse({success: true});
                        }
                    });
                }
            });
        });
        return true; // Indicates we will send a response asynchronously
    }
});
