from waitress import serve
from flask import Flask, jsonify, request, render_template, Response, send_from_directory
import threading
import time

from reader import read_data, get_grouped_rows
from worker import worker
from preset import list_presets, save_preset, load_preset, delete_preset
from util import parse_group_spec, print_startup_banner, find_free_port

# Read data.xlsx once at startup and keep it in memory.
# `df` holds the full data table, `columns` is the list of column names.
df, columns = read_data()

app = Flask(
    __name__,
    static_folder="ui",      # Folder for static assets (JS, CSS)
    static_url_path="/ui",   # Map URLs under /ui/... to files in static_folder
    template_folder="ui"     # Folder for HTML templates (control.html, overlay.html)
)

# Global state and default values for the overlay appearance/behavior.
# This state is kept in memory only (no persistence across server restarts).
state = {
    "selected_column": columns[0],  # Column used for the main overlay text (default: first column)
    "text": "place holder",         # Free text for the single-line mode (if used)
    "fontSize": 36,                 # Main text font size in pixels
    "color": "#ffffff",             # Main text color
    "backgroundColor": "#000000",   # Background color of the text container
    "backgroundOpacity": 0.4,       # Background opacity (0.0–1.0)
    "containerWidth": 600,          # Overlay container width in pixels
    "containerHeight": 300,         # Overlay container height in pixels
    "scrollSpeed": 30.0,            # Scroll speed in px/s for scrolling mode
    "listFontSize": 24,             # Font size for the list view
    "listColor": "#ffffff",         # Text color for the list view
    "textSegmentDuration": 5.0,     # Duration (in seconds) to hold each text segment
    "groupByColumn": "",            # Grouping specification, e.g., "" or "B" or "B+C"
    "textFontFamily": "system",     # Main text font family (front-end interprets "system")
    "textFontWeight": 400,          # Main text font weight (e.g., 400, 700)
    "listFontFamily": "system",     # List font family
    "listFontWeight": 400,          # List font weight
    "borderRadius": 4,              # Border radius of the container corners in pixels
}

# Version counter for the in-memory state.
# Each time `state` changes, this counter is incremented and pushed over SSE
# so the overlay can re-fetch the latest overlay data.
state_version = 0

""" Router """
@app.route("/")
def index():
    """Serve the control page as the default entry point."""
    return render_template("control.html")

@app.route("/overlay")
def overlay():
    """Serve the overlay page used by OBS as a browser source."""
    return render_template("overlay.html")

@app.route("/control")
def control():
    """Serve the control page for managing overlay settings."""
    return render_template("control.html")

@app.route("/pics/<path:filename>")
def serve_pics(filename):
    """Serve image assets from the `pics` folder."""
    return send_from_directory("pics", filename)

@app.route("/fonts/<path:filename>")
def serve_fonts(filename):
    """Serve font files from the `fonts` folder."""
    return send_from_directory("fonts", filename)

""" API """
@app.route("/api/state", methods=["GET"])
def get_state():
    """
    Return the current in-memory overlay state.
    Used by the control page to initialize form controls from the backend.
    """
    return jsonify(state)

@app.route("/api/state", methods=["POST"])
def update_state():
    """
    Update the in-memory overlay state.
    Expected JSON body (example):
    {
        "fontSize": 48,
        "color": "#ff0000",
        "backgroundOpacity": 0.5,
        ...
    }

    Only keys listed in `allowed_keys` are applied. Other keys are ignored.
    Each successful update increments `state_version` so the overlay can refresh.
    """
    global state_version

    # Force JSON parsing; return an empty dict if the body is missing or invalid
    data = request.get_json(force=True) or {}

    allowed_keys = [
        "text",
        "fontSize",
        "color",
        "backgroundColor",
        "backgroundOpacity",
        "selected_column",
        "containerWidth",
        "containerHeight",
        "scrollSpeed",
        "listFontSize",
        "listColor",
        "textSegmentDuration",
        "groupByColumn",
        "textFontFamily",
        "textFontWeight",
        "listFontFamily",
        "listFontWeight",
        "borderRadius",
    ]

    changed = False

    for key in allowed_keys:
        if key in data:
            if key == "selected_column":
                # When the display column changes, also clear the groupBy column
                # if it would become invalid (same as selected_column)
                if data[key] in columns and data[key] != state.get(key):
                    state[key] = data[key]
                    changed = True
                    if state.get("groupByColumn") == state["selected_column"]:
                        state["groupByColumn"] = ""
            elif key == "groupByColumn":
                # Normalize the grouping specification string
                # Allow values like "", "B", "B+C"
                raw_val = (data[key] or "").strip()
                cols_list = parse_group_spec(raw_val, state.get("selected_column"), columns)
                # If parsing fails or returns an empty list, treat it as "no grouping"
                val = "+".join(cols_list)
                if val != state.get("groupByColumn", ""):
                    state["groupByColumn"] = val
                    changed = True
            else:
                # For all other keys, simply overwrite if the value changed
                if data[key] != state.get(key):
                    state[key] = data[key]
                    changed = True

    if changed:
        # Mark that the state has changed so SSE subscribers (overlay) can refresh
        state_version += 1

    return jsonify({"ok": True, "state": state})


