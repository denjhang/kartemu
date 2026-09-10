"""KartRider .rho5 (DataPack) 解包器 — 从 KartSim 反混淆代码移植。

链条:
  文件名(小写)字符和 S → 头偏移/表偏移 (ok)
  头 9 字节: uk 解密(ak 密钥) → checksum==2+fileCount, version=2, fileCount
  文件表: uk 解密(ck 密钥) → 每项 {pathLen u32, path utf16, recordChecksum,
        pipelineFlags, offsetBlocks, decompressedSize, compressedSize, md5[16]}
  载荷起点 = ceil((tableOff+tableSize)/512)*512 + offsetBlocks*0x400
  载荷解密 (lk 密钥, 由 md5+区域密钥+路径派生):
        flags&4 → 前 0x400 字节解密; flags&2 → 全量解密; flags&1 → zlib
  最终 MD5 == 记录 md5
"""
import json, os, re, sys, zlib, hashlib, struct

M32 = 0xFFFFFFFF
RU = {'KR': 'y&errfV6GRS!e8JL', 'CN': 'd$Bjgfc8@dH4TQ?k', 'TW': 't5rHKg-g9BA7%=qD'}


# ---------- AES T-table 变体(nu) ----------
def _mul2(b):
    return ((b << 1) & 0xFF) ^ (0x1B if b & 0x80 else 0)


def _sbox(b):  # wk
    y = b
    for _ in range(0xFE):  # yk(b,0xfe): 乘法链;等价于求逆后仿射,这里直接用标准SBox替代会更快
        pass
    return _AES_SBOX[b]  # 数值上等价(见下注)


# 注:wk(b) 的原始实现是 GF(2^8) 求逆 + 仿射,即标准 AES S-box。
# yk/Cs 即乘法与循环移位。为效率直接内嵌标准 S-box 表:
_AES_SBOX = bytes.fromhex(
    '637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0'
    'b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275'
    '09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cf'
    'd0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2'
    'cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdb'
    'e0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08'
    'ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9e'
    'e1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16')


def _nu():
    T = [None] * 6
    for i in range(6):
        T[i] = [0] * 256
    for b in range(256):
        s = _AES_SBOX[b]                    # wk(b): 先过 S-box
        xt = _mul2(s)                       # su(s,0x1b)
        t0 = ((xt << 24) | ((xt ^ s) << 16) | (s << 8) | s) & M32
        T[0][b] = t0
        T[1][b] = _rotr(t0, 8)
        T[2][b] = _rotr(t0, 16)
        T[3][b] = _rotr(t0, 24)
        T[4][b] = (_Ti(b, 0x10) << 24 | _Ti(b, 0x27) << 16 | _Ti(b, 0x06) << 8 | _Ti(b, 0x40)) & M32
        T[5][b] = (_Ti(b, 0x17) << 24 | _Ti(b, 0xF5) << 16 | _Ti(b, 0x30) << 8 | _Ti(b, 0xEF)) & M32
    return T


def _Ti(b, n):  # 重复 xtime(0xA9) n 次
    for _ in range(n):
        b = ((b << 1) & 0xFF) ^ (0xA9 if b & 0x80 else 0)
    return b


def _rotr(x, n):
    return ((x >> n) | (x << (32 - n))) & M32


_NU = None


def nu():
    global _NU
    if _NU is None:
        _NU = _nu()
    return _NU


# ---------- dk PRNG ----------
def _pc(a, b):
    return (a + b) & M32


def _gk(key, off):  # JS: b<<0x18>>0x18 符号扩展,再 w=(w<<8|sb)>>>0
    w = 0
    for i in range(4):
        b = key[off + i]
        sb = b - 0x100 if b >= 0x80 else b      # 符号扩展到 i32
        sb &= M32                                # i32 的位模式
        w = ((w << 8) | sb) & M32
    return w


def _mk(x):
    return ((x << 8) & M32) ^ nu()[5][x >> 24]


def _pk(x):
    return (x >> 8) ^ nu()[4][x & 0xFF]


def _fk(x):
    T = nu()
    return T[0][x >> 24] ^ T[1][(x >> 16) & 0xFF] ^ T[2][(x >> 8) & 0xFF] ^ T[3][x & 0xFF]


class Dk:
    def __init__(self, key: bytes):
        if len(key) < 16:
            raise ValueError('key too short')
        self.state = [0] * 16
        for k in range(4):
            w = _gk(key, k * 4)
            self.state[15 - k] = w
            self.state[11 - k] = (~w) & M32
            self.state[7 - k] = w
            self.state[3 - k] = (~w) & M32
        self.r1 = 0
        self.r2 = 0
        for _ in range(32):
            self.clock(True)

    def clock(self, warm):
        t = ((_pc(self.r1, self.state[15]) ^ self.r2) & M32) if warm else 0
        a = (_mk(self.state[0]) ^ self.state[2] ^ _pk(self.state[11]) ^ t) & M32
        b = _pc(self.r2, self.state[5])
        c = _fk(self.r1)
        self.state = self.state[1:] + [a]
        self.r1 = b
        self.r2 = c
        return (_pc(b, a) ^ c ^ self.state[0]) & M32

    def next_word(self):
        return self.clock(False)


def uk(data: bytes, key: bytes) -> bytes:
    d = Dk(key)
    out = bytearray(len(data))
    for i in range(0, len(data), 4):
        n = min(4, len(data) - i)
        w = int.from_bytes(data[i:i+n], 'little')
        dec = (w - d.next_word()) & M32
        out[i:i+n] = dec.to_bytes(4, 'little')[:n]
    return bytes(out)


