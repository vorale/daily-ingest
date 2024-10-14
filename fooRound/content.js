var mediaRecorder;
var recordedChunks = [];
var seconds = 0;
var screenshotInterval;
var folderName;
var recordingTabId;  // Variable to store the tab ID
const MAX_RECORDING_TIME = 7200000; // 2 hours in milliseconds
const NO_AUDIO_THRESHOLD = 120000; // 2 minutes in milliseconds
let lastAudioTime = 0;
let audioCheckInterval;

// Listen for messages from content / popup
chrome.runtime.onMessage.addListener(
    function(request, sender, sendResponse) {
        console.log(request);
        if (request.type == "tabRecord"){
            recordingTabId = request.tabId;
            recordTab(request.streamId);
            // sendResponse("startRecording");
        }
        if (request.type  == "stopRecording"){
            mediaRecorder.stop();
            sendResponse("stopRecord");
        }
    }
);

// record the tab only
async function recordTab(streamId) {
    // Create folder for screenshots and recording
    folderName = document.title
        .trim()
        .replace(/\s+/g, '_')
        .replace(/[^a-z0-9_]/gi, '')
        .replace(/_+/g, '_')
        .replace(/^_|_$/g, '');
    await createFolder(folderName);

    // Start screenshot interval
    screenshotInterval = setInterval(captureScreenshot, 10000);

    const constraints = {
        audio: {
            mandatory: {
                chromeMediaSource: 'tab',
                chromeMediaSourceId: streamId
            }
        },
        video: {
            mandatory: {
                chromeMediaSource: 'tab',
                chromeMediaSourceId: streamId
            }
        }
    };

    try {
        const tabCapture = await navigator.mediaDevices.getUserMedia(constraints);

        // Create a new MediaStream for recording
        const recordingStream = new MediaStream();
        
        tabCapture.getAudioTracks().forEach(track => recordingStream.addTrack(track));
        tabCapture.getVideoTracks().forEach(track => recordingStream.addTrack(track));

        mediaRecorder = new MediaRecorder(recordingStream, {
            mimeType: "video/webm;codecs=vp9"
        });

        recordedChunks = [];
        mediaRecorder.ondataavailable = e => {
            if (e.data.size > 0) {
                recordedChunks.push(e.data);
            }
        };

        mediaRecorder.onstop = function() {
            stopRecord(recordedChunks);
            recordingStream.getTracks().forEach(track => track.stop());
            clearInterval(screenshotInterval);
        };

        recordingStream.onended = function() {
            mediaRecorder.stop();
        };

        mediaRecorder.start();

        // Set up recording timer
        recordingTimer = setTimeout(() => {
            console.log('Stopping recording due to 2 hour time limit');
            stopRecording();
        }, MAX_RECORDING_TIME);

        // Ensure the original audio continues to play
        const audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(tabCapture);
        const analyser = audioContext.createAnalyser();
        source.connect(analyser);

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        lastAudioTime = Date.now();

        function checkAudioLevels() {
            analyser.getByteFrequencyData(dataArray);
            const average = dataArray.reduce((a, b) => a + b) / bufferLength;
            
            if (average > 0) {
                lastAudioTime = Date.now();
            } else if (Date.now() - lastAudioTime > NO_AUDIO_THRESHOLD) {
                console.log('No audio detected for 2 minutes. Stopping recording.');
                stopRecording();
                return;
            }
            
            requestAnimationFrame(checkAudioLevels);
        }
        checkAudioLevels();

    } catch (error) {
        console.error('Error accessing media devices:', error);
    }
}

async function createFolder(folderName) {
    return new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: "createFolder", folderName: folderName }, (response) => {
            if (chrome.runtime.lastError) {
                reject(chrome.runtime.lastError);
            } else {
                resolve(response);
            }
        });
    });
}

async function captureScreenshot() {
    try {
        const timestamp = Math.floor(Date.now() / 1000);
        const filename = `screenshot_${timestamp}.png`;
        
        chrome.runtime.sendMessage({
            type: "captureScreenshot",
            folderName: folderName,
            filename: filename,
            tabId: recordingTabId  // Use the saved tab ID
        }, response => {
            if (chrome.runtime.lastError) {
                console.error('Error capturing screenshot:', chrome.runtime.lastError);
            } else if (response.error) {
                console.error('Error capturing screenshot:', response.error);
            }
        });
    } catch (error) {
        console.error('Error requesting screenshot capture:', error);
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }
    clearTimeout(recordingTimer);
    clearInterval(audioCheckInterval);
}

function stopRecord(recordedChunks){
    stopRecording();
    if(mediaRecorder.state == 'recording'){
        mediaRecorder.stop();
    }
    var blob = new Blob(recordedChunks, {
        'type': 'video/mp4'
    });
    var url = URL.createObjectURL(blob);
    
    // Get the current UNIX timestamp
    let timestamp = Math.floor(Date.now() / 1000);
    
    // Create the filename
    let filename = `recording_${timestamp}.mp4`;
    
    // Save the recording to the folder
    chrome.runtime.sendMessage({
        type: "saveRecording",
        folderName: folderName,
        filename: filename,
        url: url
    });
}