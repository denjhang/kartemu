"""web/ 本地开发服务器(端口 8000)
- ThreadingHTTPServer: 多请求并发,避免多标签页同时加载时 ERR_ABORTED
- no-cache 头: 浏览器始终取最新文件,避免改代码后看到旧缓存
"""
import os
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

PORT = 8000
ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # 安静模式,不刷日志


if __name__ == "__main__":
    if len(sys.argv) > 1:
        PORT = int(sys.argv[1])
    print(f"web 开发服务器: http://127.0.0.1:{PORT}/  (根目录: {ROOT})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
