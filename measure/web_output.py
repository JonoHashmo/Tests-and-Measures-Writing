"""Plain-text browser outputs. Report data is never interpreted as HTML or code."""
from streamlit.components.v2 import component

COPY_HTML = '''
<button type="button" id="copy-report">Copy report</button>
<p id="copy-status" role="status" aria-live="polite"></p>
<div id="manual-copy" hidden>
  <p>Automatic copying is blocked by your browser. The report below is selected.
     Press Command+C on a Mac or Ctrl+C on Windows, then paste into Word.</p>
  <textarea id="copy-text" readonly aria-label="Report text for manual copying" rows="8" spellcheck="false"></textarea>
</div>
'''

COPY_CSS = '''
button {
  background: #245f58; color: white; border: 1px solid #245f58;
  border-radius: .5rem; padding: .6rem 1rem; font: inherit; cursor: pointer;
}
button:hover { background: #194b45; }
button:focus-visible, textarea:focus-visible { outline: 3px solid #bc8d4a; outline-offset: 3px; }
button:disabled { opacity: .7; cursor: wait; }
p { font: inherit; color: var(--st-text-color); line-height: 1.5; }
#copy-status:empty { display: none; }
textarea {
  box-sizing: border-box; width: 100%; padding: .75rem; border: 1px solid #84938d;
  border-radius: .5rem; font: inherit; color: var(--st-text-color);
  background: var(--st-secondary-background-color); resize: vertical;
}
[hidden] { display: none !important; }
'''

COPY_JS = '''
export default function({ data, parentElement }) {
  const button = parentElement.querySelector('#copy-report');
  const status = parentElement.querySelector('#copy-status');
  const fallback = parentElement.querySelector('#manual-copy');
  const textarea = parentElement.querySelector('#copy-text');
  const text = data.text;
  // User content is data only: never set innerHTML or evaluate report text.
  textarea.value = text;
  fallback.hidden = true;
  status.textContent = '';
  button.disabled = false;
  button.onclick = async () => {
    button.disabled = true;
    status.textContent = '';
    fallback.hidden = true;
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) {
        throw new Error('Plain-text clipboard unavailable');
      }
      await navigator.clipboard.writeText(text);
      status.textContent = 'Report copied. Paste it into your Word document.';
    } catch (_) {
      status.textContent = 'Use the selected text below to copy your report.';
      fallback.hidden = false;
      textarea.focus();
      textarea.select();
    } finally {
      button.disabled = false;
    }
  };
  return () => { button.onclick = null; };
}
'''

copy_report = component('measure_copy_report', html=COPY_HTML, css=COPY_CSS, js=COPY_JS)


def report_text_bytes(text: str) -> bytes:
    """Exact UTF-8 text, without a BOM, markup, metadata, or added newlines."""
    return text.encode('utf-8')
