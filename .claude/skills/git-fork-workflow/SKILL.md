---
name: git-fork-workflow
description: Git workflow for contributing to this repository via fork. Use when creating commits, branches, or pull requests.
---

# Git Fork Workflow

This repository uses a fork-based contribution model:

- **origin**: Points to the contributor's fork (e.g., `username/commcare-sync`)
- **upstream**: Points to the main repository (`dimagi/commcare-sync`)

Contributors do NOT have write access to the main repository, only to their fork.

## Creating Pull Requests

1. Create a feature branch from the current branch
2. Make and commit changes
3. Push the branch to `origin` (your fork)
4. Create a PR targeting the upstream repo

```bash
git checkout -b fix/descriptive-branch-name
git add <files>
git commit -m "Commit message"
git push -u origin fix/descriptive-branch-name
gh pr create --repo dimagi/commcare-sync --title "PR Title" --body "Description"
```

Never attempt to push directly to `dimagi/commcare-sync` - use PRs from your fork.
