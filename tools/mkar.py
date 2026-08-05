#!/usr/bin/env python3
"""Write a System V / GNU style `ar` archive -- the container format of an .ipk.

Apple's ar(1) cannot be used here: it treats every archive as a static library,
rejects members that are not Mach-O objects ("not a mach-o file") and writes a
__.SYMDEF table in their place, producing an empty package. Emitting the format
directly is a few lines and additionally makes the build byte-for-byte
identical on macOS and Linux.

Layout (verified byte-for-byte against an .ipk produced by LG's ares-package):

    "!<arch>\\n"                     global magic
    then, per member, a 60-byte ASCII header:
        name   16  space padded, no trailing '/'
        mtime  12  decimal seconds
        uid     6  0
        gid     6  0
        mode    8  100644
        size   10  decimal bytes
        magic   2  "`\\n"
    followed by the raw bytes, padded to an even length with "\\n".

Usage: mkar.py <archive> <member>...
Member order is significant: an .ipk must begin with debian-binary.
"""

import os
import sys
import time

GLOBAL_MAGIC = b"!<arch>\n"
HEADER_MAGIC = b"`\n"


def member_header(name, size, mtime):
    if len(name) > 16:
        # The GNU/BSD long-name extensions are not portable across opkg
        # implementations, and every name an .ipk uses is short.
        raise ValueError("member name too long for the ar header: %r" % name)

    fields = (
        (name, 16),
        (str(int(mtime)), 12),
        ("0", 6),       # uid  -- always root
        ("0", 6),       # gid  -- always root
        ("100644", 8),  # mode
        (str(size), 10),
    )

    header = "".join(value.ljust(width) for value, width in fields)
    return header.encode("ascii") + HEADER_MAGIC


def main(argv):
    if len(argv) < 3:
        sys.stderr.write("usage: mkar.py <archive> <member>...\n")
        return 2

    archive, members = argv[1], argv[2:]

    # Honour SOURCE_DATE_EPOCH so packages can be built reproducibly.
    mtime = int(os.environ.get("SOURCE_DATE_EPOCH") or time.time())

    with open(archive, "wb") as out:
        out.write(GLOBAL_MAGIC)
        for path in members:
            with open(path, "rb") as fh:
                data = fh.read()
            out.write(member_header(os.path.basename(path), len(data), mtime))
            out.write(data)
            # Members start on an even offset.
            if len(data) % 2:
                out.write(b"\n")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
