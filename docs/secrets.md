# Secrets Configuration: BUMP_PAT

## Purpose

The `BUMP_PAT` secret is required by the automated release workflows to create pull requests that trigger CI checks.

**Why a PAT instead of GITHUB_TOKEN?** GitHub's built-in `GITHUB_TOKEN` cannot be used for PR creation because PRs opened by it do not trigger CI checks. Under branch protection rules that require "All Checks" to pass, these PRs would be permanently unmergeable.

## Creating BUMP_PAT

1. Go to **GitHub Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
2. Click **Generate new token**
3. Set the following:
   - **Token name**: `anvil-bump-pat`
   - **Repository access**: Only select repositories → select `shapeandshare/anvil`
   - **Permissions**:
     - Contents: **Read and write**
     - Pull requests: **Read and write**
     - Workflows: **Read and write**
4. Click **Generate token**
5. Copy the generated token

## Adding to Repository Secrets

1. Go to **GitHub repository** → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. **Name**: `BUMP_PAT`
4. **Secret**: Paste the token you generated
5. Click **Add secret**

## Verification

To verify the secret is configured correctly:

1. Trigger a workflow run manually via **Actions** → **Release** → **Run workflow**
2. The first step will check for `BUMP_PAT` and fail with a clear diagnostic if it's missing

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Workflow fails with "BUMP_PAT secret is missing" | Secret not configured | Follow "Adding to Repository Secrets" above |
| PR created but CI doesn't run | Wrong token type used | Ensure it's a **fine-grained PAT**, not a classic token |
| Auto-merge PR stays open | Branch protection requires review | Disable "Require pull request reviews before merging" or add an exception for CI bump PRs |
| Token expired | PATs have configurable expiration | Regenerate and update the secret |