# Stremio for webOS TV -- packaging.
#
# Builds a webOS .ipk WITHOUT requiring the webOS TV SDK. An .ipk is just an
# `ar` archive holding three members in a fixed order:
#
#   debian-binary    format marker, the text "2.0"
#   control.tar.gz   package metadata (the `control` file)
#   data.tar.gz      the filesystem tree to unpack on the TV
#
# The archive is written by tools/mkar.py rather than ar(1), because Apple's ar
# rejects non-Mach-O members and would silently emit an empty package; see that
# file. If the SDK happens to be installed, `make install` / `make launch` /
# `make uninstall` drive it.
#
# Usage:
#   make              # build the .ipk
#   make install      # install onto DEVICE (needs webOS SDK)
#   make help         # all targets

SHELL := /bin/sh

SRC    := src
BUILD  := build
TOOLS  := tools

# appinfo.json is the single source of truth for identity and version, so
# there is nothing to keep in sync between it and this file.
appinfo = $(shell sed -n 's/^[[:space:]]*"$(1)"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' $(SRC)/appinfo.json | head -1)

APP_ID  := $(call appinfo,id)
VERSION := $(call appinfo,version)
TITLE   := $(call appinfo,title)
VENDOR  := $(call appinfo,vendor)

# Pulled out of config.js so `check-probe` can validate the real URL the app
# will request, rather than a copy of it kept here.
CFG_URL   := $(shell sed -n "s/^[[:space:]]*url:[[:space:]]*'\([^']*\)'.*/\1/p" $(SRC)/js/config.js | head -1)
CFG_PROBE := $(shell sed -n "s/^[[:space:]]*probeImage:[[:space:]]*'\([^']*\)'.*/\1/p" $(SRC)/js/config.js | head -1)

MAINTAINER ?= $(VENDOR)
DESCRIPTION ?= $(TITLE) for webOS TV

STAGE  := $(BUILD)/stage
APPDIR := $(STAGE)/usr/palm/applications/$(APP_ID)
PKGDIR := $(STAGE)/usr/palm/packages/$(APP_ID)
CTRL   := $(BUILD)/control-root
IPK    := $(BUILD)/$(APP_ID)_$(VERSION)_all.ipk

# Device name as registered with `ares-setup-device`.
DEVICE ?= tv

# Rebuild whenever any source file changes.
APP_FILES := $(shell find $(SRC) -type f ! -name '.DS_Store' 2>/dev/null)

# Normalise ownership and keep macOS AppleDouble/xattr junk out of the
# archives -- opkg on the TV chokes on the ._* resource-fork entries.
# bsdtar (macOS) and GNU tar spell these differently.
IS_BSDTAR := $(shell tar --version 2>&1 | grep -qi bsdtar && echo yes)
ifeq ($(IS_BSDTAR),yes)
  TAR_FLAGS := --format=ustar --uid 0 --gid 0 --uname root --gname root \
               --no-mac-metadata --no-xattrs --no-acls --no-fflags
else
  TAR_FLAGS := --format=ustar --owner=root --group=root --numeric-owner
endif
TAR := COPYFILE_DISABLE=1 tar $(TAR_FLAGS)

.PHONY: all package stage clean distclean icons check check-probe verify manifest print-version install uninstall launch inspect info help

all: package

package: $(IPK)

## ---- staging ------------------------------------------------------------

# Lay out the exact tree the TV expects under /usr/palm.
stage: $(APP_FILES)
	@rm -rf $(STAGE)
	@mkdir -p $(APPDIR) $(PKGDIR)
	@# -R copies the tree; the trailing /. copies contents, not the dir itself.
	@cp -R $(SRC)/. $(APPDIR)/
	@find $(APPDIR) -name '.DS_Store' -delete
	@printf '%s\n' \
		'{' \
		'  "app": "$(APP_ID)",' \
		'  "id": "$(APP_ID)",' \
		'  "loc_name": "$(TITLE)",' \
		'  "package_format_version": 2,' \
		'  "vendor": "$(VENDOR)",' \
		'  "version": "$(VERSION)"' \
		'}' > $(PKGDIR)/packageinfo.json
	@echo "staged $(APP_ID) $(VERSION)"

## ---- packaging ----------------------------------------------------------

