PINK TRIANGLE PORTRAITS — AUTOMATIC CONTENT FIX

Upload only these paths into the existing GitHub repository:
  scripts/build.py
  .pages.yml

No images, biographies, or assets need uploading.

PORTRAITS
- The homepage featured portrait and five-person preview now rank by the saved
  featured_at date in each biography, NOT Git timestamps.
- Richard Plant already has featured_at: 2026-11-11 and will rank ahead of
  all older undated biographies.
- Existing undated biographies are not assigned invented dates.
- The existing GitHub Action stamp-new-biographies.yml adds a date to a newly
  CREATED biography if the CMS did not supply one. It does not restamp edits.
- If a newly added portrait does not appear immediately, check whether its
  featured_at field was populated and whether Cloudflare deployed the follow-up
  GitHub Actions commit. This must be tested live.
- To feature an older portrait manually, use homepage_override in the CMS.

PRESS
- Press lists sort by the saved article publication date.
- The homepage spotlight evaluates press dates in the visitor browser.
- homepage_priority=true intentionally pins an article indefinitely until
  manually turned off; homepage_until or homepage_days controls expiration
  otherwise. No Git history dependency.

EVENTS
- Event cards and the homepage event banner are generated during a site build.
  Consequently an event ending does not automatically update the static banner
  or upcoming/past lists until another deployment occurs. The homepage
  spotlight does use visitor-time date checks.
- No published event currently exists in this ZIP; example-event is unpublished.
- A separate scheduled rebuild or client-side event-list enhancement is needed
  for hands-free day-to-day event rollover without a CMS save/deployment.

IMPORTANT: This patch fixes the portrait ranking deterministically but does
NOT claim that the events page is already fully date-automatic. Test the
Cloudflare production deployment after committing these two files.
