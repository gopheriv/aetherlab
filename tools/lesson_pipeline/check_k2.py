
if __package__:
    from ._console import configure_utf8_stdio
else:
    from _console import configure_utf8_stdio

configure_utf8_stdio()

import json

d = json.load(open('output/stage_k2_fragments/durations.json', encoding='utf-8'))['durations']
f = json.load(open('output/stage_k2_fragments/fragments.json', encoding='utf-8'))
t = json.load(open('output/stage_k_voice/timing.json', encoding='utf-8'))['fragments']
print('block sums K2 vs Stage-K whole clip:')
for b in ['B0', 'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7']:
    row = []
    for lang in ('ru', 'kk', 'en'):
        s = sum(d[fid][lang] for fid in d if f[fid]['block'] == b)
        w = t[f'{b}_{lang}']['seconds']
        row.append(f'{lang}:{s:.2f}/{w:.2f}')
    print(f'{b}: ' + ' '.join(row))
print()
print('B6 fragments ru:')
for fid in sorted(d):
    if f[fid]['block'] == 'B6':
        print(' ', fid, f[fid]['shot'], d[fid]['ru'])
print()
print('per-fragment durations (shot: ru/kk/en):')
for fid in sorted(d):
    print(f"  {fid} {f[fid]['shot']}: {d[fid]['ru']:5.2f} {d[fid]['kk']:5.2f} {d[fid]['en']:5.2f}")
