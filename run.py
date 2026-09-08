"""Launch the PrintFlow visual simulation locally. Python 3.10+; no pip install."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import webbrowser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent / "dist"
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    SimpleHTTPRequestHandler.extensions_map.update({".wasm":"application/wasm", ".py":"text/plain; charset=utf-8"})
    url = f"http://127.0.0.1:{args.port}"
    try:
        with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
            print(f"PrintFlow is running at {url}\nPress Ctrl+C to stop.")
            if not args.no_browser:
                webbrowser.open(url)
            server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
