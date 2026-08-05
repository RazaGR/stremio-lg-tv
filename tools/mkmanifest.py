#!/usr/bin/env python3
"""Emit the webOS Homebrew manifest for a built .ipk.

The Homebrew Channel tracks an app through a small JSON manifest published as a
release asset. The manifest is regenerated on every release so the version and
the .ipk hash can never drift apart.

Two details matter and are easy to get wrong:

* The filename carries no version -- it is always ``<app-id>.manifest.json`` --
  so ``releases/latest/download/<app-id>.manifest.json`` keeps resolving as new
  versions ship. That URL is what gets registered with the app repository, and
  it must never change.
* ``ipkUrl`` is a bare filename, resolved relative to the manifest's own URL.
  Since both are assets of the same release, this points at the right .ipk
  automatically and needs no absolute URL baked in.

usage:
  mkmanifest.py --appinfo src/appinfo.json --ipk build/app.ipk \
                --repo https://github.com/owner/name [--icon assets/icon160.png] \
                [--out build/<app-id>.manifest.json]
"""

import argparse
import hashlib
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--appinfo", required=True)
    ap.add_argument("--ipk", required=True)
    ap.add_argument("--repo", required=True, help="https://github.com/owner/name")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--icon", default="assets/icon160.png",
                    help="repo-relative path to the icon served to the channel")
    ap.add_argument("--out")
    args = ap.parse_args()

    with open(args.appinfo) as fh:
        info = json.load(fh)

    with open(args.ipk, "rb") as fh:
        ipk_hash = hashlib.sha256(fh.read()).hexdigest()

    repo = args.repo.rstrip("/")

    # Icon is served from the branch rather than a tag, so the listing keeps
    # working for every published version.
    raw = repo.replace("https://github.com/", "https://raw.githubusercontent.com/")
    icon_uri = "%s/%s/%s" % (raw, args.branch, args.icon)

    manifest = {
        "id": info["id"],
        "version": info["version"],
        "type": info.get("type", "web"),
        "title": info["title"],
        "appDescription": info.get("appDescription", ""),
        "iconUri": icon_uri,
        "sourceUrl": repo,
        "rootRequired": False,
        "ipkUrl": os.path.basename(args.ipk),
        "ipkHash": {"sha256": ipk_hash},
    }

    text = json.dumps(manifest, indent=2) + "\n"
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
        sys.stderr.write("wrote %s\n" % args.out)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
