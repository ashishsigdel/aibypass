# BypassGPT Humanizer — Local tools

This folder provides two ways to call the BypassGPT humanizer endpoints and poll for results:

- A Bash script: `scripts/bypassgpt.sh`
- A small Flask web UI: `app.py` + `templates/index.html`

Prerequisites

- Python 3.8+ and `pip` (for the Flask UI)
- `curl`, `jq`, and `uuidgen` (or Python) for the Bash script

Install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run the Flask UI

```bash
python app.py
# then open http://127.0.0.1:5001
```

Using the Bash script

```bash
./scripts/bypassgpt.sh -p "Your prompt here" -c "DC16376622742BA52C897B524740C39C"
```

Notes

- Both tools perform the same flow: send `humanizedChat`, read `recordId`, then poll `loadRecordInfo` until the result is available or a timeout occurs.
- The script and server try to handle the variations in the API responses described in your examples.
