# Pink Triangle Portraits — Website Starter (Version 1)

This is a **real static website starter**, not just a screenshot. It is designed for GitHub + Cloudflare Pages + Pages CMS. It includes an editable content model, responsive layout, search, and generated individual portrait pages.

## Preview locally

1. Install Python 3 and run `pip install -r requirements.txt` in this folder.
2. Run `python scripts/build.py`.
3. Run `python -m http.server 8000 --directory dist`.
4. Open `http://localhost:8000` in your browser.

Do not open `dist/index.html` by double-clicking: the site uses root-relative paths and needs a local web server.

## Publish to a NEW GitHub repository and Cloudflare Pages project

Do **not** replace Bry's existing site or the live Pink Triangle Portraits site.

- Create a new repository and upload the contents of this folder (including `.pages.yml`).
- Create a new Cloudflare Pages project connected to that repository.
- Build command: `pip install -r requirements.txt && python scripts/build.py`
- Output directory: `dist`
- Once published, connect that GitHub repository to Pages CMS and authorize it.
- Keep the temporary `*.pages.dev` URL until the replacement is approved.

## Editing content

- `content/portraits/*.md`: one entry per portrait. The latest published portrait is featured automatically; checking **Feature on homepage** overrides this (latest checked portrait wins). Uncheck older ones if you want only one manual choice.
- `content/pages/*.md`: Project, History, Contact, Shop, and Artist pages. Markdown images can be inserted in the rich-text body.
- `content/events/*.md`: published events appear on the Exhibitions page. The nearest upcoming event appears on the homepage.
- `assets/uploads/`: user-uploaded images managed by Pages CMS.
- `assets/images/`: demonstration imagery and texture; replace with approved art and properly licensed images before launch.

## Before launch

- Replace all **Sample Portrait** records with approved names, artwork, biographies, and sources.
- Review the History page for historical accuracy and source citations.
- Replace the sample hero portrait strip with Bry's chosen images or custom banner.
- Add the real Square shop link, social profiles, and a working contact form.
- Confirm image permissions and accessibility descriptions.
- Set the actual domain only after testing.

This starter intentionally does not invent historical biographies, event dates, shop URLs, or a contact form recipient.
