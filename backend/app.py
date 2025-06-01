from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify(message="Hello World from Backend!")

if __name__ == '__main__':
    app.run(port=5000)
