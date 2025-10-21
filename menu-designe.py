#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified GitHub Manager — Full (All Features)
 - Uses /home/gost/account/.env for GITHUB_TOKEN
 - Workspace: /home/gost/7heBlackLand
 - Logs: /home/gost/all-project/git-all/git_actions.log
 - Implements create/rename/delete/settings/upload/clone/pull/push/sync for repos
 - Auto-sets git identity to avoid "Author identity unknown"
"""

from __future__ import annotations
import os
import sys
import subprocess
import shutil
from typing import Optional, List
from datetime import datetime

# ---------------------------
# Auto-install missing deps (best-effort)
# ---------------------------
REQS = {
    "git": "GitPython",
    "github": "PyGithub",
    "dotenv": "python-dotenv",
    "rich": "rich",
    "requests": "requests",
}
for mod, pkg in REQS.items():
    try:
        __import__(mod)
    except Exception:
        print(f"[info] Installing missing package: {pkg} ...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        except Exception as e:
            print(f"[warn] Auto-install failed for {pkg}: {e}")

# ---------------------------
# Imports
# ---------------------------
try:
    from dotenv import load_dotenv
    from github import Github, Auth, GithubException, Repository
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.panel import Panel
except Exception as e:
    print("Missing required libraries:", e)
    sys.exit(1)

# ---------------------------
# Configuration (user paths)
# ---------------------------
ENV_PATH = "/home/gost/account/.env"
WORKSPACE = "/home/gost/7heBlackLand"
LOG_FILE = "/home/gost/all-project/git-all/git_actions.log"
DEFAULT_COMMIT_MSG = "Auto sync via Unified Manager"
DEFAULT_GIT_NAME = "7heBlackLand Bot"
DEFAULT_GIT_EMAIL = "bot@7heblackland.dev"

console = Console()

# Load environment
load_dotenv(dotenv_path=ENV_PATH)
TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    console.print("[bold red]Missing GITHUB_TOKEN in .env at /home/gost/account/.env[/bold red]")
    sys.exit(1)

# Authenticate GitHub
try:
    gh = Github(auth=Auth.Token(TOKEN))
    user = gh.get_user()
    console.print(f"✅ Authenticated as: [green]{user.login}[/green]\n")
except Exception as e:
    console.print(f"[bold red]GitHub authentication failed: {e}[/bold red]")
    sys.exit(1)


# ---------------------------
# Helpers
# ---------------------------
def log_action(msg: str):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def run(cmd: List[str], cwd: Optional[str] = None, silent: bool = False):
    if not silent:
        console.print(f"🚀 {' '.join(cmd)}  (cwd={cwd or os.getcwd()})")
    subprocess.run(cmd, cwd=cwd, check=True)


def safe_run(cmd: List[str], cwd: Optional[str] = None, silent: bool = False) -> bool:
    """Run command and return True on success, False on failure."""
    try:
        run(cmd, cwd=cwd, silent=silent)
        return True
    except subprocess.CalledProcessError:
        return False


# ---------------------------
# Ensure global git identity
# ---------------------------
def ensure_global_identity():
    try:
        name = subprocess.check_output(["git", "config", "--global", "user.name"], text=True).strip()
        email = subprocess.check_output(["git", "config", "--global", "user.email"], text=True).strip()
        if name and email:
            return
    except subprocess.CalledProcessError:
        pass

    console.print(f"⚙️ Setting global git identity to: {DEFAULT_GIT_NAME} <{DEFAULT_GIT_EMAIL}>")
    try:
        subprocess.run(["git", "config", "--global", "user.name", DEFAULT_GIT_NAME], check=False)
        subprocess.run(["git", "config", "--global", "user.email", DEFAULT_GIT_EMAIL], check=False)
        log_action(f"Set global git identity: {DEFAULT_GIT_NAME} <{DEFAULT_GIT_EMAIL}>")
    except Exception:
        pass


ensure_global_identity()


# ---------------------------
# GitHub helpers
# ---------------------------
def list_repos(limit: int = 1000) -> List[Repository.Repository]:
    try:
        return list(user.get_repos())[:limit]
    except Exception as e:
        console.print(f"[red]Failed to fetch repos: {e}[/red]")
        return []


def find_repo_by_name(name: str) -> Optional[Repository.Repository]:
    try:
        return gh.get_repo(f"{user.login}/{name}")
    except GithubException:
        for r in list_repos():
            if r.name == name:
                return r
    except Exception:
        pass
    return None


def fix_remote_with_token(repo_path: str):
    try:
        origin = subprocess.check_output(["git", "-C", repo_path, "remote", "get-url", "origin"], text=True).strip()
        if origin.startswith("https://") and "@" not in origin:
            new = origin.replace("https://", f"https://{TOKEN}@")
            safe_run(["git", "-C", repo_path, "remote", "set-url", "origin", new], silent=True)
            log_action(f"Updated remote for {repo_path}")
    except Exception:
        pass


# ---------------------------
# CRUD: Create / Rename / Delete / Settings
# ---------------------------
def create_repo():
    name = Prompt.ask("Repository name (no spaces)").strip()
    if not name:
        console.print("[red]Repository name required[/red]")
        return
    description = Prompt.ask("Description", default="")
    private = Confirm.ask("Private repository?", default=False)
    try:
        repo = user.create_repo(name=name, description=description, private=private)
        console.print(f"[green]Created {repo.full_name}[/green]")
        log_action(f"Created repo {repo.full_name} private={private}")
    except GithubException as e:
        console.print(f"[red]GitHub error: {e.data.get('message', str(e))}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to create repo: {e}[/red]")


def rename_repo():
    repos = list_repos()
    if not repos:
        console.print("[red]No repos found[/red]")
        return
    table = Table(title="Select repo to rename")
    table.add_column("No", style="cyan")
    table.add_column("Name", style="bold")
    for i, r in enumerate(repos, 1):
        table.add_row(str(i), r.name)
    console.print(table)
    sel = Prompt.ask("Select repo number").strip()
    try:
        idx = int(sel) - 1
        repo = repos[idx]
        new_name = Prompt.ask("New repository name").strip()
        if not new_name:
            console.print("[red]Name required[/red]")
            return
        repo.edit(name=new_name)
        console.print(f"[green]Renamed to {new_name}[/green]")
        log_action(f"Renamed {repo.full_name} -> {new_name}")
    except Exception as e:
        console.print(f"[red]Error renaming repo: {e}[/red]")


def delete_repo():
    repos = list_repos()
    if not repos:
        console.print("[red]No repos found[/red]")
        return
    table = Table(title="Select repo to delete")
    table.add_column("No", style="cyan")
    table.add_column("Name", style="bold")
    for i, r in enumerate(repos, 1):
        table.add_row(str(i), r.name)
    console.print(table)
    sel = Prompt.ask("Select repo number to DELETE").strip()
    try:
        idx = int(sel) - 1
        repo = repos[idx]
        ok = Confirm.ask(f"Are you sure you want to DELETE {repo.full_name}? This is irreversible.", default=False)
        if not ok:
            console.print("Cancelled.")
            return
        gh.get_user().delete_repo(repo.name)
        console.print(f"[green]Deleted {repo.full_name}[/green]")
        log_action(f"Deleted repo {repo.full_name}")
    except Exception as e:
        console.print(f"[red]Failed to delete repo: {e}[/red]")


def repo_settings():
    repos = list_repos()
    if not repos:
        console.print("[red]No repos found[/red]")
        return
    table = Table(title="Select repo to manage")
    table.add_column("No", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Visibility", justify="center")
    for i, r in enumerate(repos, 1):
        vis = "Private" if r.private else "Public"
        table.add_row(str(i), r.name, vis)
    console.print(table)
    sel = Prompt.ask("Select repo number").strip()
    try:
        idx = int(sel) - 1
        repo = repos[idx]
    except Exception:
        console.print("[red]Invalid selection[/red]")
        return

    console.print("1) Rename repo")
    console.print("2) Change visibility (public/private)")
    console.print("3) Transfer ownership (not implemented in this version)")
    console.print("4) Delete repo")
    console.print("5) Cancel")
    action = Prompt.ask("Choose action (1-5)", default="5").strip()

    if action == "1":
        new_name = Prompt.ask("New name").strip()
        if new_name:
            try:
                repo.edit(name=new_name)
                console.print(f"[green]Renamed to {new_name}[/green]")
                log_action(f"Renamed {repo.full_name} -> {new_name}")
            except Exception as e:
                console.print(f"[red]Rename failed: {e}[/red]")
    elif action == "2":
        to_private = Confirm.ask("Make private? Yes = private, No = public", default=repo.private)
        try:
            repo.edit(private=to_private)
            console.print(f"[green]Visibility set to {'Private' if to_private else 'Public'}[/green]")
            log_action(f"Set visibility {repo.full_name} -> private={to_private}")
        except Exception as e:
            console.print(f"[red]Failed to change visibility: {e}[/red]")
    elif action == "4":
        ok = Confirm.ask(f"DELETE {repo.full_name}? (irreversible)", default=False)
        if ok:
            try:
                gh.get_user().delete_repo(repo.name)
                console.print(f"[green]Deleted {repo.full_name}[/green]")
                log_action(f"Deleted {repo.full_name}")
            except Exception as e:
                console.print(f"[red]Delete failed: {e}[/red]")
    else:
        console.print("Cancelled.")


# ---------------------------
# Upload a local folder or file via git push
# ---------------------------
def upload_local_folder():
    local_path = Prompt.ask("Local path to upload (file or folder)").strip()
    if not local_path:
        console.print("[red]Local path required[/red]")
        return
    local_path = os.path.abspath(os.path.expanduser(local_path))
    if not os.path.exists(local_path):
        console.print("[red]Local path not found[/red]")
        return

    # If file: create temporary dir to initialize and push that file
    cleanup_tmp = False
    if os.path.isfile(local_path):
        tmpdir = os.path.join("/tmp", f"upload_{os.path.basename(local_path)}_{int(datetime.now().timestamp())}")
        os.makedirs(tmpdir, exist_ok=True)
        shutil.copy(local_path, os.path.join(tmpdir, os.path.basename(local_path)))
        repo_path = tmpdir
        cleanup_tmp = True
    else:
        repo_path = local_path

    # Initialize git repo if not present
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        try:
            run(["git", "init"], cwd=repo_path)
            run(["git", "config", "user.name", DEFAULT_GIT_NAME], cwd=repo_path)
            run(["git", "config", "user.email", DEFAULT_GIT_EMAIL], cwd=repo_path)
        except Exception as e:
            console.print(f"[red]Failed to init repo: {e}[/red]")
            if cleanup_tmp:
                shutil.rmtree(repo_path, ignore_errors=True)
            return

    console.print("Destination:")
    console.print("1) Existing repo in your account")
    console.print("2) Create new repo and push")
    dest_choice = Prompt.ask("Choose (1-2)", default="2").strip()

    dest_repo = None
    if dest_choice == "1":
        repos = list_repos()
        table = Table(title="Your repositories")
        table.add_column("No", style="cyan")
        table.add_column("Name", style="bold")
        for i, r in enumerate(repos, 1):
            table.add_row(str(i), r.name)
        console.print(table)
        sel = Prompt.ask("Select repo number").strip()
        try:
            idx = int(sel) - 1
            dest_repo = repos[idx]
        except Exception:
            console.print("[red]Invalid selection[/red]")
            if cleanup_tmp:
                shutil.rmtree(repo_path, ignore_errors=True)
            return
    else:
        name = Prompt.ask("New repo name").strip()
        if not name:
            console.print("[red]Name required[/red]")
            if cleanup_tmp:
                shutil.rmtree(repo_path, ignore_errors=True)
            return
        desc = Prompt.ask("Description", default="")
        private = Confirm.ask("Private?", default=False)
        try:
            dest_repo = user.create_repo(name=name, description=desc, private=private)
            console.print(f"[green]Created repo {dest_repo.full_name}[/green]")
            log_action(f"Created repo {dest_repo.full_name} for upload")
        except Exception as e:
            console.print(f"[red]Failed to create repo: {e}[/red]")
            if cleanup_tmp:
                shutil.rmtree(repo_path, ignore_errors=True)
            return

    # Prepare remote (use token in URL for push)
    clone_url = dest_repo.clone_url
    if clone_url.startswith("https://") and "@" not in clone_url:
        remote_url = clone_url.replace("https://", f"https://{TOKEN}@")
    else:
        remote_url = clone_url

    # Remove origin if exists, then add
    try:
        run(["git", "-C", repo_path, "remote", "remove", "origin"], silent=True)
    except Exception:
        pass
    try:
        run(["git", "-C", repo_path, "remote", "add", "origin", remote_url])
    except Exception as e:
        console.print(f"[red]Failed to add remote: {e}[/red]")
        if cleanup_tmp:
            shutil.rmtree(repo_path, ignore_errors=True)
        return

    branch = Prompt.ask("Branch to push to", default="main").strip()
    try:
        run(["git", "-C", repo_path, "add", "."], silent=True)
        # commit if any changes
        c = subprocess.run(["git", "-C", repo_path, "commit", "-m", "Upload via Unified Manager"])
        # ensure branch
        run(["git", "-C", repo_path, "checkout", "-B", branch], silent=True)
        run(["git", "-C", repo_path, "push", "-u", "origin", branch])
        console.print(f"[green]Pushed content to {dest_repo.full_name}:{branch}[/green]")
        log_action(f"Uploaded {repo_path} -> {dest_repo.full_name}:{branch}")
    except Exception as e:
        console.print(f"[red]Push failed: {e}[/red]")

    if cleanup_tmp:
        shutil.rmtree(repo_path, ignore_errors=True)


# ---------------------------
# Clone to workspace (one / multiple / all)
# ---------------------------
def clone_to_workspace():
    os.makedirs(WORKSPACE, exist_ok=True)
    repos = list_repos()
    if not repos:
        console.print("[red]No repos found[/red]")
        return

    console.print(Panel("[bold cyan]Clone to Workspace[/bold cyan]"))
    console.print("1) Clone ALL")
    console.print("2) Choose specific (by number)")
    console.print("3) Cancel")
    ch = Prompt.ask("Choice", default="3").strip()

    to_clone = []
    if ch == "1":
        to_clone = repos
    elif ch == "2":
        table = Table(title="Repositories")
        table.add_column("No", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Visibility", justify="center")
        for i, r in enumerate(repos, 1):
            vis = "Private 🔒" if r.private else "Public 🌍"
            table.add_row(str(i), r.name, vis)
        console.print(table)
        raw = Prompt.ask("Enter numbers (comma-separated)").strip()
        try:
            nums = [int(x.strip()) for x in raw.split(",") if x.strip()]
            to_clone = [repos[n - 1] for n in nums if 1 <= n <= len(repos)]
        except Exception:
            console.print("[red]Invalid input[/red]")
            return
    else:
        return

    for r in to_clone:
        dst = os.path.join(WORKSPACE, r.name)
        if os.path.exists(dst):
            console.print(f"⚠️ Already exists, skipping: {r.name}")
            fix_remote_with_token(dst)
            continue
        url = r.clone_url
        if url.startswith("https://") and "@" not in url:
            url = url.replace("https://", f"https://{TOKEN}@")
        console.print(f"Cloning {r.full_name} ...")
        try:
            run(["git", "clone", url, dst], silent=True)
            fix_remote_with_token(dst)
            console.print(f"[green]Cloned {r.name}[/green]")
            log_action(f"Cloned {r.full_name} -> {dst}")
        except Exception as e:
            console.print(f"[red]Failed to clone {r.name}: {e}[/red]")


# ---------------------------
# Batch workspace manager: pull / push / sync
# ---------------------------
def batch_workspace_manager():
    if not os.path.isdir(WORKSPACE):
        console.print(f"[red]Workspace missing: {WORKSPACE}[/red]")
        return
    dirs = sorted([d for d in os.listdir(WORKSPACE) if os.path.isdir(os.path.join(WORKSPACE, d))])
    dirs = [d for d in dirs if os.path.isdir(os.path.join(WORKSPACE, d, ".git"))]
    if not dirs:
        console.print("[red]No git repos in workspace[/red]")
        return

    console.print(Panel("[bold green]Batch Workspace Manager[/bold green]"))
    console.print("1) Pull all")
    console.print("2) Push all")
    console.print("3) Sync all (pull then push)")
    console.print("4) Back")
    choice = Prompt.ask("Enter (1-4)", default="4").strip()
    if choice == "4":
        return

    commit_msg = DEFAULT_COMMIT_MSG
    if choice in ("2", "3"):
        commit_msg = Prompt.ask("Commit message", default=commit_msg)

    for repo_name in dirs:
        path = os.path.join(WORKSPACE, repo_name)
        console.print(f"\n📂 {repo_name}")
        fix_remote_with_token(path)
        try:
            if choice in ("1", "3"):
                run(["git", "-C", path, "pull"], silent=True)
                log_action(f"Pulled {repo_name}")
            if choice in ("2", "3"):
                run(["git", "-C", path, "add", "."], silent=True)
                c = subprocess.run(["git", "-C", path, "commit", "-m", commit_msg])
                if c.returncode == 0:
                    run(["git", "-C", path, "push"], silent=True)
                    console.print("[green]Pushed[/green]")
                    log_action(f"Pushed {repo_name}")
                else:
                    console.print("ℹ️ Nothing to commit")
        except Exception as e:
            console.print(f"[red]Failed for {repo_name}: {e}[/red]")
            log_action(f"Error {repo_name}: {e}")

    console.print("\n✨ Batch operations completed.\n")


# ---------------------------
# Per-repo local manager
# ---------------------------
def per_repo_manager():
    path = Prompt.ask("Local repository path (default)", default=WORKSPACE).strip()
    path = os.path.abspath(os.path.expanduser(path))

    # If not a git repo, offer to clone to this path
    if not os.path.isdir(path) or not os.path.isdir(os.path.join(path, ".git")):
        console.print(f"Path is not a git repo: {path}")
        if not Confirm.ask("Clone a repo here from your account?", default=False):
            return
        # choose repo and clone
        repos = list_repos()
        table = Table(title="Select repo to clone here")
        table.add_column("No", style="cyan")
        table.add_column("Name", style="bold")
        for i, r in enumerate(repos, 1):
            table.add_row(str(i), r.name)
        console.print(table)
        sel = Prompt.ask("Select repo number").strip()
        try:
            idx = int(sel) - 1
            repo = repos[idx]
            url = repo.clone_url
            if url.startswith("https://") and "@" not in url:
                url = url.replace("https://", f"https://{TOKEN}@")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            run(["git", "clone", url, path])
            fix_remote_with_token(path)
            console.print(f"[green]Cloned {repo.name} -> {path}[/green]")
            log_action(f"Cloned {repo.full_name} -> {path}")
        except Exception as e:
            console.print(f"[red]Clone failed: {e}[/red]")
            return

    # set repo-local identity
    try:
        run(["git", "-C", path, "config", "user.name", DEFAULT_GIT_NAME], silent=True)
        run(["git", "-C", path, "config", "user.email", DEFAULT_GIT_EMAIL], silent=True)
    except Exception:
        pass

    while True:
        console.print(Panel(f"Local Repo Manager — {path}"))
        console.print("1) Pull")
        console.print("2) Push")
        console.print("3) Sync (pull + push)")
        console.print("4) Back")
        ch = Prompt.ask("Choose (1-4)", default="4").strip()
        if ch == "1":
            try:
                run(["git", "-C", path, "pull"])
                console.print("[green]Pulled[/green]")
            except Exception as e:
                console.print(f"[red]Pull failed: {e}[/red]")
        elif ch == "2":
            msg = Prompt.ask("Commit message", default=DEFAULT_COMMIT_MSG)
            try:
                run(["git", "-C", path, "add", "."], silent=True)
                c = subprocess.run(["git", "-C", path, "commit", "-m", msg])
                if c.returncode == 0:
                    run(["git", "-C", path, "push"])
                    console.print("[green]Pushed[/green]")
                    log_action(f"Pushed local {path}")
                else:
                    console.print("ℹ️ Nothing to commit")
            except Exception as e:
                console.print(f"[red]Push failed: {e}[/red]")
        elif ch == "3":
            msg = Prompt.ask("Commit message", default=DEFAULT_COMMIT_MSG)
            try:
                run(["git", "-C", path, "pull"], silent=True)
                run(["git", "-C", path, "add", "."], silent=True)
                c = subprocess.run(["git", "-C", path, "commit", "-m", msg])
                if c.returncode == 0:
                    run(["git", "-C", path, "push"], silent=True)
                    console.print("[green]Synced[/green]")
                    log_action(f"Synced local {path}")
                else:
                    console.print("ℹ️ Nothing to sync")
            except Exception as e:
                console.print(f"[red]Sync failed: {e}[/red]")
        else:
            break


# ---------------------------
# Main menu (all functions)
# ---------------------------
def main_menu():
    while True:
        console.rule(f"[bold magenta]Your Repositories list (Authenticated as: {user.login})[/bold magenta]")
        repos = list_repos()
        table = Table()
        table.add_column("No", justify="center")
        table.add_column("Name", style="bold")
        table.add_column("Visibility", justify="center")
        for i, r in enumerate(repos, 1):
            vis = "Private 🔒" if r.private else "Public 🌍"
            table.add_row(str(i), r.name, vis)
        console.print(table)

        console.print("""
1) Create new repository
2) Rename repository
3) Delete repository
4) Repo settings (rename/visibility/delete)
5) Upload local folder via git push
6) Per-repo local manager (pull / push / sync)
7) Clone to workspace (one/multiple/all)
8) Batch workspace manager (pull / push / sync)
9) Exit
""")
        choice = Prompt.ask("Enter choice", default="9").strip()
        if choice == "1":
            create_repo()
        elif choice == "2":
            rename_repo()
        elif choice == "3":
            delete_repo()
        elif choice == "4":
            repo_settings()
        elif choice == "5":
            upload_local_folder()
        elif choice == "6":
            per_repo_manager()
        elif choice == "7":
            clone_to_workspace()
        elif choice == "8":
            batch_workspace_manager()
        elif choice == "9":
            console.print("[bold magenta]Exiting Unified Manager...[/bold magenta]")
            sys.exit(0)
        else:
            console.print("[yellow]Invalid option[/yellow]")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Interrupted. Exiting...[/bold yellow]")
        sys.exit(0)
