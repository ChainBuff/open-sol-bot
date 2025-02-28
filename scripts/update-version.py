#!/usr/bin/env python3
import glob
import os
import re
import subprocess
import sys


def get_current_branch():
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], universal_newlines=True
        ).strip()
        return branch
    except subprocess.CalledProcessError:
        print("Error: Unable to get current branch.")
        sys.exit(1)


def replace_version(match, version):
    """替换匹配到的版本号"""
    before_quote = match.group(1)  # 获取第一个引号之前的所有内容
    return f'{before_quote}"{version}"'


def update_version_in_file(filepath, version):
    print(f"Processing {filepath}")
    with open(filepath) as f:
        content = f.read()

    # 只匹配 [project] 部分中的 version = "x.x.x"
    pattern = r'(\[project\](?:(?!\[).)*?version\s*=\s*)"[^"]+"'

    updated = False
    if re.search(pattern, content, re.MULTILINE | re.DOTALL):
        content = re.sub(
            pattern,
            lambda m: replace_version(m, version),
            content,
            flags=re.MULTILINE | re.DOTALL,
        )
        updated = True
    else:
        print(f"Warning: No [project] version field found in {filepath}")

    if updated:
        with open(filepath, "w") as f:
            f.write(content)

    return updated


def main():
    branch = get_current_branch()
    if not branch.startswith("release/"):
        print("Error: This script should be run on a release branch (e.g., release/0.1.8).")
        sys.exit(1)
    version = branch.split("release/")[-1]
    print(f"Current version: {version}")

    pyproject_files = [os.path.join("pyproject.toml")]
    for base in ["app", "libs"]:
        pattern = os.path.join(base, "*", "pyproject.toml")
        files_found = glob.glob(pattern)
        pyproject_files.extend(files_found)

    if not pyproject_files:
        print("No pyproject.toml files found in 'app' or 'libs' directories.")
        sys.exit(1)

    updated_files = []
    for filepath in pyproject_files:
        if update_version_in_file(filepath, version):
            updated_files.append(filepath)

    if updated_files:
        try:
            subprocess.run(["git", "add", *updated_files], check=True)
            commit_message = f"Update version to {version} in files: {', '.join(updated_files)}"
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
        except subprocess.CalledProcessError:
            print("Error: Git commit failed for updated files.")

    print("Version update complete.")


if __name__ == "__main__":
    main()
