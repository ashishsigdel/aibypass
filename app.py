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
    double_check = data.get('double_check', False)

    if not prompt:
        return jsonify({'error': 'prompt is required'}), 400

    def split_into_chunks(text, max_words=200):
        paragraphs = text.split('\n')
        chunks = []
        current_chunk = []
        current_word_count = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            words = len(para.split())
            
            # If adding this paragraph exceeds max_words and we have something in current_chunk
            if current_word_count + words > max_words and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_word_count = 0
            
            current_chunk.append(para)
            current_word_count += words
            
            # If a single paragraph is huge (starts empty or just added), it just becomes a chunk
            if current_word_count >= max_words:
                 chunks.append('\n\n'.join(current_chunk))
                 current_chunk = []
                 current_word_count = 0

        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks

    def process_text(input_text):
        chunks = split_into_chunks(input_text)
        results = []
        for i, chunk in enumerate(chunks):
            # Generate new uniqueid for each chunk request to be safe
            uid = uuid.uuid4().hex
            _, recordId, _ = send_humanize(chunk, jsession=jsession, uniqueid=uid)
            if not recordId:
                raise Exception(f"Failed to get recordId for chunk {i+1}")
            
            res = poll_record(recordId, uid, jsession=jsession, timeout=timeout)
            if res['state'] == 'success' and res['response']:
                results.append(res['response'])
            else:
                raise Exception(f"Failed to humanize chunk {i+1}. State: {res['state']}")
        return '\n\n'.join(results)

    try:
        # First pass
        pass1 = process_text(prompt)
        
        final_response = pass1
        if double_check:
            # Second pass
            final_response = process_text(pass1)
            
        return jsonify({'result': {'response': final_response, 'state': 'success'}})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Port 5000 is often taken by AirPlay on macOS, so we use 5001
    app.run(host='127.0.0.1', port=5001, debug=True)
