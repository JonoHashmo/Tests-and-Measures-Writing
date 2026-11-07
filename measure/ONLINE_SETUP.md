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

1. Select an assessment and download its CSV score template. The headers must be exactly `name,score,percentile`, in that order, with no extra columns. Fill scores and delete unused measure rows. Percentile can be blank; do not enter raw scores. CSV and Excel (.xlsx) are supported. The app determines score types from recognized names and rejects unknown names.
2. Import the completed table. Review or edit its three columns. Accepted full names and abbreviations are listed beside the template download.
3. Upload your Word/TXT/Markdown wording and click **Load uploaded template**, or paste it. The Report wording box shows the uploaded text and permits edits. Use automatic name matching or placeholders such as `{{FSIQ.score}}` and `{{FSIQ.category}}`.
4. Review the completed report. Word (.docx) is an editable document with formatting; plain text (.txt) contains the same wording without formatting. Unedited Word templates retain supported formatting; editing their text creates a fresh Word document. The editor displays text, not a visual facsimile of Word pages.

### Owner-maintained categories and abbreviations

`measure/test_profiles.json` defines each assessment's rules and additional aliases. End users do not configure ranges. WIAT and WAIS standard-score categories use the owner's supplied definitions. WIAT categories cover 40–160 only. WAIS categories include 130 and above and 69 and below within the supported score range. WAIS subtest scaled-score categories and PAI scale-specific categories remain unconfigured pending owner definitions. The app displays this status. Only configured rules determine categories, and no categories are accepted from score uploads.

For each test, replace `rules.standard` / `rules.scaled` with inclusive `min`, `max`, `label` bands as appropriate. PAI must use `rules.overrides` keyed by scale name or code. `aliases` maps a recognized canonical measure name to a list of additional matching names. Update `status` after supplying the final definitions. Keep this file in GitHub alongside the Python files.

## Data handling

Use fictional data on free online hosting. Uploaded files and report text are transmitted to the hosting server. The app keeps working state in the browser session's server memory, uses automatically deleted temporary files for imports, and adds no case database or shared cache. Hosting providers have their own logging, retention, and access policies. Closing/reloading/disconnecting can lose work; download reports before leaving. **Clear session** clears the application's current working state.

The original desktop edition remains available through `app.py`. Its local-processing statement does not apply to the online edition. The web edition currently downloads reports, not reusable desktop project files.
