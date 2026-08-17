# cfglink

Symlink-based config backup tool. Live config files are replaced by
symlinks pointing into a git-managed pool (`config-pool`).

## Install

```bash
cd config-link
pip install -e .
```

## Commands

```bash
# adopt a live file: copy into pool, symlink back, record entry,
# then open config.json in VS Code
cfglink add ~/.wezterm.lua
cfglink add ~/.tmux.conf -c tmux        # override category dir

# copy live files (dst) into the pool
cfglink upload

# replace live files with symlinks into the pool (.bak backups first)
cfglink download

# open the pool root folder in VS Code
cfglink open

# show pool paths; menu to change the pool directory (persisted)
cfglink path
```

## Paths

- Pool root: `~/tools/config-pool` by default, changeable via `cfglink path`
  (saved to `~/.config/cfglink/settings.json`).
- Platform dir: `<pool_root>/<win|mac|linux>` — auto-detected, holds
  `config.json` and the category folders.
- `--basepath <dir>` overrides the platform dir for one invocation.

`add` guesses the category dir from the file name (wezterm, tmux, vim,
bash, git, ...); fallback is the leading stem (`.foo.conf` → `foo/`).
Use `-c` to override.

## JSON config example

```json
{
    "powershell": [
        {
            "src": "powershell/ps_profile.ps1",
            "dst": "C:\\Users\\amomo\\Documents\\WindowsPowerShell\\Microsoft.PowerShell_profile.ps1"
        }
    ],
    "terminal": [
        { "src": "wezterm/.wezterm.lua", "dst": "~/.wezterm.lua" }
    ]
}
```

## Pool folder structure

```txt
~/tools/config-pool
├── win
│   ├── config.json
│   ├── powershell
│   │   └── ps_profile.ps1
│   └── wezterm
│       └── .wezterm.lua
└── mac
    └── ...
```

## Notes

- Windows: symlink creation requires Developer Mode (or an admin shell);
  `rm`-style deletations are done natively, run from any shell.
- WSL caveat: a tmux running inside WSL reads its own `$HOME`; link the
  config inside the WSL filesystem instead.
