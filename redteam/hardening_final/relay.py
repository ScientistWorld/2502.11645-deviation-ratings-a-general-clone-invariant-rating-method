"""Job log relay: forwards stdin to stdout and, after 120 s of silence, prints the
state of the job's bash/python processes (R running, S sleeping, D uninterruptible
I/O; plus the kernel wait channel). Used by scripts/run.sh to diagnose stalls.
It only reads a pipe and writes the job log; it touches no files.
"""
import os
import select
import sys
import time


def states():
    out = []
    for entry in sorted(os.listdir("/proc"), key=lambda e: (len(e), e)):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as handle:
                cmd = handle.read().replace(b"\0", b" ").decode(errors="replace").strip()
            if "python" not in cmd and "bash" not in cmd:
                continue
            with open(f"/proc/{entry}/stat") as handle:
                state = handle.read().rsplit(")", 1)[-1].split()[0]
            with open(f"/proc/{entry}/wchan") as handle:
                wchan = handle.read().strip() or "-"
        except OSError:
            continue
        out.append(f"{entry}:{state}:{wchan}:{cmd[:80]}")
    return out


def main():
    fd = sys.stdin.fileno()
    last_output = last_report = time.monotonic()
    while True:
        ready, _, _ = select.select([fd], [], [], 30)
        now = time.monotonic()
        if ready:
            chunk = os.read(fd, 65536)
            if not chunk:
                return
            sys.stdout.buffer.write(chunk)
            sys.stdout.flush()
            last_output = last_report = now
        elif now - last_report >= 120:
            print(f"[monitor {time.strftime('%H:%M:%S')}] no output for {int(now - last_output)} s; "
                  + " | ".join(states()), flush=True)
            last_report = now


if __name__ == "__main__":
    main()
