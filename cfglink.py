"""cfglink — symlink-based config backup tool.

Pool layout:  <pool_root>/<platform>/{config.json, <category>/<file>}
Live layout:  dst paths listed in config.json are replaced by symlinks
pointing back into the pool.

Commands:
    cfglink add <dst>       adopt a file: copy into pool, symlink back,
                            record in config.json, open it in VS Code
    cfglink upload          copy live files (dst) into the pool (src)
    cfglink download        replace live files with symlinks into the pool
    cfglink open            open the pool root folder in VS Code
    cfglink path            show pool paths, menu to change pool directory
"""

import json
import os
import shutil
import subprocess
import sys

import click
import questionary

DEFAULT_POOL_ROOT = os.path.join(os.path.expanduser("~"), "tools", "config-pool")
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".config", "cfglink", "settings.json")

# filename substring -> pool category dir (ordered, first match wins)
CATEGORY_HINTS = [
    ("wezterm", "wezterm"),
    ("tmux", "tmux"),
    ("powershell", "powershell"),
    ("vim", "vim"),        # .vimrc / .ideavimrc
    ("bash", "bash"),
    ("zsh", "zsh"),
    ("git", "git"),
    ("maven", "maven"),
    ("npm", "npm"),
]


def detect_platform():
    # pool subdir per OS
    if sys.platform.startswith("win"):
        return "win"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def guess_category(filename):
    # infer the pool category dir from the file name; fallback to first stem
    low = filename.lower()
    for hint, cat in CATEGORY_HINTS:
        if hint in low:
            return cat
    stem = low.lstrip(".").split(".")[0]
    return stem or "misc"


def get_path(path):
    path = os.path.expanduser(path)
    return os.path.abspath(path)


def general_copy(src, dst):
    # copy a file or a tree; symlinks are skipped with a warning
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    elif os.path.isfile(src):
        if os.path.islink(src):
            print(f"Warning: {src} is a symlink, no copy performed.")
        elif os.path.islink(dst):
            print(f"Warning: {dst} is a symlink, no copy performed.")
        else:
            shutil.copy(src, dst)
            print(f"File copied from {src=} to {dst=}")


def remove_path(path):
    # native "rm -rf" equivalent (no external command dependency)
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def same_content(a, b):
    # byte-compare two files (files only, caller checks types)
    if os.path.getsize(a) != os.path.getsize(b):
        return False
    with open(a, "rb") as fa, open(b, "rb") as fb:
        while True:
            ca, cb = fa.read(65536), fb.read(65536)
            if ca != cb:
                return False
            if not ca:
                return True


def load_settings():
    # read ~/.config/cfglink/settings.json; tolerate missing/broken file
    try:
        with open(SETTINGS_PATH, "r") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=4)
        f.write("\n")


def resolve_pool_root():
    # pool root = settings override, else default ~/tools/config-pool
    root = load_settings().get("pool_root") or DEFAULT_POOL_ROOT
    return os.path.abspath(os.path.expanduser(root))


def resolve_basepath(explicit):
    # platform dir inside the pool (holds config.json); --basepath wins
    if explicit:
        return get_path(explicit)
    return os.path.join(resolve_pool_root(), detect_platform())


def load_config(ctx):
    # lazy config load shared by add/upload/download
    basepath = resolve_basepath(ctx.obj.get("basepath_opt"))
    config_path = os.path.join(basepath, "config.json")
    if not os.path.isfile(config_path):
        raise click.ClickException(
            f"config not found: {config_path}\n"
            f"Run `cfglink path` to check the pool directory."
        )
    with open(config_path, "r") as f:
        config = json.load(f)
    return config, basepath, config_path


def replace_with_symlink(src, dst):
    # backup dst (if it has real content), remove it, then symlink dst -> src;
    # on symlink failure restore dst from the backup so nothing is lost
    backup = dst + ".bak"
    while os.path.exists(backup):
        backup += ".bak"
    general_copy(dst, backup)
    if os.path.exists(backup):
        print(f"Backup file {backup} created")
    remove_path(dst)
    try:
        os.symlink(src, dst, os.path.isdir(src))
    except OSError as e:
        if os.path.exists(backup):
            general_copy(backup, dst)
            print(f"Live file restored from {backup}")
        raise click.ClickException(
            f"symlink failed: {e}\n"
            "Windows: enable Developer Mode (Settings > Privacy & security >\n"
            "For developers), or run cfglink from an elevated shell.")
    print(f"Symlink created from {src=} to {dst=}")


def launch_code(path):
    # open a file/folder in VS Code via the `code` CLI; resolve the real
    # launcher (code.cmd on Windows) and pass args as a list to avoid
    # shell quoting issues
    exe = shutil.which("code.cmd") or shutil.which("code")
    if exe is None:
        print("Warning: `code` not found on PATH")
        return
    print(f"Opening in VS Code: {path}")
    argv = ["cmd", "/c", exe, path] if exe.endswith(".cmd") else [exe, path]
    try:
        subprocess.Popen(argv)
    except OSError as e:
        print(f"Warning: failed to launch VS Code: {e}")


