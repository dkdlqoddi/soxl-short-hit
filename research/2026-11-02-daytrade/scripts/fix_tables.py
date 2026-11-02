"""Repair markdown tables whose sell-rule cells contain " | " (OR notation): merges the split cells with " ∣ ".
Usage: python3 fix_tables.py <markdown file>
"""
import sys


def fix_tables(path):
    lines = open(path, encoding="utf-8").read().split("\n")
    out, header, target = [], None, None
    for ln in lines:
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if header is None:
                header, target = cells, len(cells) - 1
                for key in ["매도", "매도 규칙", "조건", "최고 조합", "답"]:
                    if key in cells:
                        target = cells.index(key)
                        break
                out.append(ln)
                continue
            if all(set(c) <= set("-: ") for c in cells):
                out.append(ln)
                continue
            k = len(cells) - len(header)
            if k > 0:
                cells = cells[:target] + [" ∣ ".join(cells[target:target + k + 1])] + cells[target + k + 1:]
            out.append("| " + " | ".join(cells) + " |")
        else:
            header = None
            out.append(ln)
    open(path, "w", encoding="utf-8").write("\n".join(out))


if __name__ == "__main__":
    fix_tables(sys.argv[1])
