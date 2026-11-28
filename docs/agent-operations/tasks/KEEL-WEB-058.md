# KEEL-WEB-058 — Purge tracked website/.next artifacts (fixes red main)

## Status: COMPLETED

WEB-055 removed website/ sources but left 215 tracked build artifacts
(.next/, tsbuildinfo, test-results, next-env.d.ts) — gitignored paths that
stay tracked once committed. Nine Next manifest files tripped gitleaks
generic-api-key, breaking the CI secret gate on main. Removed all stale
tracked output; hardened .gitignore (.next/, *.tsbuildinfo, test-results/)
matching the parallel worktree's identical conclusion. CI green including
both pytest legs + gitleaks.
