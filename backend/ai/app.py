from flask import Flask, request, jsonify
from flask_cors import CORS

# Import AgentManager via package import to work when `ai` is a package
from ai.agent_manager import AgentManager

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

agent_manager = AgentManager()

@app.route('/process_ticket', methods=['POST'])
def process_ticket():
    data = request.get_json()
    ticket_content = data.get('ticket')
    if not ticket_content:
        return jsonify({'error': 'No ticket content provided'}), 400
    
    try:
        result = agent_manager.process_ticket(ticket_content)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)