from flask import Flask
import mysql.connector
import os

app = Flask(__name__)

@app.route('/')
def test():
    try:
        conn = mysql.connector.connect(
            host='turntable.proxy.rlwy.net',
            user='root',
            password='QttFmgSWJcoJfFKJNFwuscHPWPSESxWs',
            database='railway',
            port=57488
        )
        return "✅ CONEXIÓN EXITOSA A RAILWAY"
    except Exception as e:
        return f"❌ ERROR: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
