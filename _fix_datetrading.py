import re, io, sys

files = [
    "학습노트/13_스윙매매_정독.md",
    "학습노트/HANDOVER_가이드북_트랙정독.md",
    "학습노트/90_사례대장.md",
    "학습노트/91_개념인덱스.md",
]
pat = re.compile(r"데이트(?!레이딩)")
for f in files:
    with io.open(f, encoding="utf-8") as fh:
        s = fh.read()
    n = len(pat.findall(s))
    if n == 0:
        print("[0] %s (변경 없음)" % f)
        continue
    s2 = pat.sub("데이트레이딩", s)
    left = len(pat.findall(s2))
    if left != 0:
        print("!! %s: 잔여 %d — 중단" % (f, left)); sys.exit(1)
    with io.open(f, "w", encoding="utf-8") as fh:
        fh.write(s2)
    print("[%d 교정] %s" % (n, f))
print("RESULT: OK")
