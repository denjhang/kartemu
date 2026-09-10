import re

js = open('deob_full.js', encoding='utf-8').read()


def extract_fn(fn):
    i = js.find('function ' + fn + '(')
    if i < 0:
        return None
    depth = 0
    j = i
    started = False
    while j < len(js):
        c = js[j]
        if c == '{':
            depth += 1
            started = True
        elif c == '}':
            depth -= 1
            if started and depth == 0:
                break
        j += 1
    return js[i:j + 1]


def extract_class(fn):
    i = js.find('class ' + fn)
    if i < 0:
        return None
    depth = 0
    j = i
    started = False
    while j < len(js):
        c = js[j]
        if c == '{':
            depth += 1
            started = True
        elif c == '}':
            depth -= 1
            if started and depth == 0:
                break
        j += 1
    return js[i:j + 1]


parts = []
for fn in ['yk', 'Cs', 'wk', 'su', 'wc', 'Ti', 'nu', 'gk', 'mk', 'pk', 'fk', 'pc',
           'ok', 'ak', 'ck', 'hk', 'lk', 'jo', 'uk']:
    s = extract_fn(fn)
    if s is None:
        print(fn, 'NOT FOUND')
        continue
    parts.append(s)
for cls in ['dk', 'Nk']:
    s = extract_class(cls)
    if s is None:
        print(cls, 'NOT FOUND')
        continue
    # 统一类名大小写引用
    s = s.replace('new ' + cls, 'new ' + cls.capitalize())
    parts.append(s)

kit = '\n'.join(parts)
kit = kit.replace('new Dk', 'new Dk')
kit += '''
const RU = { KR: 'y&errfV6GRS!e8JL', CN: 'd$Bjgfc8@dH4TQ?k', TW: 't5rHKg-g9BA7%=qD' };
const fs = require('fs');
const name = 'DataPack2_00007.rho5';
const raw = fs.readFileSync('mirror/p3528/' + name);
const offs = ok(name.toLowerCase());
console.log('ok offsets:', JSON.stringify(offs));
const key = ak(name.toLowerCase(), RU.CN);
console.log('ak key[0:16]:', Buffer.from(key.slice(0, 16)).toString('hex'));
const head = uk(raw.subarray(offs.header, offs.header + 9), key);
console.log('head hex:', Buffer.from(head).toString('hex'));
const ckKey = ck(name.toLowerCase(), RU.CN);
const tsize = Math.min(raw.length - offs.fileTable, Math.max(0x40 * 0x400, 100 * 0xC0 + 0x400));
const tbl = uk(raw.subarray(offs.fileTable, offs.fileTable + tsize), ckKey);
console.log('table[0:64]:', Buffer.from(tbl.subarray(0, 64)).toString('hex'));
'''
open('rho5kit.js', 'w', encoding='utf-8').write(kit)
print('kit 大小:', len(kit))
