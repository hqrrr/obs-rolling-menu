// Current vertical scroll offset (in pixels) for the scrolling list
let scrollOffset = 0;
// Timestamp of the previous animation frame, used to compute delta time
let lastTimestamp = null;

// Container dimensions and scroll speed, driven by backend state
let containerWidth = 600;
let containerHeight = 300;
let scrollSpeed = 30; // pixels per second

// Hash used to detect when the list content or styling has changed
let lastRowsHash = null;

// Top text rotation (header / marquee-like) configuration
let textSegments = [];
let currentSegmentIndex = 0;
// Duration (in seconds) each segment should be visible; provided by backend
let textSegmentDuration = 5;
// Fixed fade-in/fade-out duration (in seconds) for text transitions
const textFadeDuration = 0.5;

let textRotationTimerId = null;
// Hash used to detect changes to the text rotation configuration
let lastTextConfigHash = null;

/**
 * Fetch the latest overlay data from the backend and update the DOM.
 *
 * This includes:
 * - Top text (segments, font, color, fade timing).
 * - Container size, background color and opacity, border radius.
 * - Scrolling list content and font styling.
 *
 * The function is designed to avoid unnecessary DOM rebuilding:
 * - Text rotation is only reset if the text content or duration changes.
 * - List DOM is only rebuilt if the row content or list styles change.
 */
