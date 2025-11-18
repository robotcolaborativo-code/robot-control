from flask import Flask, jsonify, render_template_string, request
import mysql.connector
import os
import time
import traceback

app = Flask(__name__)

# ======================= CONEXIÓN MYSQL CON MANEJO DE ERRORES =======================
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.environ.get('MYSQL_HOST', 'turntable.proxy.rlwy.net'),
            user=os.environ.get('MYSQL_USER', 'root'),
            password=os.environ.get('MYSQL_PASSWORD', 'QttFmgSWJcoJfFKJNFwuscHPWPSESxWs'),
            database=os.environ.get('MYSQL_DATABASE', 'railway'),
            port=int(os.environ.get('MYSQL_PORT', 57488)),
            connect_timeout=10
        )
        print("✅ Conexión MySQL exitosa")
        return conn
    except Exception as e:
        print(f"❌ Error conectando a MySQL: {e}")
        print(f"🔍 Detalles: host={os.environ.get('MYSQL_HOST')}, user={os.environ.get('MYSQL_USER')}")
        return None

# ======================= CONFIGURACIÓN INICIAL SIMPLIFICADA =======================
def setup_database():
    try:
        conn = get_db_connection()
        if conn is None:
            print("❌ No se pudo conectar a la base de datos para setup")
            return False
            
        cursor = conn.cursor()
        
        # Solo crear tablas si no existen
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comandos_robot (
                id INT AUTO_INCREMENT PRIMARY KEY,
                esp32_id VARCHAR(50),
                comando VARCHAR(100),
                parametros TEXT,
                motor_num INT,
                pasos INT,
                velocidad INT,
                direccion VARCHAR(10),
                posicion_m1 FLOAT,
                posicion_m2 FLOAT,
                posicion_m3 FLOAT,
                posicion_m4 FLOAT,
                garra_estado VARCHAR(10),
                modo_conexion VARCHAR(20),
                ejecutado BOOLEAN DEFAULT FALSE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS moduls_tellis (
                id INT AUTO_INCREMENT PRIMARY KEY,
                esp32_id VARCHAR(50),
                motores_activos BOOLEAN,
                emergency_stop BOOLEAN,
                posicion_m1 FLOAT,
                posicion_m2 FLOAT,
                posicion_m3 FLOAT,
                posicion_m4 FLOAT,
                garra_abierta BOOLEAN,
                velocidad_actual INT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posiciones_guardadas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nombre VARCHAR(100),
                posicion_m1 FLOAT,
                posicion_m2 FLOAT,
                posicion_m3 FLOAT,
                posicion_m4 FLOAT,
                garra_estado VARCHAR(10),
                velocidad INT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Tablas creadas/verificadas correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error en setup_database: {e}")
        print(traceback.format_exc())
        return False

# Configurar base de datos al inicio
setup_database()

# ======================= HTML SIMPLIFICADO PARA PRUEBAS =======================
HTML_SIMPLE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Control Robot - Debug</title>
    <style>
        body { font-family: Arial; margin: 20px; }
        .btn { padding: 10px; margin: 5px; background: blue; color: white; border: none; cursor: pointer; }
        .success { color: green; }
        .error { color: red; }
    </style>
</head>
<body>
    <h1>Control Robot - Modo Debug</h1>
    
    <div id="status">Estado: Conectando...</div>
    
    <h3>Comandos Básicos</h3>
    <button class="btn" onclick="sendCommand('ON')">ON</button>
    <button class="btn" onclick="sendCommand('OFF')">OFF</button>
    <button class="btn" onclick="sendCommand('ABRIR')">ABRIR GARRA</button>
    <button class="btn" onclick="sendCommand('CERRAR')">CERRAR GARRA</button>
    
    <h3>Test Conexión</h3>
    <button class="btn" onclick="testAPI()">Test API</button>
    <button class="btn" onclick="testDB()">Test Base de Datos</button>
    
    <div id="result"></div>

    <script>
        async function sendCommand(cmd) {
            try {
                const response = await fetch('/api/comando/' + cmd);
                const result = await response.json();
                showResult(result, 'Comando: ' + cmd);
            } catch (error) {
                showResult({status: 'error', error: error.message}, 'Error');
            }
        }
        
        async function testAPI() {
            try {
                const response = await fetch('/api/test');
                const result = await response.json();
                showResult(result, 'Test API');
            } catch (error) {
                showResult({status: 'error', error: error.message}, 'Error API');
            }
        }
        
        async function testDB() {
            try {
                const response = await fetch('/api/test_db');
                const result = await response.json();
                showResult(result, 'Test DB');
            } catch (error) {
                showResult({status: 'error', error: error.message}, 'Error DB');
            }
        }
        
        function showResult(result, title) {
            const div = document.getElementById('result');
            const color = result.status === 'success' ? 'success' : 'error';
            div.innerHTML = `<div class="${color}"><strong>${title}:</strong> ${JSON.stringify(result)}</div>`;
        }
        
        // Test inicial
        testAPI();
    </script>
</body>
</html>
'''

# ======================= RUTAS CON MANEJO DE ERRORES =======================
@app.route('/')
def dashboard():
    return render_template_string(HTML_SIMPLE)

@app.route('/api/test')
def test_api():
    """Ruta de prueba básica"""
    try:
        return jsonify({
            "status": "success", 
            "message": "✅ API funcionando correctamente",
            "timestamp": time.time(),
            "python_version": "Flask OK"
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/test_db')
def test_db():
    """Ruta para probar la base de datos"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No se pudo conectar a MySQL"}), 500
            
        cursor = conn.cursor()
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success", 
            "message": "✅ Base de datos conectada correctamente",
            "db_test": result[0]
        })
    except Exception as e:
        print(f"❌ Error en test_db: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/comando/<accion>')
def enviar_comando(accion):
    """Comandos generales: ON, OFF, STOP, RESET, ABRIR, CERRAR"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"}), 500
            
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO comandos_robot (esp32_id, comando) VALUES (%s, %s)",
            ('CDBOT_001', accion.upper())
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "comando": accion, "message": "Comando guardado en BD"})
        
    except Exception as e:
        print(f"❌ Error en enviar_comando: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/comandos_pendientes/<esp32_id>')
def obtener_comandos_pendientes(esp32_id):
    """Obtener comandos pendientes para un ESP32"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"}), 500
            
        cursor = conn.cursor()
        
        # Obtener comandos no ejecutados
        cursor.execute(
            "SELECT * FROM comandos_robot WHERE esp32_id = %s AND (ejecutado IS NULL OR ejecutado = FALSE) ORDER BY timestamp ASC LIMIT 10",
            (esp32_id,)
        )
        comandos = cursor.fetchall()
        
        comandos_list = []
        for cmd in comandos:
            comando_data = {
                "id": cmd[0],
                "comando": cmd[2],
                "motor_num": cmd[4],
                "pasos": cmd[5],
                "velocidad": cmd[6],
                "direccion": cmd[7],
                "posicion_m1": cmd[8],
                "posicion_m2": cmd[9],
                "posicion_m3": cmd[10],
                "posicion_m4": cmd[11]
            }
            comandos_list.append(comando_data)
        
        # Marcar como ejecutados
        if comandos:
            ids = [str(cmd[0]) for cmd in comandos]
            placeholders = ','.join(['%s'] * len(ids))
            cursor.execute(
                f"UPDATE comandos_robot SET ejecutado = TRUE WHERE id IN ({placeholders})",
                ids
            )
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "comandos": comandos_list})
        
    except Exception as e:
        print(f"❌ Error en comandos_pendientes: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/actualizar_estado', methods=['POST'])
def actualizar_estado():
    """Actualizar estado del robot desde el ESP32"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "error": "No JSON data received"}), 400
            
        print(f"📊 Estado recibido del ESP32: {data}")
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"}), 500
            
        cursor = conn.cursor()
        
        # Usar INSERT ... ON DUPLICATE KEY UPDATE
        cursor.execute('''
            INSERT INTO moduls_tellis 
            (esp32_id, motores_activos, emergency_stop, posicion_m1, posicion_m2, posicion_m3, posicion_m4, garra_abierta, velocidad_actual) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            motores_activos = VALUES(motores_activos),
            emergency_stop = VALUES(emergency_stop),
            posicion_m1 = VALUES(posicion_m1),
            posicion_m2 = VALUES(posicion_m2),
            posicion_m3 = VALUES(posicion_m3),
            posicion_m4 = VALUES(posicion_m4),
            garra_abierta = VALUES(garra_abierta),
            velocidad_actual = VALUES(velocidad_actual),
            timestamp = CURRENT_TIMESTAMP
        ''', (
            data.get('esp32_id', 'CDBOT_001'),
            data.get('motors_active', False),
            data.get('emergency_stop', False),
            data.get('motor1_deg', 0),
            data.get('motor2_deg', 0), 
            data.get('motor3_deg', 0),
            data.get('motor4_deg', 0),
            data.get('garra_state') == 'ABIERTA',
            data.get('velocidad_actual', 500)
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "message": "Estado actualizado"})
        
    except Exception as e:
        print(f"❌ Error actualizando estado: {e}")
        print(traceback.format_exc())
        return jsonify({"status": "error", "error": str(e)}), 500

# ======================= MANEJO DE ERRORES GLOBAL =======================
@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": "error", "error": "Endpoint no encontrado"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"status": "error", "error": "Error interno del servidor"}), 500

# ======================= INICIALIZACIÓN =======================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Iniciando servidor en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