def ask_select(title, choices):
    # arrow-key menu via questionary; numbered click prompt as fallback for
    # non-console environments (pipes, mintty without winpty, ...)
    try:
        answer = questionary.select(title, choices=choices).ask()
        if answer is not None:
            return answer
        return None  # cancelled (Ctrl-C / Ctrl-D)
    except Exception:
        pass
    print(title)
    for i, c in enumerate(choices, 1):
        print(f"  {i}) {c}")
    idx = click.prompt("Select", type=click.IntRange(1, len(choices)), default=1)
    return choices[idx - 1]


def ask_path_input(title):
    # path input with completion via questionary; plain prompt fallback
    try:
        answer = questionary.path(title).ask()
        if answer is not None:
            return answer
        return None
    except Exception:
        pass
    return click.prompt(title)


@click.group()
@click.option("--basepath", default=None,
              help="pool platform dir (default: <pool_root>/<platform>)")
@click.pass_context
def main(ctx, basepath):
    ctx.ensure_object(dict)
    ctx.obj["basepath_opt"] = basepath


@main.command()
@click.argument("dst")
@click.option("-c", "--category", default=None,
              help="pool category dir (default: guess from filename)")
@click.pass_context
def add(ctx, dst, category):
    """Adopt DST: copy it into the pool, symlink it back, record it."""
    config, basepath, config_path = load_config(ctx)
    dst_path = get_path(dst)

    if os.path.islink(dst_path):
        raise click.ClickException(f"{dst_path} is already a symlink")
    if not os.path.exists(dst_path):
        raise click.ClickException(f"not found: {dst_path}")

    # refuse if this dst is already managed
    for items in config.values():
        for item in items:
            if get_path(item["dst"]) == dst_path:
                raise click.ClickException(
                    f"already managed as: {item['src']}")

    name = os.path.basename(dst_path)
    cat = category or guess_category(name)
    src_rel = f"{cat}/{name}"
    src = os.path.join(basepath, cat, name)

    # copy the live file into the pool
    if os.path.lexists(src):
        if os.path.isfile(src) and os.path.isfile(dst_path) and same_content(src, dst_path):
            print(f"Pool already has an identical {src_rel}")
        else:
            raise click.ClickException(f"pool file exists and differs: {src}")
    else:
        os.makedirs(os.path.dirname(src), 0o755, exist_ok=True)
        general_copy(dst_path, src)

    # backup the live file, then replace it with a symlink
    replace_with_symlink(src, dst_path)

    # record the entry
    config.setdefault(cat, []).append({"src": src_rel, "dst": dst_path})
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
        f.write("\n")
    print(f"Config updated: {config_path}")

    launch_code(config_path)


@main.command()
@click.pass_context
def upload(ctx):
    """Copy live files (dst) into the pool (src)."""
    config, basepath, _ = load_config(ctx)
    for items in config.values():
        for item in items:
            src = get_path(os.path.join(basepath, item["src"]))
            dst = get_path(item["dst"])
            parent = os.path.dirname(src)  # find parent path of src
            if not os.path.exists(parent):
                os.makedirs(parent, 0o755, True)  # mkdir -p
                print(f"Parent path {parent} created")
            general_copy(dst, src)


@main.command()
@click.pass_context
def download(ctx):
    """Replace live files (dst) with symlinks into the pool (src)."""
    config, basepath, _ = load_config(ctx)
    for items in config.values():
        for item in items:
            src = get_path(os.path.join(basepath, item["src"]))
            dst = get_path(item["dst"])

            if not os.path.exists(dst) and not os.path.islink(dst):
                parent = os.path.dirname(dst)  # find parent path of dst
                if not os.path.exists(parent):
                    os.makedirs(parent, 0o755, True)  # mkdir -p
                    print(f"Parent path {parent} created")
                os.symlink(src, dst, os.path.isdir(src))
                print(f"Symlink created from {src=} to {dst=}")
            else:
                replace_with_symlink(src, dst)


@main.command(name="open")
@click.pass_context
def open_pool(ctx):
    """Open the pool root folder in VS Code."""
    if ctx.obj.get("basepath_opt"):
        launch_code(resolve_basepath(ctx.obj["basepath_opt"]))
    else:
        launch_code(resolve_pool_root())


@main.command()
def path():
    """Show pool paths and optionally change the pool directory."""
    root = resolve_pool_root()
    plat = detect_platform()
    basepath = os.path.join(root, plat)
    print(f"pool root : {root}")
    print(f"platform  : {plat} -> {basepath}")
    print(f"config    : {os.path.join(basepath, 'config.json')}")
    print(f"settings  : {SETTINGS_PATH}")

    choice = ask_select(
        "Change pool directory?",
        ["Keep current", "Change directory", "Reset to default"],
    )
    if choice is None or choice == "Keep current":
        return

    if choice == "Reset to default":
        new_root = DEFAULT_POOL_ROOT
    else:
        new_root = ask_path_input("New pool root (~ allowed):")
        if new_root is None:
            return
        new_root = os.path.abspath(os.path.expanduser(new_root))

    if not os.path.isdir(new_root):
        raise click.ClickException(f"not a directory: {new_root}")
    save_settings({"pool_root": new_root})
    print(f"Pool root saved: {new_root}")
    new_base = os.path.join(new_root, plat)
    if not os.path.isfile(os.path.join(new_base, "config.json")):
        print(f"Warning: {os.path.join(new_base, 'config.json')} not found; "
              f"create it before add/upload/download.")


if __name__ == "__main__":
    main()
