from flask import Flask, jsonify
import mysql.connector
from config import get_mysql_config  # <-- Importar la configuración
import os

app = Flask(__name__)

@app.route('/api/comando/<accion>')
def enviar_comando(accion):
    """Recibe comandos de la web y los guarda en MySQL"""
    try:
        conn = mysql.connector.connect(**get_mysql_config())  # <-- Conexión REAL
        cursor = conn.cursor()
        
        # Insertar comando en la tabla comandos_robot
        cursor.execute(
            "INSERT INTO comandos_robot (esp32_id, comando, parametros) VALUES (%s, %s, %s)",
            ('CDBOT_001', accion, '{}')
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "comando": accion})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route('/api/estado')
def obtener_estado():
    """Devuelve el estado actual del robot desde MySQL"""
    try:
        conn = mysql.connector.connect(**get_mysql_config())  # <-- Conexión REAL
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM moduls_tellis WHERE esp32_id = 'CDBOT_001'")
        estado = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if estado:
            return jsonify({
                "motores_activos": bool(estado[2]),
                "emergency_stop": bool(estado[3]), 
                "posicion_m1": estado[4],
                "posicion_m2": estado[5],
                "posicion_m3": estado[6],
                "posicion_m4": estado[7],
                "garra_abierta": bool(estado[8])
            })
        else:
            return jsonify({"error": "No se encontró estado"})
            
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

# ... (tus rutas existentes aquí)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