@app.route("/api/columns", methods=["GET"])
def get_columns():
    """Return all column names for populating dropdowns in the control UI."""
    return jsonify({"columns": columns})


@app.route("/api/overlay-data", methods=["GET"])
def overlay_data():
    """
    Build and return the overlay data payload.

    The payload contains:
    - `rows`: prepared text rows for the overlay, possibly grouped.
    - current visual settings (font sizes, colors, container size, etc.).

    The grouping logic:
    - `groupByColumn` is stored as a string, e.g., "", "B", or "B+C".
    - `parse_group_spec()` turns this into a list of group columns.
    - For each group column, `get_grouped_rows()` is called and the rows are
      appended in order. Duplicate group columns are skipped.
    """
    display_col = state["selected_column"]
    group_spec = state.get("groupByColumn", "") or ""

    # Convert a string like "B+C" into ["B", "C"]
    group_cols = parse_group_spec(group_spec, display_col, columns)

    rows = []
    if group_cols:
        used = set()
        for gc in group_cols:
            if gc in used:
                # Skip duplicated group columns to avoid repeated data
                continue
            used.add(gc)
            part = get_grouped_rows(df, display_col, gc)
            rows.extend(part)
    else:
        # No grouping: pass group_col=None
        rows = get_grouped_rows(df, display_col, group_col=None)

    return jsonify({
        "selected_column": display_col,
        "groupByColumn": group_spec,
        "rows": rows,
        "containerWidth": state.get("containerWidth", 600),
        "containerHeight": state.get("containerHeight", 300),
        "scrollSpeed": state.get("scrollSpeed", 30.0),
        "listFontSize": state.get("listFontSize", 24),
        "listColor": state.get("listColor", "#ffffff"),
        "text": state.get("text", ""),
        "fontSize": state.get("fontSize", 36),
        "color": state.get("color", "#ffffff"),
        "backgroundColor": state.get("backgroundColor", "#000000"),
        "backgroundOpacity": state.get("backgroundOpacity", 0.4),
        "textSegmentDuration": state.get("textSegmentDuration", 5.0),
        "textFontFamily": state.get("textFontFamily", "system"),
        "textFontWeight": state.get("textFontWeight", 400),
        "listFontFamily": state.get("listFontFamily", "system"),
        "listFontWeight": state.get("listFontWeight", 400),
        "borderRadius": state.get("borderRadius", 4),
    })

@app.route("/api/stream")
def stream():
    """
    Server-Sent Events endpoint.

    The overlay page connects using `EventSource`:
        const es = new EventSource("/api/stream")

    Whenever `state_version` changes, the server sends a message:
        data: <version_number>

    The front-end can then call `/api/overlay-data` to pull the latest data.
    """
    def event_stream(last_seen_version):
        global state_version
        while True:
            if last_seen_version != state_version:
                last_seen_version = state_version
                # Send a simple version number. The client will fetch /api/overlay-data
                # after receiving this event
                yield f"data: {last_seen_version}\n\n"
            # Sleep a little to avoid busy-waiting and maxing out CPU.
            time.sleep(0.5)

    return Response(event_stream(state_version), mimetype="text/event-stream")

@app.route("/api/presets", methods=["GET"])
def api_list_presets():
    """Return the list of available preset names."""
    return jsonify({"presets": list_presets()})


@app.route("/api/presets", methods=["POST"])
def api_save_preset():
    """
    Save a new preset.

    Expected JSON body:
    {
        "name": "MyPreset",
        "state": { ... current state ... }
    }

    Notes:
    - Name must be non-empty and valid according to `save_preset()`.
    - By default we store the entire state dict.
      If you only want to persist some keys, filter them here.
    """
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    # Accept both "state" and "style" key
    style = data.get("state") or data.get("style")

    if not name:
        return jsonify({"ok": False, "error": "empty_name"}), 400
    if not style:
        return jsonify({"ok": False, "error": "empty_state"}), 400

    try:
        # save all state values
        save_preset(name, style)
    except FileExistsError:
        return jsonify({"ok": False, "error": "exists"}), 400
    except ValueError:
        return jsonify({"ok": False, "error": "invalid_name"}), 400

    return jsonify({"ok": True})


@app.route("/api/presets/<preset_name>", methods=["GET"])
def api_get_preset(preset_name):
    """Load a preset and return its stored state so it can be applied to the UI."""
    preset = load_preset(preset_name)
    if preset is None:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, "state": preset})


@app.route("/api/presets/<preset_name>", methods=["DELETE"])
def api_delete_preset(preset_name):
    """Delete a preset by name."""
    delete_preset(preset_name)
    return jsonify({"ok": True})


if __name__ == "__main__":
    # Find an available port for Flask server
    port = find_free_port(5000)

    # Print startup banner
    print_startup_banner(port=port)

    # Optional background worker thread.
    # If you do not need background tasks for now, keep these lines commented out
    # t = threading.Thread(target=worker, daemon=True)
    # t.start()

    # Run the server on localhost.
    serve(app, host="127.0.0.1", port=port)

    # After running, open:
    # http://127.0.0.1:5000/control or http://127.0.0.1:5000/ to open the control page
    # http://127.0.0.1:5000/overlay to open the overlay page (also use this as the source in OBS)
