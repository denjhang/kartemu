import re, sys, json

src = open('deob_full.js', encoding='utf-8').read()

def extract(name):
    # find "function NAME(" or "NAME=function" or "async function NAME("
    for pat in (r'function\s+' + re.escape(name) + r'\s*\(',
                re.escape(name) + r'\s*=\s*(async\s+)?function\s*\(',
                r'(async\s+function\s+' + re.escape(name) + r'\s*\()'):
        m = re.search(pat, src)
        if m: break
    else:
        return None
    # skip parameter list (balanced parens) to find the body brace
    p = src.index('(', m.end()-1)
    depth = 0; k = p
    instr = None
    while k < len(src):
        c = src[k]
        if instr:
            if c == '\\': k += 2; continue
            if c == instr: instr = None
        else:
            if c in '"\'`': instr = c
            elif c == '(': depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0: break
        k += 1
    i = src.index('{', k)
    # brace matching, string-aware
    depth = 0; j = i; instr = None; prev=''
    while j < len(src):
        c = src[j]
        if instr:
            if c == '\\': j += 2; continue
            if c == instr: instr = None
        else:
            if c in '"\'`': instr = c
            elif c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0: break
        j += 1
    return src[m.start():j+1]

def extract_class(name):
    m = re.search(r'class\s+' + re.escape(name) + r'\b', src)
    if not m: return None
    i = src.index('{', m.end())
    depth=0; j=i; instr=None
    while j < len(src):
        c=src[j]
        if instr:
            if c=='\\': j+=2; continue
            if c==instr: instr=None
        else:
            if c in '"\'`': instr=c
            elif c=='{': depth+=1
            elif c=='}':
                depth-=1
                if depth==0: break
        j+=1
    return src[m.start():j+1]

if __name__ == '__main__':
    out = []
    for name in sys.argv[1:]:
        t = extract(name) or extract_class(name)
        if t is None:
            out.append(f'//// {name}: NOT FOUND')
        else:
            out.append(f'//// {name} @ {src.index(t[:60])}\n{t}')
    print('\n\n'.join(out))