def jo(data, key):
    return uk(data, key)


# ---------- 密钥派生 ----------
def ak(name: str, region_key: str) -> bytes:
    seed = name.lower() + region_key
    return bytes(((ord(seed[i % len(seed)]) & 0xFF) + i) & 0xFF for i in range(0x80))


def ck(name: str, region_key: str) -> bytes:
    seed = name.lower() + region_key
    out = bytearray(0x80)
    for i in range(0x80):
        j = i % len(seed)
        c = (ord(seed[len(seed) - j - 1]) & 0xFF) * (2 + i % 3) + i
        out[i] = c & 0xFF
    return bytes(out)


def hk(s: str) -> int:  # FNV-1a
    h = 0x811C9DC5
    for ch in s:
        h = ((((h ^ ord(ch)) & M32) * 0x01000193) & M32)
    return h


def lk(md5: bytes, region_key: str, path: str) -> bytes:
    digits = [ord(c) - 0x30 for c in str(hk(region_key))]
    out = bytearray(0x80)
    for i in range(0x80):
        bit = digits[i % len(digits)] & 1
        d1 = digits[(i + 1) % len(digits)]
        d2 = (digits[(i + 2) % len(digits)] + i) & 0xF
        v = ((d1 + i) % 5 + md5[d2] + bit) & 0xFF
        p = ord(path[i % len(path)]) & 0xFF
        out[i] = (v * p + i) & 0xFF
    return bytes(out)


# ---------- 容器 ----------
def ok(name_lower: str):
    s = sum(ord(c) for c in name_lower)
    header = s % 0x138 + 0x1E
    file_table = header + s * 3 % 0xD4 + 0x2A
    return header, file_table


def read_header(raw: bytes, name: str, region='CN'):
    name_l = name.lower()
    h_off, t_off = ok(name_l)
    head = uk(raw[h_off:h_off + 9], ak(name_l, RU[region]))
    checksum = int.from_bytes(head[0:4], 'little')
    version = head[4]
    file_count = int.from_bytes(head[5:9], 'little')
    assert version == 2, f'{name}: 版本 {version}'
    assert checksum == (version + file_count) & M32, f'{name}: 头校验失败'
    return file_count, t_off


def read_table(raw: bytes, name: str, region='CN'):
    name_l = name.lower()
    file_count, t_off = read_header(raw, name, region)
    size = min(len(raw) - t_off, max(0x40 * 0x400, file_count * 0xC0 + 0x400))
    while True:
        table = uk(raw[t_off:t_off + size], ck(name_l, RU[region]))
        try:
            entries, pos = parse_table(table, file_count)
            break
        except IndexError:
            size = min(size * 2, len(raw) - t_off)
            continue
    data_begin = ((t_off + pos + 0x3FF) // 0x400) * 0x400
    for e in entries:
        e['payloadStart'] = data_begin + e['offsetBlocks'] * 0x400
    return entries


def parse_table(table: bytes, file_count: int):
    entries = []
    pos = 0
    for _ in range(file_count):
        path_len = int.from_bytes(table[pos:pos+4], 'little'); pos += 4
        path = table[pos:pos+path_len*2].decode('utf-16-le'); pos += path_len * 2
        checksum = int.from_bytes(table[pos:pos+4], 'little'); pos += 4
        flags = int.from_bytes(table[pos:pos+4], 'little'); pos += 4
        offset_blocks = int.from_bytes(table[pos:pos+4], 'little'); pos += 4
        decompressed = int.from_bytes(table[pos:pos+4], 'little'); pos += 4
        compressed = int.from_bytes(table[pos:pos+4], 'little'); pos += 4
        md5 = table[pos:pos+16]; pos += 16
        entries.append(dict(path=path, recordChecksum=checksum, pipelineFlags=flags,
                            offsetBlocks=offset_blocks, compressedSize=compressed,
                            decompressedSize=decompressed, md5=md5))
    return entries, pos


def extract_payload(raw: bytes, e: dict, region='CN') -> bytes:
    data = raw[e['payloadStart']:e['payloadStart'] + e['compressedSize']]
    key = lk(e['md5'], RU[region], e['path'])
    flags = e['pipelineFlags']
    if flags & 4:
        n = min(0x400, len(data))
        data = jo(data[:n], key) + data[n:]
    if flags & 2:
        data = jo(data, key)
    if flags & 1:
        data = zlib.decompress(data)
    assert len(data) == e['decompressedSize'], f"{e['path']}: {len(data)} != {e['decompressedSize']}"
    assert hashlib.md5(data).digest() == e['md5'], f"{e['path']}: MD5 不匹配"
    return data


def extract_part(part_file: str, out_dir: str, prefix_filter=None, region='CN') -> int:
    raw = open(os.path.join('mirror/p3528', part_file), 'rb').read()
    entries = read_table(raw, part_file, region)
    n = 0
    for e in entries:
        if prefix_filter and not e['path'].startswith(prefix_filter):
            continue
        try:
            data = extract_payload(raw, e, region)
        except Exception as ex:
            print('  [失败]', e['path'], ex)
            continue
        path = os.path.join(out_dir, e['path'].replace('/', os.sep))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').write(data)
        n += 1
    return n


if __name__ == '__main__':
    part = sys.argv[1] if len(sys.argv) > 1 else 'DataPack2_00000.rho5'
    filt = sys.argv[2] if len(sys.argv) > 2 else None
    out = os.path.join('unpacked', part.replace('.rho5', ''))
    os.makedirs(out, exist_ok=True)
    n = extract_part(part, out, filt)
    print(f'{part}: 解出 {n} 个文件 -> {out}')
