PINK TRIANGLE PORTRAITS — CMS REORGANIZATION

IMPORTANT: TEST ON STAGING. Back up your repository first.

1. Upload .pages.yml to the repository ROOT (replace existing .pages.yml).
2. Upload the 8 new files from content/settings/ into content/settings/.
3. Replace scripts/build.py and assets/site.css with supplied files.
4. Commit and wait for Cloudflare Pages deployment.
5. Refresh Pages CMS. It should show 8 separate design sections.
6. Verify the navigation includes The Artist, icon spacing, and 10px decorative rules.
7. Do NOT edit the old content/settings/site.yml. Once verified, delete that legacy file in GitHub to avoid two sources of truth.

IMPORTANT LIMITATION: This migration retains old build-script defaults for fields that were previously blank. Not all historical CSS overrides have been converted to live CMS controls. Some legacy controls may still be overridden by CSS and need visual QA. The site.yml file remains a fallback until you delete it.

No content pages, portrait records, or events are included or modified.
