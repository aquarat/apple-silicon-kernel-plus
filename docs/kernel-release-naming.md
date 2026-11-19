# Kernel release naming

How this project's kernel releases are named and why they sort where
they do against `@asahi`'s kernels. Short version in the
[README](../README.md#kernel-release-naming).

The kernel is `<Linux version>-<N>.asahiwip.plus<M>.fc44`:

| | version-release | `uname -r` |
|---|---|---|
| stock `@asahi` | `7.1.13-402.asahi.fc44` | `7.1.13-402.asahi.fc44.aarch64+16k` |
| this project, up to 7.1.13 | `7.1.13-402.asahi.plus1.fc44` | `7.1.13-402.asahi.plus1.fc44.aarch64+16k` |
| this project, 7.2.11 before Thunderbolt networking | `7.2.11-900.asahiwip.plus1.fc44` | `7.2.11-900.asahiwip.plus1.fc44.aarch64+16k` |
| this project, 7.2.11 with Thunderbolt networking | `7.2.11-900.asahiwip.plus2.fc44` | `7.2.11-900.asahiwip.plus2.fc44.aarch64+16k` |
| this project, 7.2.11 with TSO forwarding | `7.2.11-900.asahiwip.plus3.fc44` | `7.2.11-900.asahiwip.plus3.fc44.aarch64+16k` |
| this project, 7.2.11 with the independent PAuth patch | `7.2.11-900.asahiwip.plus4.fc44` | `7.2.11-900.asahiwip.plus4.fc44.aarch64+16k` |
| this project, 7.2.11 with thunderbolt-net TSO for a lowered MSS and the GPU kernel-VM BO leak fix (branch `kernel-7.2`) | `7.2.11-900.asahiwip.plus5.fc44` | `7.2.11-900.asahiwip.plus5.fc44.aarch64+16k` |
| this project, 7.2.15 | `7.2.15-900.asahiwip.plus1.fc44` | `7.2.15-900.asahiwip.plus1.fc44.aarch64+16k` |
| this project, 7.3.1 | `7.3.1-900.asahiwip.plus1.fc44` | `7.3.1-900.asahiwip.plus1.fc44.aarch64+16k` |
| this project, 7.3.1 with thunderbolt-net TSO for a lowered MSS | `7.3.1-900.asahiwip.plus2.fc44` | `7.3.1-900.asahiwip.plus2.fc44.aarch64+16k` |
| this project, 7.3.1 with the independent PAuth patch | `7.3.1-900.asahiwip.plus3.fc44` | `7.3.1-900.asahiwip.plus3.fc44.aarch64+16k` |
| this project, 7.3.1 with the PMP fabric/DRAM requests (patches 0030-0034) | `7.3.1-900.asahiwip.plus4.fc44` | `7.3.1-900.asahiwip.plus4.fc44.aarch64+16k` |
| this project now (7.3.4; kept at `plus5` rather than `plus1` so the plus number keeps rising across the 7.3 line; sorts above `@asahi`'s `7.3.4-401.asahi`) | `7.3.4-900.asahiwip.plus5.fc44` | `7.3.4-900.asahiwip.plus5.fc44.aarch64+16k` |

- The version is the Linux release the pinned Asahi commit is based on
  (`KERNEL_VERSION` in [`packages/kernel/kernel-plus.conf`](../packages/kernel/kernel-plus.conf)).
- `N` (`PKGRELEASE`) starts at 900 for each Linux version and goes up by
  one for each newer Asahi commit on the same Linux version. 900 is above
  any release number `@asahi` uses (400 and up), so for the same Linux
  version this project's kernel sorts first.
- `asahiwip` says where the source comes from (the Asahi tree; the name
  stayed when the pin moved from the `asahi-wip` branch to an `asahi` tag
  at 7.2.15); `plus<M>` (`BUILDID`) goes
  up when only this project's patches, configs or packaging change, and
  back to `plus1` when `N` or the version changes.

rpm compares version first, then the release segment by segment (numbers
as numbers, letters as strings). Checked with `rpmdev-vercmp`:

| this project's `7.2.11-900.asahiwip.plus1.fc44` against | result |
|---|---|
| `7.1.13-402.asahi.fc44` (stock), `7.1.13-402.asahi.plus1.fc44` (ours before), `7.1.14-403.asahi.fc44` | newer (7.2.11 > 7.1.x) |
| `7.2.11-400.asahi.fc44`, `7.2.11-402.asahi.fc44` (a future `@asahi` 7.2.11) | newer (900 > 40x) |
| `7.2.11-200.fc44` (Fedora's, not a 16k package anyway) | newer |
| `7.2.11-900.asahiwip.plus2.fc44`, `7.2.11-901.asahiwip.plus1.fc44`, `7.2.12-900.asahiwip.plus1.fc44` | older (our own next builds) |
| `7.2.12-400.asahi.fc44`, `7.3.0-400.asahi.fc44` (a future `@asahi` kernel of a newer Linux version) | older |

`7.2.11-901.asahiwip.plus1` is also newer than `7.2.11-900.asahiwip.plus9`:
`N` decides before `M`.

So once `@asahi` publishes a kernel of a newer Linux version than this
project's, `dnf upgrade` offers `@asahi`'s, which has none of this
project's changes. To stay on this project's kernels, give the COPR
repository a higher priority:

```sh
sudo dnf config-manager setopt "copr:copr.fedorainfracloud.org:aquarat:apple-silicon-kernel-plus.priority=10"
```

dnf then takes `kernel-16k` only from this repository.
