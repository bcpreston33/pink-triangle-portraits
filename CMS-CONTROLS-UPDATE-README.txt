PINK TRIANGLE PORTRAITS — CMS CONTROLS & EXHIBITIONS CLEANUP

INSTALL
1. Unzip this update and copy the FIVE replacement files into the same locations in your GitHub repository.
2. Replace existing versions, keeping the folders exactly as shown.
3. IMPORTANT: .pages.yml is a HIDDEN file on macOS. Press Command + Shift + Period in Finder to reveal hidden files.
4. Commit the changes and let Cloudflare Pages redeploy.
5. Refresh Pages CMS after deployment to see the new fields.

FILES
.pages.yml
scripts/build.py
assets/site.css
assets/site.js
CMS-CONTROLS-UPDATE-README.txt (this guide; optional, no need to upload)

WHERE TO EDIT
- Pages CMS > Homepage Design: Hero, rotating features, Project fallback text, rotating feature link labels, lower exhibition band, gallery teaser, lower press section.
- Pages CMS > Site pages > the-project: Right column, press typography, image sizes and thin dividers.
- Pages CMS > Press & Media: Article metadata, manual logo/thumbnail, per-article hide-image, homepage eligibility and duration.
- Pages CMS > Site pages > exhibitions: Main introduction and historical year-by-year content, plus featured column heading, empty message and visibility.
- Pages CMS > Exhibitions and events: Create new dated events, venue, address, opening reception, hours, featured checkbox, featured order, image, description and homepage eligibility.
- Pages CMS > Portraits & biographies: New portraits and optional homepage override.

EXHIBITIONS: IMPORTANT
Existing historical exhibition entries are preserved as editorial text in Site pages > exhibitions.
For NEW events, create an entry in Exhibitions and events. Do not also manually copy that event into the old year-by-year page text, or it will appear twice.
Featured upcoming events are displayed in the right column while also remaining in the left chronological list. After their end dates they remain in history, but leave the featured column.

WHAT IS AUTOMATIC
- Homepage spotlight priorities: upcoming exhibition, eligible recent press, latest portrait, Project fallback. Two or three columns.
- Exhibition event date classification and expiry, without republishing.
- Press expiry based on the article publication date, or its custom homepage duration/until date.
- Quarterly press link checking is unchanged.

NOT FULLY AUTOMATIC / LIMITATIONS
- Publication logo discovery is best-effort and may not work on all sites. You can always upload a manual logo or thumbnail.
- GitHub's issue email alerts depend on your GitHub notification settings.
- Historical exhibition text cannot be automatically converted into structured events without adding dates and fields.
- Date changes in CMS require saving/publishing once. Afterward the display date logic runs in the browser.
- The existing site has many global visual design settings; this update adds missing editorial controls and clarifies key labels rather than changing the established design.

TESTS
Python builder ran successfully with the existing 66 artworks and 61 people.
CMS YAML parsed successfully; JavaScript syntax checked.
A temporary future featured exhibition was built successfully and then removed before packaging.
Live Cloudflare deployment and visual browser QA have not been performed.