$(IPK): stage
	@rm -rf $(CTRL) && mkdir -p $(CTRL)
	@# Debian's Installed-Size is advisory here; opkg on webOS does not enforce it.
	@printf '%s\n' \
		'Package: $(APP_ID)' \
		'Version: $(VERSION)' \
		'Section: misc' \
		'Priority: optional' \
		'Architecture: all' \
		"Installed-Size: $$(($$(du -sk $(STAGE) | cut -f1) * 1024))" \
		'Maintainer: $(MAINTAINER)' \
		'Description: $(DESCRIPTION)' \
		'webOS-Package-Format-Version: 2' \
		'webOS-Packager-Version: make' > $(CTRL)/control
	@# Member paths carry no './' prefix, matching ares-package byte for byte.
	@$(TAR) -czf $(BUILD)/control.tar.gz -C $(CTRL) control
	@$(TAR) -czf $(BUILD)/data.tar.gz -C $(STAGE) usr
	@printf '2.0\n' > $(BUILD)/debian-binary
	@rm -f $@
	@# Order matters: debian-binary must be the first member. Written by
	@# tools/mkar.py rather than ar(1) -- see that file for why.
	@python3 $(TOOLS)/mkar.py $@ \
		$(BUILD)/debian-binary $(BUILD)/control.tar.gz $(BUILD)/data.tar.gz
	@rm -f $(BUILD)/control.tar.gz $(BUILD)/data.tar.gz $(BUILD)/debian-binary
	@rm -rf $(CTRL)
	@echo "built $@ ($$(du -h $@ | cut -f1))"

## ---- release ------------------------------------------------------------

