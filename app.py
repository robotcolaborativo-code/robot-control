from flask import Flask, jsonify
import mysql.connector
import os

app = Flask(__name__)

# Configuración simple y directa
def get_db_config():
    return {
        'host': 'monorail.proxy.rlwy.net',
        'user': 'root',
        'password': 'QttFmgSWJcoJTFKJNFwuschPWPSESxWs',
        'database': 'railway',
        'port': 15829
    }

@app.route('/')
def index():
    return "🤖 Robot Control API - FUNCIONANDO ✅"

@app.route('/api/estado')
def obtener_estado():
    try:
        return jsonify({"status": "API ESTADO FUNCIONA", "prueba": True})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/comando/<accion>')
def enviar_comando(accion):
    try:
        return jsonify({"status": "success", "comando": accion, "mensaje": "API COMANDO FUNCIONA"})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
