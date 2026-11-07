# Measure in Chrome

The browser edition uses Python and Streamlit. It does not need Tkinter or a Mac.

## Free online hosting

1. Create a GitHub repository and upload the `measure` and `examples` folders, preserving their names and contents. Do not upload real assessment data, environments, or generated reports.
2. Sign in at https://share.streamlit.io using GitHub.
3. Choose **Create app**, select the repository and branch, and set **Main file path** to `measure/web_app.py`.
4. Deploy. Streamlit finds `measure/requirements.txt` beside the entry point and installs the dependencies. Choose Python 3.12 in advanced settings if selecting a version.
5. Open the resulting `https://...streamlit.app` URL in Google Chrome. Upload or paste your scores to start.

Streamlit Community Cloud is free: https://docs.streamlit.io/deploy/streamlit-community-cloud
Deployment instructions: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app

No live app is created merely by adding these files. Publishing requires your GitHub repository and Streamlit account.

## Run the browser edition on your computer

From the Measure project folder:

```bash
python3 -m venv /tmp/measure-web-env
/tmp/measure-web-env/bin/python -m pip install -r measure/requirements.txt
/tmp/measure-web-env/bin/python -m streamlit run measure/web_app.py
```

Open `http://localhost:8501` in Chrome if the browser does not open automatically.

## Workflow

1. Start by selecting an assessment and clicking **Continue**. Only test selection appears on the opening screen. The left sidebar shows the current step, **Back a step**, and **Restart**.
2. Download the selected assessment's **Excel (.xlsx) score template**. Its measure names and the accepted-name reference list belong only to that assessment. The headers must be exactly `name,score,percentile`, in that order, with no extra columns. Fill in only the scores you want to report. Leave unused score/percentile cells blank or delete unused rows; a complete assessment battery is not required. Percentile can be blank; do not enter raw scores. CSV and Excel (.xlsx) are supported. The app determines score types from recognized names and rejects unknown names.
3. Import the completed table, or paste copied Excel/Numbers cells, including headers, into **Or paste your score table here**. Click outside the box to load the table automatically; no import button is needed. The score editor appears only after scores are loaded. Pasted CSV text is also accepted. Invalid pasted tables leave current scores unchanged. Review or edit its three columns. Accepted full names and abbreviations are listed beside the template download.
4. Click **Continue to wording**, then upload your Word/TXT/Markdown wording and click **Load uploaded template**, or paste/type your text directly into **Report wording** without uploading anything. Pasting uses plain text and standard export formatting. The Report wording box shows the uploaded text and permits edits. Use automatic name matching or placeholders such as `{{FSIQ.score}}` and `{{FSIQ.category}}`.
5. Click **Continue to review** and review the completed report. Word (.docx) is an editable document with formatting; plain text (.txt) contains the same wording without formatting. Unedited Word templates retain supported formatting; editing their text creates a fresh Word document. The editor displays text, not a visual facsimile of Word pages.

Apple Numbers `.numbers` files are not imported directly. Open the workbook in Numbers and use **File → Export To → Excel**, then upload the exported `.xlsx` file. Renaming `.numbers` to `.xlsx` does not convert it. Unsupported, unreadable, or damaged files display an error without replacing current scores. CSV remains supported for imports. Uploaded files are read without modifying the original workbook.

### Owner-maintained categories and abbreviations

`measure/test_profiles.json` defines each assessment's category rules. Fixed names and abbreviations live in `measure/catalog.py` and are identical for every user. WAIS subtests follow the supplied order; indexes appear separately. WIAT displays names only. PAI subscales follow their parent scales in both the reference tables and Excel template. End users do not configure ranges. WIAT and WAIS standard-score categories use the owner's supplied definitions. WIAT categories extend below 40 as Very Low and above 160 as Very High. Standard-score category endpoints extend to any entered whole-number value; the app does not check score/percentile correspondence. WAIS categories include 130 and above and 69 and below within the supported score range. WAIS subtest scaled-score categories and PAI scale-specific categories remain unconfigured pending owner definitions. The app displays this status. Only configured rules determine categories, and no categories are accepted from score uploads.

For each test, replace `rules.standard` / `rules.scaled` with inclusive `min`, `max`, `label` bands as appropriate. PAI must use `rules.overrides` keyed by scale name or code. Update `status` after supplying the final definitions. Keep this file in GitHub alongside the Python files.

## Data handling

Use fictional data on free online hosting. Uploaded files and report text are transmitted to the hosting server. The app keeps working state in the browser session's server memory, reads uploads in memory without writing imported content to temporary files, and adds no case database or shared cache. Hosting providers have their own logging, retention, and access policies. Closing/reloading/disconnecting can lose work; download reports before leaving. **Restart** clears the application's current working state.

