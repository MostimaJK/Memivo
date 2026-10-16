"""Run Spectrum in the system WebView, or use --browser for development."""
import argparse
import os
import threading
import webbrowser
from pathlib import Path

from desktop.server import create_server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    server = create_server(port=args.port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if args.browser:
            print(server.url, flush=True)
            webbrowser.open(server.url)
            threading.Event().wait()
        else:
            if os.name == 'nt':
                import ctypes
                # Give the taskbar its own application identity rather than Python's group.
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Memivo.Desktop')
            import webview
            window = webview.create_window(server.app.window_title, server.url,
                                          width=1480, height=960, min_size=(1040, 700))
            server.app.window = window
            window.events.shown += lambda: print('MEMIVO_WINDOW_READY',flush=True)
            if os.name == 'nt':
                from desktop.window import center_windows_window
                window.events.before_show += center_windows_window
            def on_closing():
                if server.app.task['state'] == 'running':
                    server.app.cancel.set()
                    # First close asks the active worker to stop; close again when done.
                    return False
            window.events.closing += on_closing
            icon = Path(__file__).resolve().parent / 'frontend/public/memivo.ico'
            webview.start(gui='edgechromium' if os.name == 'nt' else None, icon=str(icon))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
