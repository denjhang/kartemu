import json, re

js = open('mirror/assets/index-DICvPz5y.js', encoding='utf-8').read()
table = {int(k): v for k, v in json.load(open('string_table.json')).items()}

# 1) 收集所有指向 _0x5f4c 的别名(传递闭包)
alias = {'_0x5f4c'}
changed = True
pat = re.compile(r'(_0x[0-9a-f]+)\s*=\s*(_0x[0-9a-f]+)\b')
while changed:
    changed = False
    for m in pat.finditer(js):
        a, b = m.group(1), m.group(2)
        if b in alias and a not in alias:
            alias.add(a)
            changed = True
print('别名数量:', len(alias))

# 2) 替换所有 ALIAS(0xHEX) 调用为字符串字面量
call_pat = re.compile(r'(_0x[0-9a-f]+)\((0x[0-9a-f]+)\)')

def repl(m):
    if m.group(1) in alias:
        idx = int(m.group(2), 16)
        if idx in table:
            return json.dumps(table[idx], ensure_ascii=False)
    return m.group(0)

out = call_pat.sub(repl, js)
open('deob_full.js', 'w', encoding='utf-8').write(out)
print('还原后大小:', len(out), '剩余未解析调用:', len(call_pat.findall(out)))