# Repository the release assets are published from. CI supplies this from the
# GitHub context; locally it falls back to the origin remote.
# NB: sed uses | as its delimiter here, not / or #. A # anywhere on this line
# would start a make comment and truncate the function call.
REPO_URL ?= $(if $(GITHUB_REPOSITORY),https://github.com/$(GITHUB_REPOSITORY),$(shell git remote get-url origin 2>/dev/null | sed -e 's|^git@github\.com:|https://github.com/|' -e 's|\.git$$||'))

# Manifest for the webOS Homebrew Channel. The filename deliberately carries no
# version: the app repository registers the releases/latest/download/ URL once,
# and it must keep resolving as new versions ship.
MANIFEST := $(BUILD)/$(APP_ID).manifest.json

manifest: $(IPK)
	@test -n "$(REPO_URL)" \
		|| { echo "REPO_URL is unset and no origin remote found; pass REPO_URL=https://github.com/owner/name"; exit 1; }
	@python3 $(TOOLS)/mkmanifest.py \
		--appinfo $(SRC)/appinfo.json --ipk $(IPK) \
		--repo "$(REPO_URL)" --out $(MANIFEST)

# Used by CI to check the pushed tag matches appinfo.json.
print-version:
	@echo $(VERSION)

## ---- assets -------------------------------------------------------------

# Regenerate the packaged icons (80x80, 130x130, splash) plus the 160x160
# listing icon used by the Homebrew Channel, which is kept out of the .ipk.
icons:
	@python3 $(TOOLS)/make-icons.py $(SRC) assets

## ---- verification -------------------------------------------------------

# Validate the sources before packaging.
check:
	@python3 -c "import json,sys; json.load(open('$(SRC)/appinfo.json'))" \
		&& echo "appinfo.json: valid JSON"
	@test -n "$(APP_ID)"  || { echo "appinfo.json: missing id"; exit 1; }
	@test -n "$(VERSION)" || { echo "appinfo.json: missing version"; exit 1; }
	@test -f $(SRC)/index.html || { echo "missing $(SRC)/index.html"; exit 1; }
	@python3 -c "import struct,sys; \
		[sys.exit('%s must be %dx%d' % (p,w,h)) \
		 for p,w,h in (('$(SRC)/icon.png',80,80),('$(SRC)/largeIcon.png',130,130)) \
		 if struct.unpack('>II', open(p,'rb').read(24)[16:24]) != (w,h)]" \
		&& echo "icons: correct dimensions"
	@echo "check: ok ($(APP_ID) $(VERSION))"

# Network check, kept out of `check` so offline builds still work.
#
# A probe URL that 404s serves an HTML error page; <img> cannot decode that, so
# the app would report a connection problem on a perfectly healthy TV. Assert
# the URL really returns an image.
check-probe:
	@echo "probing $(CFG_URL)$(CFG_PROBE)"
	@type=$$(curl -fsSL -o /dev/null -w '%{content_type}' "$(CFG_URL)$(CFG_PROBE)") \
		|| { echo "probe URL is not reachable"; exit 1; }; \
	case "$$type" in \
		image/*) echo "check-probe: ok ($$type)" ;; \
		*) echo "probe URL returned '$$type', not an image"; exit 1 ;; \
	esac

# Unpack the built .ipk and prove it has the structure the TV expects.
verify: $(IPK)
	@rm -rf $(BUILD)/verify && mkdir -p $(BUILD)/verify
	@python3 $(TOOLS)/unar.py $(IPK) $(BUILD)/verify >/dev/null
	@test "$$(cat $(BUILD)/verify/debian-binary)" = "2.0" \
		|| { echo "bad debian-binary"; exit 1; }
	@tar tzf $(BUILD)/verify/control.tar.gz | grep -q control \
		|| { echo "control.tar.gz missing control"; exit 1; }
	@tar tzf $(BUILD)/verify/data.tar.gz | grep -q 'usr/palm/applications/$(APP_ID)/appinfo.json' \
		|| { echo "data.tar.gz missing appinfo.json"; exit 1; }
	@tar tzf $(BUILD)/verify/data.tar.gz | grep -q 'usr/palm/packages/$(APP_ID)/packageinfo.json' \
		|| { echo "data.tar.gz missing packageinfo.json"; exit 1; }
	@! tar tzf $(BUILD)/verify/data.tar.gz | grep -q '\._' \
		|| { echo "data.tar.gz contains macOS resource forks"; exit 1; }
	@! tar tzf $(BUILD)/verify/data.tar.gz | grep -q '\.git/' \
		|| { echo "data.tar.gz contains a .git directory"; exit 1; }
	@rm -rf $(BUILD)/verify
	@echo "verify: ok"

## ---- device -------------------------------------------------------------
# These need the webOS TV CLI (ares-*) on PATH and a device registered with
# `ares-setup-device`. Without the SDK, sideload $(IPK) with the webOS Dev
# Manager desktop app instead.

install: $(IPK)
	@command -v ares-install >/dev/null 2>&1 \
		|| { echo "ares-install not found -- install the webOS TV SDK, or sideload $(IPK) with webOS Dev Manager"; exit 1; }
	ares-install -d $(DEVICE) $(IPK)

uninstall:
	@command -v ares-install >/dev/null 2>&1 || { echo "ares-install not found"; exit 1; }
	ares-install -d $(DEVICE) -r $(APP_ID)

launch:
	@command -v ares-launch >/dev/null 2>&1 || { echo "ares-launch not found"; exit 1; }
	ares-launch -d $(DEVICE) $(APP_ID)

# Open the remote Web Inspector against the running app.
inspect:
	@command -v ares-inspect >/dev/null 2>&1 || { echo "ares-inspect not found"; exit 1; }
	ares-inspect -d $(DEVICE) $(APP_ID) --open

## ---- housekeeping -------------------------------------------------------

info:
	@echo "id:      $(APP_ID)"
	@echo "title:   $(TITLE)"
	@echo "version: $(VERSION)"
	@echo "vendor:  $(VENDOR)"
	@echo "output:  $(IPK)"
	@echo "device:  $(DEVICE)"

clean:
	@rm -rf $(STAGE) $(CTRL) $(BUILD)/verify \
		$(BUILD)/control.tar.gz $(BUILD)/data.tar.gz $(BUILD)/debian-binary

distclean:
	@rm -rf $(BUILD)

help:
	@echo "Stremio for webOS TV"
	@echo
	@echo "  make            build the .ipk into $(BUILD)/"
	@echo "  make check      validate appinfo.json and icon sizes"
	@echo "  make check-probe  assert the connection-probe URL serves an image"
	@echo "  make verify     build, then assert the .ipk structure is correct"
	@echo "  make manifest   write the Homebrew Channel manifest for the built .ipk"
	@echo "  make icons      regenerate icon/largeIcon/splash PNGs"
	@echo "  make install    install onto the TV      (DEVICE=$(DEVICE))"
	@echo "  make launch     launch it on the TV      (DEVICE=$(DEVICE))"
	@echo "  make uninstall  remove it from the TV    (DEVICE=$(DEVICE))"
	@echo "  make inspect    open the Web Inspector   (DEVICE=$(DEVICE))"
	@echo "  make info       show resolved package identity"
	@echo "  make clean      remove intermediates"
	@echo "  make distclean  remove $(BUILD)/ entirely"
