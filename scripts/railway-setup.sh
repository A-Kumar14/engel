#!/usr/bin/env bash
# Engel — Railway API + Postgres setup (run after: railway login)
set -euo pipefail

echo "Engel Railway setup"
echo "==================="
echo ""
echo "1. Create Railway project 'engel'"
echo "2. Add Postgres plugin"
echo "3. Add web service from this repo, root directory: backend"
echo "4. Reference DATABASE_URL from Postgres in the web service"
echo ""

if ! railway whoami &>/dev/null; then
  echo "Run: railway login"
  exit 1
fi

read -rsp "RESEND_API_KEY: " RESEND_API_KEY; echo
read -rp "WAITLIST_FROM_EMAIL (e.g. Engel <hello@domain.com>): " WAITLIST_FROM_EMAIL
read -rp "PUBLIC_API_BASE_URL (Railway URL, no trailing slash): " PUBLIC_API_BASE_URL

railway variables set \
  "RESEND_API_KEY=${RESEND_API_KEY}" \
  "WAITLIST_FROM_EMAIL=${WAITLIST_FROM_EMAIL}" \
  "PUBLIC_API_BASE_URL=${PUBLIC_API_BASE_URL}" \
  "CORS_ORIGINS=https://a-kumar14.github.io,http://127.0.0.1:8080,http://localhost:8080" \
  "WAITLIST_SUCCESS_URL=https://a-kumar14.github.io/engel/confirmed.html" \
  "ENV=prod"

echo ""
echo "Deploy: git push origin main (or railway up)"
echo "Migrate Render data: see DEPLOYMENT.md pg_dump/psql steps"