async function fetchOverlayData() {
    try {
        const resp = await fetch("/api/overlay-data");
        const data = await resp.json();

        const headerEl = document.getElementById("overlay-header");
        const listEl = document.getElementById("overlay-list");
        const containerEl = document.getElementById("overlay-root");
        const viewportEl = document.getElementById("overlay-viewport");
        const textEl = document.getElementById("overlay-text");

        // If any of the core elements are missing, abort this update
        if (!headerEl || !listEl || !containerEl || !viewportEl) return;

        if (textEl) {
            // Text font size / color for the top rotating text
            if (data.fontSize != null) {
                textEl.style.fontSize = data.fontSize + "px";
            }
            if (data.color) {
                textEl.style.color = data.color;
            }

            // Font family and weight for the top text
            const fam = data.textFontFamily || "system";
            const w = data.textFontWeight || 400;

            if (fam === "system") {
                textEl.style.fontFamily = `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
            } else {
                textEl.style.fontFamily = `"${fam}", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
            }
            textEl.style.fontWeight = w;

            // Segment display duration (seconds)
            textSegmentDuration =
                data.textSegmentDuration != null
                    ? Number(data.textSegmentDuration)
                    : 5;

            const fullText = data.text || "";

            // Split into segments by ';', trim whitespace, and drop empty segments
            const segments = fullText
                .split(";")
                .map(s => s.trim())
                .filter(s => s.length > 0);

            // If no valid segments are found, use the full text as a single segment
            const effectiveSegments =
                segments.length > 0 ? segments : [fullText];

            // Create a simple hash to detect meaningful changes in text config
            const textConfigHash = JSON.stringify({
                segments: effectiveSegments,
                duration: textSegmentDuration,
            });

            // Only restart the text rotation if content or duration changed
            // This prevents resetting the text every time a non-text setting changes
            if (textConfigHash !== lastTextConfigHash) {
                lastTextConfigHash = textConfigHash;
                setupTextRotation(effectiveSegments);
            }
        }

        // Set header text to the currently selected column name
        headerEl.textContent = data.selected_column || "";

        // Update container dimensions and scroll speed regardless of content changes
        containerWidth = data.containerWidth || 600;
        containerHeight = data.containerHeight || 300;
        scrollSpeed =
            data.scrollSpeed != null && !isNaN(data.scrollSpeed)
                ? Number(data.scrollSpeed)
                : 30;

        // Apply width to the root container
        containerEl.style.width = containerWidth + "px";
        // Apply height to the viewport only (scrolling region)
        viewportEl.style.height = containerHeight + "px";

        // Background color and opacity for the container
        const bgColor = data.backgroundColor || "#000000";
        const bgOpacityRaw =
            data.backgroundOpacity != null ? Number(data.backgroundOpacity) : 0.4;
        const alpha = Math.max(
            0,
            Math.min(1, isNaN(bgOpacityRaw) ? 0.4 : bgOpacityRaw)
        );

        // Normalize #rgb or #rrggbb to r, g, b components
        let hex = bgColor.replace("#", "");
        if (hex.length === 3) {
            hex = hex
                .split("")
                .map(ch => ch + ch)
                .join("");
        }
        const r = parseInt(hex.substring(0, 2), 16) || 0;
        const g = parseInt(hex.substring(2, 4), 16) || 0;
        const b = parseInt(hex.substring(4, 6), 16) || 0;

        containerEl.style.background = `rgba(${r}, ${g}, ${b}, ${alpha})`;

        // Container border radius (in pixels)
        if (data.borderRadius != null) {
            containerEl.style.borderRadius = data.borderRadius + "px";
        }

        const rows = data.rows || [];

        // List font styling (applies to group and item rows in the scrolling list)
        const listFontSize =
            data.listFontSize != null ? Number(data.listFontSize) : 24;
        const listColor =
            data.listColor || "#ffffff";
        const listFam = data.listFontFamily || "system";
        const listWeight = data.listFontWeight || 400;

        /**
         * Apply current list font settings to the given element.
         */
        function applyListFont(el) {
            if (listFam === "system") {
                el.style.fontFamily =
                    `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
            } else {
                el.style.fontFamily =
                    `"${listFam}", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
            }
            el.style.fontWeight = listWeight;
            el.style.fontSize = listFontSize + "px";
            el.style.color = listColor;
        }

        // Build a hash of content + font configuration to detect changes
        const listHash = JSON.stringify({
            rows,
            listFontSize,
            listColor,
            listFam,
            listWeight
        });

        // If there is no change in list data or styling, keep the existing DOM and scroll state
        if (listHash === lastRowsHash) {
            return;
        }

        // Content or list styles changed: rebuild DOM and reset scroll state
        lastRowsHash = listHash;

        listEl.innerHTML = "";
        const inner = document.createElement("div");
        inner.id = "overlay-inner";

        /**
         * Append group and item rows to the target element.
         * Supports:
         * - row is a simple string.
         * - row is an object with { type: "group"|"item", ... }.
         */
        function appendItems(target) {
            rows.forEach(row => {
                // if row is a string, treat it as a simple item
                if (typeof row === "string") {
                    const item = document.createElement("div");
                    item.className = "overlay-item";
                    item.textContent = row;
                    target.appendChild(item);
                    return;
                }

                if (!row || typeof row !== "object") return;

                if (row.type === "group") {
                    const groupEl = document.createElement("div");
                    groupEl.className = "overlay-group";
                    // Render group as e.g. [Artist A].
                    groupEl.textContent = `[${row.label ?? ""}]`;
                    applyListFont(groupEl);
                    target.appendChild(groupEl);
                } else {
                    const itemEl = document.createElement("div");
                    itemEl.className = "overlay-item";
                    itemEl.textContent = row.text ?? "";
                    itemEl.style.fontSize = listFontSize + "px";
                    itemEl.style.color = listColor;
                    applyListFont(itemEl);
                    target.appendChild(itemEl);
                }
            });
        }

        // Duplicate the content:
        // - First copy: actual content
        // - Second copy: enables seamless vertical looping when scrolling
        appendItems(inner);
        appendItems(inner);

        listEl.appendChild(inner);

        // Reset scrolling state when content changes
        scrollOffset = 0;
        lastTimestamp = null;
        inner.style.transform = "translateY(0px)";
    } catch (e) {
        console.error("Error fetching overlay data", e);
    }
}

