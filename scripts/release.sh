#!/usr/bin/env bash
# Run manually on the chosen Linux host after CI passes. Intentionally not auto-deployed.
set -euo pipefail
cd "$(dirname "$0")/.."
node scripts/check-deploy.mjs deploy/.env.production
if test -n "$(git status --porcelain)"; then
  echo "Commit all source changes before building a release." >&2
  exit 1
fi
release_tag="$(node --input-type=module -e "import {readFileSync} from 'node:fs'; import {validateDeployment} from './scripts/check-deploy.mjs'; console.log(validateDeployment(readFileSync('deploy/.env.production','utf8')).RELEASE_TAG)")"
if test "$release_tag" != "$(git rev-parse HEAD)"; then
  echo "RELEASE_TAG must match the checked-out, tested commit." >&2
  exit 1
fi
compose=(docker compose --project-name rally-production --env-file deploy/.env.production -f compose.production.yaml)
"${compose[@]}" build
"${compose[@]}" up -d --wait db
# Small-club maintenance deployment: pause writes before backup and migrations.
"${compose[@]}" stop edge frontend api
node scripts/backup.mjs
"${compose[@]}" run --rm migrate
"${compose[@]}" up -d --wait
echo "Release services are running. Verify HTTPS, sign-in, and a test booking."