The original desktop edition remains available through `app.py`. Its local-processing statement does not apply to the online edition. The web edition currently downloads reports, not reusable desktop project files.

### Report score formatting

The browser edition formats automatic summaries with commas and ordinal percentile ranks: `SS = 109, 73rd%ile, Average`. For exact sentence placement, use:

```text
On Mathematics, performance was in the {{Mathematics.category}} range ({{Mathematics.score_summary}}).
```

This produces `On Mathematics, performance was in the Average range (SS = 109, 73rd%ile).` To include the category inside parentheses instead, use `Mathematics ({{Mathematics.summary}}).` For an introductory result, use `{{Total Achievement.category}} range (Total Achievement: Standard Score (SS) = {{Total Achievement.score}}, {{Total Achievement.percentile_report}})`.

`percentile_report` adds the ordinal suffix and `%ile`; `percentile` still returns the imported numeric rank for compatibility. Noninteger ranks such as `0.5` use `0.5%ile` without an ordinal suffix. The browser fills only sentence-ending blank score markers, such as `(SS = XX, XX%ile)`, and explicit placeholders. It leaves ordinary measure mentions and existing numeric results unchanged. For multiple measures in one sentence, explicitly name the intended measure inside the marker: `(Mathematics: SS = XX, XX%ile)`. Use `(T = XX, XX%ile)` for T scores or `(Scaled score = XX, XX%ile)` for scaled scores. More complex sentences should use placeholders for exact placement. Pre-existing numeric results are retained and flagged for review; strengths and clinical interpretations are not generated.

### Strength and weakness labels

All Excel templates now have `name, score, percentile, strengths`. Older three-column tables remain accepted. In `strengths`, enter NS, PS, NW, or PW; combine labels with commas (for example, `NS, PS`). Leave the cell blank if none applies. These labels can be entered for any measure, including subtests and PAI scales/subscales. PAI defaults contain the label names only; users can edit their definitions. Contradictory pairs (NS/NW or PS/PW) require correction.

In Score table, expand **Strength and weakness definitions (edit for this report)** to view/edit the selected test's four defaults. Edits apply to the current session; changing tests or clearing the session resets them. Update names and pronouns for the person being described, as appropriate for your report. Later abbreviated sentences simply say, for example, “This was also a PS.”

Strength/weakness definitions are separate sentences after score parentheses, never inside them. Each code is defined only on its first use in the report; subsequent uses show just the code . For exact placement, use `{{Mathematics.strengths}}`; `{{Mathematics.score_summary}}` supplies only score/percentile information. Plain `{{Mathematics.summary}}` includes scores and the category; place `{{Mathematics.strengths}}` after the score parentheses for strength sentences. Explicitly requesting strengths for a measure with no entered labels is flagged instead of inventing them.

The app contains no AI and does not calculate assessment scores, percentiles, score differences, statistical significance, or strength/weakness labels. It copies user-entered results, checks their format, looks up descriptive categories in the configured ranges, and inserts selected definitions. Ordinal suffixes and document formatting change presentation only.

Select **She / her**, **He / him**, or **They / them** in Score table to update strength/weakness definitions for this report. This selection applies to those definitions only; it does not rewrite the uploaded report wording. You can still edit each definition directly. Repeated labels use “an NS”, “an NW”, “a PS”, and “a PW”.


### Privacy audit and limits

The browser entry point does not import the desktop project-saving interface, call AI services, issue custom external HTTP requests, or cache report data globally. Imports use in-memory buffers. Working data exists in server-side session memory. Restart clears application state and explicitly releases the current session's uploaded-file and generated-download references through Streamlit's managers; other live sessions are not cleared. This is reference removal, not cryptographic erasure of memory. Downloads already saved on a user's computer cannot be deleted by Restart.

`measure/.streamlit/config.toml` requests no usage telemetry, immediate eligibility for disconnected-session cleanup (`disconnectedSessionTTL = 0`), disabled static-file serving, and hidden error details. Include this hidden folder when uploading to GitHub. Streamlit's cleanup timing is framework-controlled; immediate physical erasure after tab closure is not guaranteed. The local launcher also disables usage statistics.

**Community Cloud limitation:** https://docs.streamlit.io/deploy/streamlit-community-cloud/status explicitly lists `browser.gatherUsageStats = true` among hosting overrides. Consequently, a deployment on Community Cloud cannot be certified to have no non-report network traffic. Hosting infrastructure can also process connection metadata and logs; this source audit does not verify provider retention, swap, backups, or browser storage. The app has no infrastructure-level outbound network firewall. To enforce the strict no-third-party-network requirement, run locally or use controlled hosting with telemetry disabled and outbound access denied after dependencies are installed. This is not a claim of regulatory certification.
