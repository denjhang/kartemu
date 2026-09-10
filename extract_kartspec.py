import re

js = open('mirror/assets/LocalTimeAttackParameters-CnGQYfTA.js', encoding='utf-8').read()
h = re.search(r'id,speedType,source[a-zA-Z,]*', js)
header = h.group(0)
rows = re.findall(r'\d{1,5},[47],cn3229\+local-p3528,[^\\]*', js)
print('字段数:', len(header.split(',')), ' 数据行数:', len(rows))
if rows:
    print('首行字段数:', len(rows[0].rstrip(',').split(',')))
    ids = sorted(set(int(r.split(',')[0]) for r in rows))
    print('车辆数:', len(ids), ' id范围:', ids[0], '-', ids[-1])
    s4 = sum(1 for r in rows if r.split(',')[1] == '4')
    print('速度4:', s4, ' 速度7:', len(rows) - s4)
with open('kartspec.csv', 'w') as f:
    f.write(header + '\n')
    for r in rows:
        f.write(r.rstrip(',').replace('\\x0a', '') + '\n')
print('导出完成 -> kartspec.csv')
