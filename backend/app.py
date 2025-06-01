from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify(message="Hello World from Backend!")

# Esta parte solo se ejecuta si corres el script directamente (ej. python app.py)
# Gunicorn no la ejecutará cuando importe 'app:app'
if __name__ == '__main__':
    app.run(port=5000, debug=True) # Añadido debug=True para desarrollo local
