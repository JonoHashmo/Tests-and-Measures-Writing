# Measure in Chrome

The browser edition uses Python and Streamlit. It does not need Tkinter or a Mac.

## Free online hosting

1. Create a GitHub repository and upload the `measure` and `examples` folders, preserving their names and contents. Do not upload real assessment data, environments, or generated reports.
2. Sign in at https://share.streamlit.io using GitHub.
3. Choose **Create app**, select the repository and branch, and set **Main file path** to `measure/web_app.py`.
4. Deploy. Streamlit finds `measure/requirements.txt` beside the entry point and installs the dependencies. Choose Python 3.12 in advanced settings if selecting a version.
5. Open the resulting `https://...streamlit.app` URL in Google Chrome. Click **Try fictional example** to test it.

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

1. Start by selecting an assessment and clicking **Continue**. Only test selection appears on the opening screen. The left sidebar shows the current step, **Back a step**, and **Clear session**.
2. Download the selected assessment's **Excel (.xlsx) score template**. Its measure names and the accepted-name reference list belong only to that assessment. The headers must be exactly `name,score,percentile`, in that order, with no extra columns. Fill in only the scores you want to report. Leave unused score/percentile cells blank or delete unused rows; a complete assessment battery is not required. Percentile can be blank; do not enter raw scores. CSV and Excel (.xlsx) are supported. The app determines score types from recognized names and rejects unknown names.
3. Import the completed table, or open **Or paste a score table**, paste copied Excel/Numbers cells including the three headers, and click **Import pasted table**. Pasted CSV text is also accepted. Invalid pasted tables leave current scores unchanged. Review or edit its three columns. Accepted full names and abbreviations are listed beside the template download.
4. Click **Continue to wording**, then upload your Word/TXT/Markdown wording and click **Load uploaded template**, or paste/type your text directly into **Report wording** without uploading anything. Pasting uses plain text and standard export formatting. The Report wording box shows the uploaded text and permits edits. Use automatic name matching or placeholders such as `{{FSIQ.score}}` and `{{FSIQ.category}}`.
5. Click **Continue to review** and review the completed report. Word (.docx) is an editable document with formatting; plain text (.txt) contains the same wording without formatting. Unedited Word templates retain supported formatting; editing their text creates a fresh Word document. The editor displays text, not a visual facsimile of Word pages.

Apple Numbers `.numbers` files are not imported directly. Open the workbook in Numbers and use **File → Export To → Excel**, then upload the exported `.xlsx` file. Renaming `.numbers` to `.xlsx` does not convert it. Unsupported, unreadable, or damaged files display an error without replacing current scores. CSV remains supported for imports. Uploaded files are read without modifying the original workbook.

### Owner-maintained categories and abbreviations

`measure/test_profiles.json` defines each assessment's category rules. Fixed names and abbreviations live in `measure/catalog.py` and are identical for every user. WAIS subtests follow the supplied order; indexes appear separately. WIAT displays names only. PAI subscales follow their parent scales in both the reference tables and Excel template. End users do not configure ranges. WIAT and WAIS standard-score categories use the owner's supplied definitions. WIAT categories cover 40–160 only. WAIS categories include 130 and above and 69 and below within the supported score range. WAIS subtest scaled-score categories and PAI scale-specific categories remain unconfigured pending owner definitions. The app displays this status. Only configured rules determine categories, and no categories are accepted from score uploads.

For each test, replace `rules.standard` / `rules.scaled` with inclusive `min`, `max`, `label` bands as appropriate. PAI must use `rules.overrides` keyed by scale name or code. Update `status` after supplying the final definitions. Keep this file in GitHub alongside the Python files.

## Data handling

Use fictional data on free online hosting. Uploaded files and report text are transmitted to the hosting server. The app keeps working state in the browser session's server memory, uses automatically deleted temporary files for imports, and adds no case database or shared cache. Hosting providers have their own logging, retention, and access policies. Closing/reloading/disconnecting can lose work; download reports before leaving. **Clear session** clears the application's current working state.

The original desktop edition remains available through `app.py`. Its local-processing statement does not apply to the online edition. The web edition currently downloads reports, not reusable desktop project files.

### Report score formatting

The browser edition formats automatic summaries with commas and ordinal percentile ranks: `SS = 109, 73rd%ile, Average`. For exact sentence placement, use:

```text
On Mathematics, performance was in the {{Mathematics.category}} range ({{Mathematics.score_summary}}).
```

This produces `On Mathematics, performance was in the Average range (SS = 109, 73rd%ile).` To include the category inside parentheses instead, use `Mathematics ({{Mathematics.summary}}).` For an introductory result, use `{{Total Achievement.category}} range (Total Achievement: Standard Score (SS) = {{Total Achievement.score}}, {{Total Achievement.percentile_report}})`.

`percentile_report` adds the ordinal suffix and `%ile`; `percentile` still returns the imported numeric rank for compatibility. Noninteger ranks such as `0.5` use `0.5%ile` without an ordinal suffix. Automatic matching recognizes a single-measure sentence with “in the … range”, updates that category, and places the score summary before the sentence-ending punctuation. More complex sentences should use placeholders for exact placement. Pre-existing numeric results are retained and flagged for review; strengths and clinical interpretations are not generated.

### Strength and weakness labels

WIAT and WAIS Excel templates now have `name, score, percentile, strengths`. Older three-column tables remain accepted. In `strengths`, enter NS, PS, NW, or PW; combine labels with commas (for example, `NS, PS`). Leave the cell blank if none applies. These labels are accepted only for WIAT composites and WAIS indexes, not individual subtests or PAI scales. Contradictory pairs (NS/NW or PS/PW) require correction.

In Score table, expand **Strength and weakness definitions (edit for this report)** to view/edit the selected test's four defaults. Edits apply to the current session; changing tests or clearing the session resets them. Update names and pronouns for the person being described, including the supplied WAIS PW default that mentions Carolina.

Automatic summaries include definitions for entered labels. For exact placement, use `{{Mathematics.strengths}}`; `{{Mathematics.score_summary}}` supplies only score/percentile information. Plain `{{Mathematics.summary}}` includes the category and entered strength definitions. Explicitly requesting strengths for a measure with no entered labels is flagged instead of inventing them.

The app contains no AI and does not calculate assessment scores, percentiles, score differences, statistical significance, or strength/weakness labels. It copies user-entered results, checks their format, looks up descriptive categories in the configured ranges, and inserts selected definitions. Ordinal suffixes and document formatting change presentation only.
