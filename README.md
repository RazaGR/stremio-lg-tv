# Stremio for webOS TV

A native webOS TV app that opens [Stremio](https://tv.strem.io/) on an LG Smart
TV, packaged as an installable `.ipk`.

The app itself is small — a boot screen, a connection check, and a handover to
Stremio. Most of this repository is the packaging: a `make` build that produces
a valid `.ipk` **without needing the webOS TV SDK**.

## Install

Sideloading onto an LG TV needs Developer Mode, and Developer Mode needs a free
LG developer account. Everything below uses LG's official CLI — no IDE, no SDK
installer and no third-party tools.

### 1. Create an LG developer account

Sign up at <https://webostv.developer.lge.com/> and verify the email.

### 2. Turn on Developer Mode on the TV

1. Open the **LG Content Store** on the TV and install the **Developer Mode**
   app.
2. Launch it and sign in with the account from step 1.
3. Turn on **Dev Mode Status**, then turn on **Key Server**.
4. The TV restarts and shows a **6-character passphrase** and its **IP address**
   — keep both to hand.

Developer Mode expires after about 1000 hours; reopen the app and press
**Extend** to renew it.

### 3. Install the CLI and register the TV

```sh
npm install -g @webos-tools/cli    # LG's official webOS TV CLI
ares-setup-device                  # add your TV: IP address + passphrase
```

Pick **add**, name the device (for example `mytv`), enter the TV's IP, leave the
port at `9922` and the user at `prisoner`, and paste the passphrase.

### 4. Install the app

```sh
make install DEVICE=mytv
make launch  DEVICE=mytv
```

That builds the `.ipk` and pushes it straight to the TV. The app then appears in
the Home launcher.

To install a prebuilt package instead of building it, download the `.ipk` from
the [latest release](../../releases/latest) and run:

```sh
ares-install -d mytv <downloaded>.ipk
```

### Alternative: install with a GUI

If you would rather not use a terminal, [webOS Dev
Manager](https://github.com/webosbrew/dev-manager-desktop) installs a downloaded
`.ipk` without Node.js or the CLI. Steps 1 and 2 above are still required.

1. Download the `.ipk` from the [latest release](../../releases/latest).
2. Install and open webOS Dev Manager, click **Add Device**, and enter the TV's
   IP address and the 6-character passphrase.
3. Go to the **Apps** tab → **Install app** → **Choose File**, pick the
   downloaded `.ipk`, and click **Install**.

The app appears in the Home launcher within a few seconds.

## Requirements

| | |
|---|---|
| TV | webOS 5.0 or newer (2020 models and later) |
| Build | `make`, `python3`, `tar` |
| Deploy | `@webos-tools/cli` from npm (needs Node.js) |

Stremio's engine is compiled to WebAssembly, which arrived in Chromium 57.
webOS 3.x (Chromium 38) and 4.x (Chromium 53) cannot run it; the app detects
this and says so rather than opening a page that will never load.

## Build

```sh
make              # → build/<app-id>_<version>_all.ipk
make check        # validate appinfo.json and icon dimensions
make check-probe  # assert the connection-probe URL still serves an image
make verify       # build, then assert the .ipk structure is correct
make manifest     # write the Homebrew Channel manifest for the built .ipk
make help         # all targets
```

With a device registered (step 3 above):

```sh
make install DEVICE=mytv
make launch  DEVICE=mytv
make inspect DEVICE=mytv    # remote Web Inspector
```

## Releasing

Pushing a `v*` tag is the entire release process. GitHub Actions builds the
`.ipk`, verifies its structure, and publishes it as a GitHub release that anyone
can download and sideload.

**First time only** — create an empty repository on GitHub, then:

```sh
git remote add origin git@github.com:<owner>/<repo>.git
git push -u origin main
```

**Each release:**

1. Bump `version` in [`src/appinfo.json`](src/appinfo.json). webOS refuses to
   install a package over an equal or lower version, so this must go up every
   time.

   ```jsonc
   "version": "1.0.4",
   ```

2. Commit it, then tag with a matching `v` prefix and push the tag:

   ```sh
   git commit -am "Release 1.0.4"
   git push
   git tag v1.0.4
   git push origin v1.0.4
   ```

3. Watch the run under the repository's **Actions** tab. When it finishes, the
   **Releases** page has the `.ipk` and a `SHA256SUMS` file attached, with
   release notes generated from the commits.

The workflow refuses to publish if the tag and `src/appinfo.json` disagree —
tagging `v1.0.4` while `appinfo.json` still says `1.0.3` would otherwise ship a
package that silently fails to install over the previous one.

To undo a bad tag before anyone downloads it:

```sh
git push --delete origin v1.0.4
git tag -d v1.0.4
```

Then delete the release from the Releases page if one was created.

## Submitting to the Homebrew Channel

[`webosbrew/com.razagr.stremio.yml`](webosbrew/com.razagr.stremio.yml) is
the submission file for the [webOS Homebrew app
repository](https://github.com/webosbrew/apps-repo). To list the app:

1. Cut a release first — the submission points at release assets that must
   already exist.
2. Fork `webosbrew/apps-repo`, copy the file into `packages/`, and open a pull
   request.

Once merged the app is installable from the Homebrew Channel on the TV. The
`manifestUrl` resolves through `releases/latest/download/`, so every later
release is picked up automatically and the submission never needs updating.

## Configure

Tunables live in [`src/js/config.js`](src/js/config.js): the Stremio URL, the
connection check and the boot timings. Package identity lives in
[`src/appinfo.json`](src/appinfo.json), which is the single source of truth —
the Makefile reads the id, title, version and vendor from it. To publish under
your own namespace, change `id` there.

Two behaviours worth knowing before changing them:

- **The app navigates the top-level window to Stremio** rather than embedding
  it. That keeps Stremio's storage first-party, which is what lets your login
  and addon collection survive a restart.
- **The connection check never blocks startup.** If it fails, the app reports it
  and opens Stremio anyway. Note that a probe URL which 404s serves an HTML
  error page — it cannot decode as an image, and the failure is
  indistinguishable from being offline. `make check-probe` guards against that.

## Notes on Stremio itself

**The Addons screen does not list your addons.** It shows only a prompt to
configure addons on your phone or PC and press *Sync Addons*, and it stays that
way even when addons are installed and working. Nothing is wrong.

To confirm your addons really are there, open any title and press **Show
Streams** — streams from your addons will be listed. Or read the profile
directly via `make inspect`:

```js
JSON.parse(localStorage.getItem('profile')).addons.map(a => a.manifest.name)
```

## Layout

```
src/
  appinfo.json      app manifest (source of truth for id/title/version/vendor)
  index.html        boot screen
  css/app.css       boot screen styling
  js/config.js      tunables
  js/app.js         capability check, connection check, handover
  icon.png          80x80    (required by webOS)
  largeIcon.png     130x130
  splash.png        1920x1080
tools/
  make-icons.py     regenerates the three PNGs   (`make icons`)
  mkar.py           writes the .ipk ar container
  unar.py           reads it back for `make verify`
  mkmanifest.py     writes the Homebrew Channel manifest (`make manifest`)
assets/
  icon160.png       listing icon for the Homebrew Channel (not packaged)
webosbrew/
  com.razagr.stremio.yml   submission file for the app repository
Makefile
```

### How the packaging works

An `.ipk` is an `ar` archive of `debian-binary`, `control.tar.gz` and
`data.tar.gz`, in that order, unpacking into `/usr/palm`.

The archive is written by `tools/mkar.py` rather than `ar(1)`. Apple's `ar`
treats every archive as a static library: it rejects members that are not
Mach-O objects and writes a `__.SYMDEF` table in their place, silently
producing an empty package. Emitting the 60-byte member headers directly is a
few lines, and makes the build behave identically on macOS and Linux. The tar
steps also strip macOS AppleDouble (`._*`) entries and xattrs, which `opkg` on
the TV would reject.

`make verify` unpacks the result and asserts the structure, so a broken package
fails the build instead of the TV.

## License

MIT — see [LICENSE](LICENSE).

Stremio is a separate project with its own license and terms. This repository
bundles none of its code; it packages a launcher that opens it.
