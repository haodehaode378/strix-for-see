# Windows Installation and Release

## Install and First Launch

Install Docker Desktop before scanning; Strix Console detects Docker and links to the required
remediation but never installs or starts it silently. Download the signed NSIS installer from the
stable GitHub Release and run it as the current Windows user. The installer obtains Microsoft
WebView2 when Windows does not already provide it.

Windows SmartScreen may show the publisher or reputation prompt until the installer has established
reputation. Verify the repository, release tag, and installer signature before choosing **More
info > Run anyway**. Never bypass SmartScreen for an installer from another source.

After launch, open **Environment** and resolve every required check. Records and configuration live
under `%LOCALAPPDATA%\StrixConsole`; API credentials stay in Windows Credential Manager.

## Upgrade and Recovery

The app checks only stable GitHub Releases. Installation requires an explicit checkbox and is
blocked while any scan is active or queued. Tauri verifies the signed updater artifact before
replacing the installed version. A download or signature failure leaves the current installation
working. The desktop app, control service, and bundled Strix always share one version.

Sandbox images update separately from a fixed GHCR repository. `sandbox.json` must declare the
version, digest, byte size, and compatible app-version range. Pulls use the immutable digest, expose
download/verification state, and never delete an older image.

## Uninstall

Stop scans, exit from the tray, then uninstall **Strix Console** from Windows Settings > Apps.
Uninstalling the program does not silently delete `%LOCALAPPDATA%\StrixConsole` or Docker images.
Remove those separately only after confirming the local scan records are no longer needed.

## Maintainer Release Checklist

1. Update the matching versions in `console/package.json`, the Python service, Cargo, and
   `tauri.conf.json`; run all checks on Windows.
2. Generate the Tauri updater key once and store the private key only as
   `TAURI_SIGNING_PRIVATE_KEY` and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` GitHub secrets. Store its
   public key as `TAURI_UPDATER_PUBLIC_KEY`.
3. Publish the compatible Sandbox image to
   `ghcr.io/haodehaode378/strix-for-see-sandbox:<version>` and record its digest and compressed byte
   size in `sandbox.json`.
4. Push tag `v<console-version>`. The Console release workflow builds the two sidecars, bilingual
   per-user NSIS installer, signed updater archive, and `latest.json`.
5. On a clean Windows VM, install, run Environment checks, browse a local record, start and stop an
   authorized test scan, check both update paths, uninstall, and record the evidence in the release.

Tags named `strix-v*` remain reserved for the upstream standalone Strix release workflow.
