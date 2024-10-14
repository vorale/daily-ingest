let startX, startY, endX, endY;
let isSelecting = false;
let selectionDiv;

function createSelectionOverlay() {
    const overlay = document.createElement('div');
    overlay.style.position = 'fixed';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.width = '100%';
    overlay.style.height = '100%';
    overlay.style.backgroundColor = 'rgba(0,0,0,0.5)';
    overlay.style.zIndex = '9999';
    document.body.appendChild(overlay);

    selectionDiv = document.createElement('div');
    selectionDiv.style.position = 'fixed';
    selectionDiv.style.border = '2px solid red';
    selectionDiv.style.backgroundColor = 'rgba(255,0,0,0.2)';
    selectionDiv.style.display = 'none';
    selectionDiv.style.zIndex = '10000';
    document.body.appendChild(selectionDiv);

    overlay.addEventListener('mousedown', startSelection);
    overlay.addEventListener('mousemove', updateSelection);
    overlay.addEventListener('mouseup', endSelection);
}

function startSelection(e) {
    isSelecting = true;
    startX = e.clientX;
    startY = e.clientY;
    selectionDiv.style.left = startX + 'px';
    selectionDiv.style.top = startY + 'px';
    selectionDiv.style.width = '0px';
    selectionDiv.style.height = '0px';
    selectionDiv.style.display = 'block';
}

function updateSelection(e) {
    if (!isSelecting) return;
    endX = e.clientX;
    endY = e.clientY;
    const width = Math.abs(endX - startX);
    const height = Math.abs(endY - startY);
    selectionDiv.style.width = width + 'px';
    selectionDiv.style.height = height + 'px';
    selectionDiv.style.left = (endX > startX ? startX : endX) + 'px';
    selectionDiv.style.top = (endY > startY ? startY : endY) + 'px';
}

function endSelection() {
    isSelecting = false;
    const selectedArea = {
        x: parseInt(selectionDiv.style.left),
        y: parseInt(selectionDiv.style.top),
        width: parseInt(selectionDiv.style.width),
        height: parseInt(selectionDiv.style.height)
    };
    chrome.runtime.sendMessage({type: "areaSelected", area: selectedArea});
    document.body.removeChild(selectionDiv.parentElement);
    document.body.removeChild(selectionDiv);
}

createSelectionOverlay();
