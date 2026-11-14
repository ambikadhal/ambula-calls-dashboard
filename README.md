# Hindi calls dashboard
Daily: put the new Excel in `data/`, run `python3 update.py`, commit and push `index.html` + `dashboard.html`.
`update.py` merges all `data/*.xlsx` (de-duplicated by Call ID), recomputes the plan and writes `index.html` (field-team lookup, from `field.html`) and `dashboard.html` (team dashboard, from `tpl.html`).
The page shows referral codes only (no names, no phone numbers). Excel files are git-ignored.
