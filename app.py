from flask import Flask, render_template, request, jsonify
import requests
import uuid
import time

app = Flask(__name__)

API_BASE = 'https://api.bypassgpt.co/api/v1/chat'


def send_humanize(prompt, jsession='', uniqueid=None):
    if uniqueid is None:
        uniqueid = uuid.uuid4().hex
    headers = {
        'uniqueid': uniqueid,
        'Content-Type': 'application/json'
    }
    if jsession:
        headers['Cookie'] = f'JSESSIONID={jsession}'
    resp = requests.post(f'{API_BASE}/humanizedChat', json={'prompt': prompt}, headers=headers, timeout=30)
    resp.raise_for_status()
    j = resp.json()
    recordId = j.get('data', {}).get('recordId') if isinstance(j.get('data'), dict) else None
    return uniqueid, recordId, j


def poll_record(recordId, uniqueid, jsession='', timeout=120):
    headers = {
        'uniqueid': uniqueid,
        'Content-Type': 'application/json'
    }
    if jsession:
        headers['Cookie'] = f'JSESSIONID={jsession}'
    start = time.time()
    while True:
        r = requests.post(f'{API_BASE}/loadRecordInfo', json={'recordId': int(recordId)}, headers=headers, timeout=30)
        r.raise_for_status()
        j = r.json()
        # possible locations for state
        state = None
        if isinstance(j.get('data'), dict):
            state = j.get('data', {}).get('state')
        if state is None:
            state = j.get('state')

        # try to extract humanized response text from likely paths
        responseText = None
        try:
            # nested possibilities
            nested = j.get('data', {}).get('data') if isinstance(j.get('data'), dict) else None
            human = None
            if nested and isinstance(nested, dict):
                human = nested.get('humanizeData') or nested
            else:
                human = j.get('data', {}).get('humanizeData') if isinstance(j.get('data'), dict) else None
            if isinstance(human, dict):
                responseText = human.get('responseText')
        except Exception:
            responseText = None

        if responseText:
            return {'state': 'success', 'response': responseText, 'payload': j}

        if state == 'success':
            return {'state': 'success', 'response': None, 'payload': j}
        if state in ('fail', 'error'):
            return {'state': state, 'response': None, 'payload': j}
        if time.time() - start > timeout:
            return {'state': 'timeout', 'response': None, 'payload': j}

        time.sleep(2)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/humanize', methods=['POST'])
def api_humanize():
    data = request.json or {}
    prompt = data.get('prompt')
    jsession = data.get('jsession', '')
    timeout = int(data.get('timeout', 120))
    # allow client to pass uniqueid or generate new one
    uniqueid = data.get('uniqueid')

    if not prompt:
        return jsonify({'error': 'prompt is required'}), 400

    try:
        uniqueid, recordId, initial = send_humanize(prompt, jsession=jsession, uniqueid=uniqueid)
    except Exception as e:
        return jsonify({'error': 'initial request failed', 'details': str(e)}), 500

    if not recordId:
        # return initial payload if no recordId
        return jsonify({'uniqueid': uniqueid, 'recordId': None, 'initial': initial}), 200

    result = poll_record(recordId, uniqueid, jsession=jsession, timeout=timeout)
    return jsonify({'uniqueid': uniqueid, 'recordId': recordId, 'result': result})


if __name__ == '__main__':
    # Port 5000 is often taken by AirPlay on macOS, so we use 5001
    app.run(host='127.0.0.1', port=5001, debug=True)
