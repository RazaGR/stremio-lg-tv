#!/usr/bin/env python3
"""Extract a System V / GNU style `ar` archive. Counterpart to mkar.py.

Used by `make verify`. Apple's ar(1) cannot reliably read archives whose
members are not Mach-O objects, so verification parses the format itself and
stays honest about what was actually written.

Usage: unar.py <archive> <output-dir>
Prints the member names in archive order.
"""

import os
import sys

GLOBAL_MAGIC = b"!<arch>\n"
HEADER_SIZE = 60


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: unar.py <archive> <output-dir>\n")
        return 2

    archive, out_dir = argv[1], argv[2]

    with open(archive, "rb") as fh:
        blob = fh.read()

    if not blob.startswith(GLOBAL_MAGIC):
        sys.stderr.write("not an ar archive: %s\n" % archive)
        return 1

    os.makedirs(out_dir, exist_ok=True)

    offset = len(GLOBAL_MAGIC)
    while offset + HEADER_SIZE <= len(blob):
        header = blob[offset:offset + HEADER_SIZE]
        if header[58:60] != b"`\n":
            sys.stderr.write("corrupt member header at offset %d\n" % offset)
            return 1

        name = header[0:16].decode("ascii").strip().rstrip("/")
        size = int(header[48:58].decode("ascii").strip())
        offset += HEADER_SIZE

        with open(os.path.join(out_dir, name), "wb") as out:
            out.write(blob[offset:offset + size])
        print(name)

        offset += size + (size % 2)  # members start on an even offset

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
