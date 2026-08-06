"""管理 Windows 任务计划中的每日行情同步任务（基于系统自带 schtasks）。

用法（在项目根目录）：
    .venv\\Scripts\\python.exe scripts\\manage_sync_task.py add                # 注册：每周一~五 17:35 自动同步
    .venv\\Scripts\\python.exe scripts\\manage_sync_task.py add --time 17:40   # 自定义执行时间
    .venv\\Scripts\\python.exe scripts\\manage_sync_task.py add --days MON,WED,FRI
    .venv\\Scripts\\python.exe scripts\\manage_sync_task.py add --name my_task # 自定义任务名
    .venv\\Scripts\\python.exe scripts\\manage_sync_task.py query              # 查询任务状态
    .venv\\Scripts\\python.exe scripts\\manage_sync_task.py delete             # 删除任务

说明：
    - 任务以当前登录用户身份运行，无需管理员权限；若电脑锁屏/未登录则不会执行。
    - 真正执行的是 scripts\\sync_daily.py（幂等，可重复跑）。
"""
import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASK_NAME = "fund_daily_sync"
DEFAULT_TIME = "17:35"
DEFAULT_DAYS = "MON,TUE,WED,THU,FRI"


def _python_exe() -> Path:
    p = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    return p if p.exists() else Path(sys.executable)


def _decode(b: bytes) -> str:
    """schtasks 输出用系统代码页（中文 Windows 为 GBK），做兼容解码。"""
    for enc in ("utf-8", "gbk"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def _run(cmd: list[str]) -> int:
    print(">", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, shell=False)
    out = _decode(r.stdout).strip()
    err = _decode(r.stderr).strip()
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return r.returncode


def add_task(name: str, time_str: str, days: str) -> None:
    python = _python_exe()
    script = PROJECT_ROOT / "scripts" / "sync_daily.py"
    # /tr 的整体值 = "python.exe" "脚本路径"（作为单个参数传给 schtasks）
    tr = f'"{python}" "{script}"'
    cmd = [
        "schtasks", "/create", "/tn", name,
        "/tr", tr,
        "/sc", "weekly", "/d", days,
        "/st", time_str, "/f",
    ]
    code = _run(cmd)
    if code == 0:
        print(f"\n✅ 已注册任务「{name}」：每周 {days} {time_str} 自动同步行情。")
        print("   执行命令为：", tr)
        print("   可用 query 查看状态，delete 删除。")
    else:
        print(f"\n❌ 注册失败（退出码 {code}）。可尝试以管理员身份运行。")


def delete_task(name: str) -> None:
    code = _run(["schtasks", "/delete", "/tn", name, "/f"])
    if code == 0:
        print(f"\n✅ 已删除任务「{name}」。")
    else:
        print(f"\n❌ 删除失败（退出码 {code}）：任务可能不存在，或需要管理员权限。")


def query_task(name: str) -> None:
    code = _run(["schtasks", "/query", "/tn", name, "/v", "/fo", "LIST"])
    if code != 0:
        print(f"\n未找到任务「{name}」，可用 add 注册。")
    sys.exit(code)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="管理 Windows 每日行情同步任务计划（schtasks 封装）"
    )
    parser.add_argument(
        "action", choices=["add", "delete", "query"],
        help="add=注册任务 / delete=删除任务 / query=查询状态",
    )
    parser.add_argument(
        "--name", default=DEFAULT_TASK_NAME,
        help=f"任务名（默认 {DEFAULT_TASK_NAME}）",
    )
    parser.add_argument(
        "--time", default=DEFAULT_TIME,
        help=f"执行时间 HH:MM（默认 {DEFAULT_TIME}）",
    )
    parser.add_argument(
        "--days", default=DEFAULT_DAYS,
        help=f"每周哪几天（默认 {DEFAULT_DAYS}，如 MON,TUE,WED,THU,FRI）",
    )
    args = parser.parse_args()

    if args.action == "add":
        add_task(args.name, args.time, args.days)
    elif args.action == "delete":
        delete_task(args.name)
    else:
        query_task(args.name)



if __name__ == "__main__":

    """
    """
    main()