/**
 * Initialize the top text rotation with the given list of segments.
 *
 * This sets up CSS transitions, clears any previous timers,
 * and kicks off the first segment after a short delay.
 */
function setupTextRotation(segments) {
    const textEl = document.getElementById("overlay-text");
    if (!textEl) return;

    textSegments = segments;
    currentSegmentIndex = 0;

    // Configure CSS transition for fade-in / fade-out
    textEl.style.transition = `opacity ${textFadeDuration}s ease`;
    textEl.style.opacity = 0;

    // Clear any existing rotation timer
    if (textRotationTimerId) {
        clearTimeout(textRotationTimerId);
        textRotationTimerId = null;
    }

    // Start the first segment after a brief delay to ensure styles are applied
    textRotationTimerId = setTimeout(() => {
        showCurrentSegment();
    }, 50);
}

/**
 * Display the current segment and schedule a fade-out to the next segment.
 */
function showCurrentSegment() {
    const textEl = document.getElementById("overlay-text");
    if (!textEl || textSegments.length === 0) return;

    const total = Math.max(textSegmentDuration, textFadeDuration * 2);
    const visibleTime = total - textFadeDuration * 2;

    // textEl.textContent = textSegments[currentSegmentIndex] || "";
    // Use 'innerHTML' instead of 'textContent' to allow simple inline formatting in the text segments
    textEl.innerHTML = textSegments[currentSegmentIndex] || "";
    textEl.style.opacity = 1; // Fade in (relies on CSS transition)

    // After the visible phase, start fading out
    textRotationTimerId = setTimeout(() => {
        fadeToNextSegment();
    }, visibleTime * 1000);
}

/**
 * Fade out the current segment and then advance to the next one.
 */
function fadeToNextSegment() {
    const textEl = document.getElementById("overlay-text");
    if (!textEl) return;

    // Trigger fade-out via CSS opacity
    textEl.style.opacity = 0;

    // After fade-out completes, switch to the next segment and show it
    textRotationTimerId = setTimeout(() => {
        currentSegmentIndex =
            (currentSegmentIndex + 1) % textSegments.length;
        showCurrentSegment();
    }, textFadeDuration * 1000);
}

/**
 * Animation loop for the vertical scrolling list.
 *
 * Uses `requestAnimationFrame` and a time-based step to ensure
 * smooth scrolling independent of frame rate.
 */
function scrollStep(timestamp) {
    const inner = document.getElementById("overlay-inner");

    if (!inner) {
        window.requestAnimationFrame(scrollStep);
        return;
    }

    if (lastTimestamp == null) {
        lastTimestamp = timestamp;
    }

    const dt = (timestamp - lastTimestamp) / 1000.0;
    lastTimestamp = timestamp;

    // Only half of inner.scrollHeight is the "single" content height,
    // because the content is duplicated for seamless looping.
    const singleContentHeight = inner.scrollHeight / 2;

    if (singleContentHeight > 0 && scrollSpeed > 0) {
        scrollOffset += scrollSpeed * dt;

        // Wrap around once we have scrolled through one full content length
        if (scrollOffset >= singleContentHeight) {
            scrollOffset -= singleContentHeight;
        }

        inner.style.transform = `translateY(-${scrollOffset}px)`;
    }

    window.requestAnimationFrame(scrollStep);
}

// Initial fetch so the overlay is populated as soon as the page loads
fetchOverlayData();

// Listen to backend state changes via Server-Sent Events (SSE)
// Whenever the state_version changes, we simply re-fetch the overlay data
const evtSource = new EventSource("/api/stream");

evtSource.onmessage = function (event) {
    // event.data contains the latest version number, but we only care
    // that "something changed", so we trigger a refresh unconditionally
    fetchOverlayData();
};

evtSource.onerror = function (err) {
    // Simple error handler, reconnection logic could be added if needed
    console.error("SSE error:", err);
};

// Start the scrolling animation loop
window.requestAnimationFrame(scrollStep);
