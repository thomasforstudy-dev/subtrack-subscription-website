"""Start SubTrack with waitress, a real web server for the public site.

The Flask dev server (run_local.bat) is only for testing on this PC; it must
never be put on the internet. Cloudflare Tunnel forwards the domain to here.
"""

from waitress import serve

from app import create_app

if __name__ == "__main__":
    # 127.0.0.1 = only this PC can reach it directly; visitors come in
    # through Cloudflare Tunnel.
    serve(create_app(), host="127.0.0.1", port=8000, threads=8)
