from version import __version__, APP_NAME, AUTHOR, HOMEPAGE
import socket

def find_free_port(start_port=5000, max_tries=50):
    """
    Try to find an available TCP port starting from start_port.
    Returns the available port number.
    """
    port = start_port
    for _ in range(max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("Could not find a free port.")


def parse_group_spec(spec: str, selected_col: str, all_columns):
    """
    Parse a grouping specification string into a validated list of column names.

    Input Format:
        spec may be:
            ""       (no grouping)
            "B"      (single grouping column)
            "B+C"    (two grouping columns)
            " C + D " (whitespace is allowed and trimmed)

    Returned Value:
        A list containing up to two **distinct, valid** column names.
        Invalid or disallowed entries are silently skipped.

    Filtering Rules:
        - Empty segments are ignored.
        - Columns not in `all_columns` are discarded.
        - The display column (`selected_col`) is never allowed as a group column.
        - Duplicate columns are removed while preserving order.
        - The list is capped at two elements.

    Args:
        spec (str): User-provided grouping specification.
        selected_col (str): The display column; cannot be used for grouping.
        all_columns (Iterable[str]): Set or list of all allowed column names.

    Returns:
        list[str]: A validated list of grouping columns (0–2 items).
    """
    if not spec:
        return []

    # Split by '+' and trim whitespace, filtering out empty strings
    parts = [p.strip() for p in spec.split("+") if p.strip()]

    result = []
    for p in parts:
        # Exclude invalid or disallowed entries
        if p == selected_col:
            continue
        if p not in all_columns:
            continue
        if p not in result:
            result.append(p)
        # Limit grouping to at most two columns
        if len(result) >= 2:
            break
    return result


ASCII_ART = r"""
╣╢╢╢╢╣╣╢╢╢╢╢Ñ╝╩╣╢╢╣╢╢╢╢╢╢╢╢╢╣╢╢╢╢╢╣╣╣╣╢╢
╣╣╢╢╢╢╢╢╣╣"       ╫╣╢╢╢╢╢╢╢╢╢╢╣╢╢╢╣╢╢╣╢╢
╢╟╢╢╢╢╢▒╣   @▒╢    ╢╢╢╢╣╢╣╢╣╢╢╢╢╣╢╣╢╢╢╢╣
╣╢╢╢╢╢╢▒   ╢╢╢╣@   ]╢╣╢╢╢╣╢╢╢╢╢╢╢╢╢╢╢╢╢╢
╢╢╢╢╢╢╢▒  ║╢╣╣╣▒   ]╢╢╢╣╢╢╢╢╢╢╢╢╢╣╢╣╢╢╢╣
╢╢╢╢╢╢╢Γ  ²ⁿ"`       "╨╬╣╢╢╢╢╢╢╢╣╣╣╣╣╣╣╣
╢╢╢╢╢╢▓  ╒#║▒▒▒▒   ▒▒║╓  └╬╢╢╢╢╢╢╣╢▓╝' "
╢╢╢╢▒╣ ]▒║╢▒▒╨^     ╙▒▒▒▒╗  ╙▓▓▓▓▓▀ .║▒ 
▓▓▓▓▓ ]`  ─└▒        ]▒▒▒▒▒▒╓ `╫▀  ║╜`  
▓▓▓▓▌ ▒.^  ╥▒        ┌▒▒▒▒▒▒▒▒@  @▒▒▒╝▒▒
▓▓▓▓ß ╨╙╜╨▒▒▒         ..'║▒▒▒▒▒▒▒▒▒▒▒╓╓ 
████▓ -ºMh, ╙.         ╓∩ ▒▒▒▒▒▒▒╢▒▒▒r`"
██████. ²╙╙ ,▒%╓──╓@,...╓@▒▒▒▒▒╙ ▄,.`╙╝Ü
███████▄ '▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒╢╙ ▄██████▄,
██████████▄`'╙╨║▒▒▒▒▒▒▒▒Ñ╜"`▄███████████
██████████████▄▄▄▄▄,,,,▄▄███████████████
"""

def print_startup_banner(port=5000):
    """
    Print startup information to console when launching the application.
    """
    print(ASCII_ART)
    print(f"{APP_NAME} v{__version__}")
    print(f"Author: {AUTHOR}")
    print(f"Homepage: {HOMEPAGE}")
    print("============================================")
    print("控制面板地址 (浏览器打开):")
    print(f"  -> http://127.0.0.1:{port}/control")
    print("滚动菜单地址 (浏览器打开，在OBS中使用此地址作为浏览器源):")
    print(f"  -> http://127.0.0.1:{port}/overlay")
    print("注意：右键单击即可复制，请勿使用 Ctrl+C 进行复制！")
    print("")
    print("如何关闭:")
    print("  - 直接关闭本窗口，或者")
    print("  - 在本窗口内使用 Ctrl+C")
    print("")
