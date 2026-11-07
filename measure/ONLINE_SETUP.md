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

Select an assessment, upload a table, select a sheet/table and header row, and map the columns. Import replaces the current score table. Edit cells or add rows in the score editor; use `standard`, `scaled`, or `t` for the score type. Separate additional aliases with semicolons.

Under descriptive ranges, edit the inclusive minimum, maximum, and label. Click **Apply cutoff ranges**. Enter a measure name or code to define an override; PAI requires named scale rules. Imported labels take precedence unless you select **Cutoff rules only**.

Upload your Word/TXT/Markdown wording and click **Load uploaded template**, or paste text. Use automatic name matching or placeholders such as `{{FSIQ.score}}` and `{{FSIQ.category}}`. Review and download Word or text. Unedited Word templates retain supported formatting; editing their text creates a fresh Word document.

## Data handling

Use fictional data on free online hosting. Uploaded files and report text are transmitted to the hosting server. The app keeps working state in the browser session's server memory, uses automatically deleted temporary files for imports, and adds no case database or shared cache. Hosting providers have their own logging, retention, and access policies. Closing/reloading/disconnecting can lose work; download reports before leaving. **Clear session** clears the application's current working state.

The original desktop edition remains available through `app.py`. Its local-processing statement does not apply to the online edition. The web edition currently downloads reports, not reusable desktop project files.
