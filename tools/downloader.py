import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import urllib.request

BASE = "https://kart-assets.iii.moe/p3528/"
OUT = r"D:\working\vscode-projects\kartemu\mirror\p3528"

d = json.load(open(r"D:\working\vscode-projects\kartemu\resources.bin", encoding="utf-8"))
files = {f["name"]: f["size"] for f in d["files"]}

done, skipped = 0, 0
lock_held = False

def fetch(name, size):
    path = os.path.join(OUT, name)
    if os.path.exists(path) and os.path.getsize(path) == size:
        return ("skip", name)
    req = urllib.request.Request(BASE + name, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) != size:
                raise IOError(f"size mismatch {len(data)} != {size}")
            tmp = path + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
            return ("ok", name)
        except Exception as e:
            if attempt == 3:
                return ("fail", f"{name}: {e}")
            time.sleep(2 * (attempt + 1))

os.makedirs(OUT, exist_ok=True)
t0 = time.time()
with ThreadPoolExecutor(max_workers=16) as ex:
    futs = [ex.submit(fetch, n, s) for n, s in files.items()]
    for i, fut in enumerate(futs, 1):
        status, name = fut.result()
        if status == "skip":
            skipped += 1
        elif status == "ok":
            done += 1
        else:
            print("FAIL", name, flush=True)
        if i % 50 == 0:
            print(f"[{i}/{len(files)}] ok={done} skip={skipped} elapsed={time.time()-t0:.0f}s", flush=True)

print(f"DONE ok={done} skip={skipped} total={len(files)} in {time.time()-t0:.0f}s", flush=True)
# 校验
missing = [n for n, s in files.items()
           if not (os.path.exists(os.path.join(OUT, n)) and os.path.getsize(os.path.join(OUT, n)) == s)]
print("MISSING:", len(missing), flush=True)
for n in missing[:20]:
    print(" -", n, flush=True)
