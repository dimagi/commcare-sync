# Pilot builds

Unsigned builds of CommCare Data Pipeline for Windows and macOS, for product
managers and QA engineers. Each build is a prerelease on the
[releases page](https://github.com/dimagi/commcare-sync/releases) tagged
`pilot-YYYYMMDD-<commit>` with three downloads: a Windows installer, and a zip
of the macOS app for Apple Silicon (`arm64`) and for Intel (`x86_64`).

## Installing

Follow [Install CommCare Data Pipeline](install.md). The builds are not signed,
so Windows and macOS each warn once before running them; the installation guide
says how to get past the warnings.

## Reporting a problem

Zip the `logs` folder from the data directory and attach it, with the build's
tag and what you did. [Troubleshooting](troubleshooting.md) says where the data
directory is and what to check first.

## QA checklist

Run on Windows, on an Apple Silicon Mac and on an Intel Mac.

- [ ] First run: the window opens on the setup page; creating the admin user
      signs you in.
- [ ] Closing the window with no run in progress closes it without a question.
- [ ] A real export into a scratch database runs to completion, and the run
      shows as completed.
- [ ] Closing the window during a run asks for confirmation. Cancel keeps the
      window open; Quit closes it. After reopening the app, the run shows as
      Interrupted, a retry has run, and the banner at the top of the page lists
      the interrupted run.
- [ ] Opening the app a second time while it is running opens the running
      instance in the browser instead of a second window.
- [ ] After closing the app, no `commcare-sync` process remains (Task Manager on
      Windows, Activity Monitor on macOS).
