# Pilot builds

Unsigned builds of CommCare Data Pipeline for Windows and macOS, for
product managers and QA engineers. Each build is a GitHub prerelease
tagged `pilot-YYYYMMDD-<commit>` with three downloads: a Windows
installer, and a zip of the macOS app for Apple Silicon (`arm64`) and
for Intel (`x86_64`).

The builds are not signed, so both operating systems warn before
running them. The steps below get past the warnings.

## Installing on Windows

1. Download `CommCare-Data-Pipeline-Setup-<version>.exe` and run it.
2. SmartScreen says "Windows protected your PC". Click **More info**,
   then **Run anyway**.
3. The installer needs no administrator rights. It installs for your
   user account and adds **CommCare Data Pipeline** to the Start Menu.

Start it from the Start Menu. A window opens; on the first run it shows
the setup page, where you create the admin user.

## Installing on macOS

1. Download the zip for your Mac: `arm64` for Apple Silicon (M1 and
   later), `x86_64` for Intel. If unsure, Apple menu → About This Mac.
2. Double-click the zip to unpack `CommCare Data Pipeline.app`, and
   move it to Applications.
3. Open it. macOS refuses: "Apple could not verify ... is free of
   malware". Click **Done**, then open **System Settings → Privacy &
   Security**, scroll to the Security section, and click **Open Anyway**
   next to the message about CommCare Data Pipeline. Confirm, and
   authenticate.

Or, in Terminal, remove the quarantine flag and open it normally:

```shell
xattr -dr com.apple.quarantine "/Applications/CommCare Data Pipeline.app"
```

## Where things are

The app keeps its database, encryption keys, logs and uploaded files in
a data directory for your user account:

| Platform | Data directory                                   |
| -------- | ------------------------------------------------ |
| Windows  | `%LOCALAPPDATA%\commcare-sync`                   |
| macOS    | `~/Library/Application Support/commcare-sync`    |

Logs are in `logs/` there: `launcher.log` for the app's own startup and
shutdown, `app.log` for the web application, and the export tool's logs
for each export. To report a problem, zip the `logs` folder and attach
it, with the build's tag and what you did. The logs contain no
passwords or API keys.

Uninstalling leaves the data directory in place. Delete it by hand to
start over.

## Databases

Exports write to a PostgreSQL, MySQL or SQL Server database that you
provide. PostgreSQL and MySQL need nothing more. SQL Server needs
Microsoft's ODBC driver for SQL Server, which is a separate install on
every platform; without it, an export to SQL Server fails with a
message about the driver. The pilot builds have not been tested against
SQL Server.

## QA checklist

Run on Windows, on an Apple Silicon Mac and on an Intel Mac.

- [ ] First run: the window opens on the setup page; creating the admin
      user signs you in.
- [ ] Closing the window with no run in progress closes it without a
      question.
- [ ] A real export into a scratch database runs to completion, and the
      run shows as completed.
- [ ] Closing the window during a run asks for confirmation. Cancel keeps
      the window open; Quit closes it. After reopening the app, the run
      shows as Interrupted, a retry has run, and the banner at the top
      of the page lists the interrupted run.
- [ ] Opening the app a second time while it is running opens the running
      instance in the browser instead of a second window.
- [ ] After closing the app, no `commcare-sync` process remains (Task
      Manager on Windows, Activity Monitor on macOS).
