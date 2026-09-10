"""KartSim 本地镜像服务器
路由:
  /                          -> mirror/index.html(已补丁)
  /assets/*                  -> mirror/assets/*
  /manifest.webmanifest      -> mirror/manifest.webmanifest
  /__p3528/resources         -> resources.bin(资源清单)
  /__p3528/archive-index     -> archive-index.bin(zlib 压缩索引)
  /p3528/<name>              -> mirror/p3528/<name>(全部 .rho/.rho5/.pk 资源包)
"""
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mirror")

MAPPING = {
    "/__p3528/resources": os.path.join(ROOT, "..", "resources.bin"),
    "/__p3528/archive-index": os.path.join(ROOT, "..", "archive-index.bin"),
    "/manifest.webmanifest": os.path.join(ROOT, "manifest.webmanifest"),
}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def translate_path(self, path):
        path = path.split("?", 1)[0].split("#", 1)[0]
        if path in MAPPING:
            real = os.path.normpath(MAPPING[path])
        elif path.startswith("/web/"):
            real = os.path.normpath(os.path.join(ROOT, "..", path.lstrip("/")))
        elif path.startswith("/p3528/"):
            name = os.path.normpath(path[len("/p3528/"):]).lstrip("\\/")
            if ".." in name:
                return os.path.join(ROOT, "404")
            real = os.path.join(ROOT, "p3528", name)
        else:
            real = super().translate_path(path)
        # aria2 仍在下载的文件(存在 .aria2 控制文件)按 404 处理,避免游戏读到半截数据
        if os.path.exists(real + ".aria2"):
            return os.path.join(ROOT, "404")
        return real

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass

    def send_error(self, code, *a, **kw):
        if code == 404 and self.path.startswith("/p3528/"):
            with open(os.path.join(ROOT, "404.log"), "a", encoding="utf-8") as f:
                f.write(self.path[len("/p3528/"):].split("?")[0] + "\n")
        return super().send_error(code, *a, **kw)


if __name__ == "__main__":
    port = 8088
    print(f"KartSim 本地镜像: http://127.0.0.1:{port}/")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
