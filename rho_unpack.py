"""KartRider .rho 解包器(独立于源包,直接产出明文文件)

格式要点(逆向自 KartSim):
  - 每个文件的数据 = 块表[dataIndex] 指向的块(可能带续块 dataIndex+1)
  - processingFlags: bit0=有Adler32校验, bit2=zlib压缩, bit4=数据密钥XOR加密, bit8=未知(不支持)
  - 解密密钥流: 64字节 = 16个uint32LE, seed = dataKey ^ 0x8473fbc1, 逐个 - 0x7b8c043f (mod 2^32)
  - 校验: Adler-32 == block.checksum
  - 块表/文件表(路径/dataIndex/dataKey)直接取自 archive-index.json
"""
import json, os, sys, zlib, struct

IDX = json.load(open('archive-index.json', encoding='utf-8'))
SRC = 'mirror/p3528'

M32 = 0xFFFFFFFF


def keystream64(data_key: int) -> bytes:
    seed = (data_key ^ 0x8473FBC1) & M32
    words = []
    for _ in range(16):
        words.append(seed)
        seed = (seed - 0x7B8C043F) & M32
    return struct.pack('<16I', *words)


def adler32(b: bytes) -> int:
    # 注意:KartSim 的 rn() 初始 a=0(标准 Adler-32 初始 a=1)
    a, s = 0, 0
    for x in b:
        a = (a + x) % 0xFFF1
        s = (s + a) % 0xFFF1
    return ((s << 16) | a) & M32


def xor64(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % 64] for i, b in enumerate(data))


def read_block(raw: bytes, blocks: dict, data_index: int, data_key: int, name: str) -> bytes:
    blk = blocks.get(data_index)
    if blk is None:
        raise KeyError(f'{name}: 缺少数据块 {data_index}')
    data = raw[blk['offset']:blk['offset'] + blk['storedSize']]
    flags = blk['processingFlags']
    if flags & 8:
        raise ValueError(f'{name}: 遇到不支持的 flag 0x08 (块 {data_index})')
    if flags & 2:
        data = zlib.decompress(data)
    if flags & 4:
        data = xor64(data, keystream64(data_key))
    if len(data) != blk['logicalSize']:
        raise ValueError(f'{name}: 块 {data_index} 长度不匹配 {len(data)} != {blk["logicalSize"]}')
    if flags & 1 and adler32(data) != blk['checksum']:
        raise ValueError(f'{name}: 块 {data_index} Adler32 校验失败')
    return data


def extract(rho_name: str, out_dir: str, only_ext=None, only_path=None) -> int:
    ent = next(r for r in IDX['rho'] if r['name'] == rho_name)
    raw = open(os.path.join(SRC, rho_name), 'rb').read()
    blocks = {b['index']: b for b in ent['blocks']}
    n = 0
    for f in ent['files']:
        if only_ext and not f['path'].lower().endswith(only_ext):
            continue
        if only_path and only_path not in f['path']:
            continue
        data = bytearray()
        di = f['dataIndex'] & M32
        # 主块
        blk = blocks[di]
        if blk['processingFlags'] == 4:
            # HC 路径:先按 dataKey 解密,可能跟明文续块
            part = read_block(raw, blocks, di, f['dataKey'], rho_name)
            data += part
            if f['size'] > len(data):
                nb = blocks.get((di + 1) & M32)
                if nb and nb['processingFlags'] == 0:
                    data += raw[nb['offset']:nb['offset'] + nb['storedSize']]
        else:
            # jw 路径:必要时用续块拼接(先解主块)
            data += read_block(raw, blocks, di, f['dataKey'], rho_name)
            while len(data) < f['size']:
                di = (di + 1) & M32
                nb = blocks.get(di)
                if nb is None:
                    break
                data += read_block(raw, blocks, di, 0, rho_name) if nb['processingFlags'] & 4 == 0 else read_block(raw, blocks, di, f['dataKey'], rho_name)
        if len(data) != f['size']:
            print(f'  [警告] {f["path"]}: 解出 {len(data)} != 标称 {f["size"]}')
        path = os.path.join(out_dir, f['path'].replace('/', os.sep))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').write(data)
        n += 1
    return n


if __name__ == '__main__':
    rho = sys.argv[1] if len(sys.argv) > 1 else 'boss.rho'
    out = os.path.join('unpacked', rho.replace('.rho', ''))
    os.makedirs(out, exist_ok=True)
    n = extract(rho, out)
    print(f'{rho}: 解出 {n} 个文件 -> {out}')
