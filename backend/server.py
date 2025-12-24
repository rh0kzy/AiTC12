import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS

# Ensure workspace root is on sys.path so we can import the `ai` package
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Now import the AgentManager from the ai package

app = Flask(__name__)
CORS(app)

# Lazy initialization: create the AgentManager in a background thread to avoid
# blocking the Flask startup if external SDKs try to initialize network/SSL.
agent_manager = None
manager_ready = False
manager_starting = False

def _start_manager_background():
    global agent_manager, manager_ready, manager_starting
    try:
        manager_starting = True
        # Import here to avoid heavy SDK imports during module import
        from ai.agent_manager import AgentManager
        agent_manager = AgentManager()
        manager_ready = True
    except Exception as e:
        agent_manager = None
        manager_ready = False
        print('Failed to initialize AgentManager:', e)
    finally:
        manager_starting = False

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'manager_ready': manager_ready,
        'manager_starting': manager_starting
    })

@app.route('/process_ticket', methods=['POST'])
def process_ticket():
    global agent_manager, manager_ready, manager_starting

    data = request.get_json() or {}
    ticket_content = data.get('ticket')
    if not ticket_content:
        return jsonify({'error': 'No ticket content provided'}), 400

    # If manager isn't ready, start it in background and return 202
    if not manager_ready:
        if not manager_starting:
            # Start background thread
            import threading
            t = threading.Thread(target=_start_manager_background, daemon=True)
            t.start()
            return jsonify({'status': 'starting', 'message': 'Agent manager is starting. Try again shortly.'}), 202
        else:
            return jsonify({'status': 'starting', 'message': 'Agent manager is still starting. Try again shortly.'}), 202

    # Manager is ready — process the ticket (this may be slow if it calls external APIs)
    try:
        result = agent_manager.process_ticket(ticket_content)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
