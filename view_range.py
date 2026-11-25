# 读取 data 文件夹里某个 parquet 文件的第 A 组到第 B 组数据，生成一个网页（单个 .html 文件，图片直接嵌在里面）
# 用法一：双击本文件，按提示输入
# 用法二：cmd 里运行   py view_range.py 文件编号 起始 结束     例如   py view_range.py 5 100 149
import sys, os, html, base64, traceback, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT_DIR = os.path.join(HERE, "views")


def ask(prompt, default):
    s = input(f"{prompt}（直接回车 = {default}）：").strip()
    return s if s else str(default)


def find_file(arg):
    names = sorted(f for f in os.listdir(DATA) if f.endswith(".parquet"))
    if arg.isdigit():
        hit = [n for n in names if n.startswith(f"train-{int(arg):05d}-")]
        if hit:
            return os.path.join(DATA, hit[0])
    elif arg in names:
        return os.path.join(DATA, arg)
    raise ValueError(f"找不到文件 {arg}。data 里共有 {len(names)} 个 parquet 文件，编号 0 到 {len(names) - 1}。")


def read_rows(pf, start, end):
    """只读取包含 start..end（含两端，从 0 开始）的那几个 row group，不会把整个文件读进内存"""
    rows, offset = [], 0
    for g in range(pf.num_row_groups):
        n = pf.metadata.row_group(g).num_rows
        if offset + n > start and offset <= end:
            part = pf.read_row_group(g).to_pylist()
            lo, hi = max(start - offset, 0), min(end - offset, n - 1)
            rows.extend(part[lo:hi + 1])
        offset += n
        if offset > end:
            break
    return rows


def is_image(v):
    return isinstance(v, dict) and "bytes" in v


def img_tag(cell, label):
    data = cell.get("bytes")
    if not data:
        return f"<figure><div class='noimg'>（无图片）</div><figcaption>{label}</figcaption></figure>"
    if data[:4] == b"\x89PNG":
        mime = "image/png"
    elif data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        mime = "image/jpeg"
    b64 = base64.b64encode(data).decode("ascii")
    return f"<figure><img src='data:{mime};base64,{b64}'><figcaption>{label}</figcaption></figure>"


def card(idx, r):
    imgs = "".join(img_tag(v, html.escape(k)) for k, v in r.items() if is_image(v))
    texts = "".join(f"<p><b>{html.escape(k)}:</b> {html.escape(str(v))}</p>"
                    for k, v in r.items() if not is_image(v))
    return f"<div class='card'><div class='idx'>第 {idx} 组</div><div class='imgs'>{imgs}</div>{texts}</div>"


CSS = """body{font-family:sans-serif;background:#f4f4f4;margin:20px}
.card{background:#fff;border-radius:8px;padding:14px;margin-bottom:18px;box-shadow:0 1px 3px #0002}
.idx{font-weight:bold;color:#c33;margin-bottom:8px}.imgs{display:flex;gap:12px;flex-wrap:wrap}
figure{margin:0}img{max-width:480px;max-height:400px;border-radius:4px}
figcaption{font-size:12px;color:#666;text-align:center}.noimg{width:200px;height:120px;background:#eee}
p{margin:6px 0;line-height:1.5;word-break:break-word}"""


def main():
    try:
        import pyarrow.parquet as pq
    except ImportError:
        print("[错误] 当前 Python 没有安装 pyarrow，请在 cmd 里运行：")
        print(f'  "{sys.executable}" -m pip install pyarrow')
        return

    print("使用的 Python：", sys.executable)
    args = sys.argv[1:]
    if len(args) >= 3:
        f_arg, s_arg, e_arg = args[:3]
    else:
        print("data 文件夹：", DATA)
        f_arg = ask("要看哪个文件？输入编号 0~90 或完整文件名", 0)
        s_arg = ask("从第几组开始？（编号从 0 开始）", 0)
        e_arg = ask("到第几组结束？（包含这一组）", int(s_arg) + 49)

    path = find_file(f_arg.strip())
    pf = pq.ParquetFile(path)
    total = pf.metadata.num_rows
    start, end = sorted((int(s_arg), int(e_arg)))
    if start < 0 or start >= total:
        raise ValueError(f"起始编号超出范围：这个文件只有第 0 到第 {total - 1} 组。")
    end = min(end, total - 1)
    if end - start + 1 > 300:
        print("提示：一次超过 300 组，网页会很大，打开可能比较慢。")

    name = os.path.splitext(os.path.basename(path))[0]
    print(f"正在读取 {name}（共 {total} 组）的第 {start} 到第 {end} 组 ...")
    rows = read_rows(pf, start, end)

    body = "".join(card(start + i, r) for i, r in enumerate(rows))
    title = f"{name} 第 {start}-{end} 组"
    page = (f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>"
            f"<style>{CSS}</style></head><body><h2>{title}（本文件共 {total} 组）</h2>{body}</body></html>")

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{name}_{start}-{end}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"\n完成！共 {len(rows)} 组，网页已保存到：\n  {out}")
    webbrowser.open("file:///" + out.replace("\\", "/"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("\n[出错了] 请把下面的报错全部复制发给我：\n")
        traceback.print_exc()
    input("\n按回车键关闭窗口 ...")
