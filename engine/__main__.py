"""Command line:  ./ce <command>

  doctor                    check setup and say what's missing
  run [--id ID]             process the calendar once (what the schedule runs)
  demo                      add a demo row (test voice, no API key needed) and render it
  schedule on [--every 30]  run automatically every N minutes (macOS launchd); schedule off to stop
  new-client SLUG [--name]  create clients/SLUG/ from the template
  sheet-setup               add headers + status dropdown to your Google Sheet tab
  template                  write templates/content_calendar.csv/.xlsx again
  publish ID                post one Scheduled row now (only if auto-posting is enabled)
  youtube-login             sign in to YouTube once (for auto-posting Shorts)
  metrics                   write views/likes of Posted rows back into the sheet
"""
import argparse
import sys


def main():
    p = argparse.ArgumentParser(prog="ce", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("doctor")
    r = sub.add_parser("run")
    r.add_argument("--id")
    r.add_argument("--max-renders", type=int)
    sub.add_parser("demo")
    s = sub.add_parser("schedule")
    s.add_argument("state", choices=["on", "off"])
    s.add_argument("--every", type=int, default=30, help="minutes between runs")
    n = sub.add_parser("new-client")
    n.add_argument("slug")
    n.add_argument("--name", default="")
    sub.add_parser("sheet-setup")
    sub.add_parser("template")
    pb = sub.add_parser("publish")
    pb.add_argument("id")
    sub.add_parser("youtube-login")
    sub.add_parser("metrics")
    a = p.parse_args()

    if a.cmd == "doctor":
        from .doctor import run
        sys.exit(run())
    if a.cmd == "run":
        from .worker import run
        run(only_id=a.id, max_renders=a.max_renders)
    elif a.cmd == "demo":
        from .demo import run
        run()
    elif a.cmd == "schedule":
        from . import schedule
        schedule.install(a.every) if a.state == "on" else schedule.uninstall()
    elif a.cmd == "new-client":
        from .clients import new_client
        print(f"Created {new_client(a.slug, a.name)}. Fill in brand.json, add voice.wav + avatar.mp4, "
              "and get consent.json signed before rendering.")
    elif a.cmd == "sheet-setup":
        from .sheet import GoogleSheet, open_sheet
        sh = open_sheet("google")
        assert isinstance(sh, GoogleSheet)
        sh.setup()
        print(f"Set up {sh.describe()}")
    elif a.cmd == "template":
        from .templates import write_templates
        write_templates()
    elif a.cmd == "publish":
        from . import config
        if not config.flag("AUTO_POST"):
            sys.exit("Auto-posting is off (AUTO_POST=false in .env). Post the files in ready/ yourself.")
        from .worker import run
        run(only_id=a.id, max_renders=0)
    elif a.cmd == "youtube-login":
        from .publish import youtube
        youtube.login()
    elif a.cmd == "metrics":
        from .metrics import refresh
        refresh()
    else:
        p.print_help()


if __name__ == "__main__":
    main()
