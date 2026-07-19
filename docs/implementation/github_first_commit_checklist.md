# GitHub First Commit Checklist

Use this checklist before creating the first GitHub commit for `cata-email-assistant`.

## Repo safety

- Confirm the local path is `/Users/williamherridge/Documents/repos/cata-email-assistant`.
- Confirm the current branch name is acceptable for the initial commit strategy.
- Confirm Git user name and email are correct for the first commit author.
- Confirm no unexpected remotes are configured.
- Confirm ignored local secrets and local data remain excluded from version control.

## Sensitive-path verification

- Keep `config/credentials.json` ignored.
- Keep `config/token.json` ignored.
- Keep `data/raw/*` ignored.
- Keep `data/processed/*` ignored.
- Keep `data/analytics/taxonomy_discovery/*` ignored.
- Keep any future local secret or token variants ignored through wildcard rules.

## Content verification

- Confirm no TennisLink files remain in the repository.
- Confirm no TennisLink references remain in docs, code, data, or web assets.
- Confirm the repository name is consistently `cata-email-assistant` in visible docs.
- Confirm the architecture baseline reflects the approved MVP scope.

## First commit contents

Recommended first commit scope:

- requirements and architecture docs
- exploratory Gmail ingestion helpers
- taxonomy exploration utilities
- local development examples and non-sensitive manifests
- repository hygiene such as `.gitignore`, `README.md`, and dependency manifests

Avoid including:

- OAuth credentials
- OAuth tokens
- local Gmail export data
- processed local analytics artifacts
- throwaway OS metadata files if they can be excluded cleanly

## GitHub bootstrap steps

When ready:

1. Create the GitHub repository.
2. Add the remote.
3. Review the staged file list carefully.
4. Create the first commit.
5. Push the initial branch.
6. Protect the default branch after the initial publish if desired.

## Immediate next architecture work

After the first commit lands:

1. Choose the first hosted runtime target: `App Runner` or `ECS Fargate`.
2. Draft the initial relational schema for messages, analysis, drafts, and audit events.
3. Choose the portal framework and application packaging approach.
4. Define the background job boundaries for poll, analyze, prework, and draft steps.
5. Write the first implementation backlog from the approved architecture baseline.
