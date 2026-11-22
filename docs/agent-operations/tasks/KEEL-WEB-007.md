# KEEL-WEB-007 — web-next shared chrome + /docs

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-007
- **TASK TITLE**: Shared header/footer + /docs port on web-next
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-web-007-site-chrome-docs

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Sticky SiteHeader (mark, primary nav with aria-current, mobile menu, GitHub link) + SiteFooter mounted in root layout
- [x] /docs ported — same 4 groups / 15 doc rows as website, linked to GitHub blob paths + live install.sh
- [x] Home buttons wired to real destinations (Get started → repo README, Read the docs → /docs); dead buttons removed
- [x] /docs added to e2e ROUTES; axe caught a real label-content-name-mismatch on the home link (aria-label must contain visible K′ text) → fixed to literal prime
- [x] typecheck + build green, 4/4 e2e pass

#### NEXT RECOMMENDED ACTION
- Port /product or /changelog next; nav extends by editing NAV in header.tsx.
