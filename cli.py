"""Quick check from the terminal without starting the server.

Usage:
  python cli.py samples/fake_gmail_fee.txt
  python cli.py samples/genuine.txt --sender campus.hiring@accenture.com
"""
import argparse
from app.analyzer import analyze

parser = argparse.ArgumentParser(description="Check a job offer for scam signs")
parser.add_argument("file", help="Text file containing the offer")
parser.add_argument("--sender", help="Sender email address")
parser.add_argument("--online", action="store_true", help="Also check website age")
args = parser.parse_args()

with open(args.file, encoding="utf-8") as f:
    report = analyze(f.read(), sender=args.sender, online=args.online)

print(f"\n{report.verdict.upper()}  (risk {report.risk_score}/100)\n")
print(report.summary, "\n")
for item in report.findings:
    print(f"  {item.weight:+4}  {item.title}")
    if item.evidence:
        print(f"        \"{item.evidence}\"")
