from flask import Flask, jsonify, render_template_string, request
import mysql.connector
import os
import time

app = Flask(__name__)

# HTML mínimo del dashboard
HTML_DASHBOARD = '''
<!DOCTYPE html>
<html>
<head>
    <title>Control Robot</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f0f0f0; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .header { text-align: center; margin-bottom: 30px; }
        .btn { padding: 10px 20px; margin: 5px; border: none; border-radius: 5px; cursor: pointer; }
        .btn-on { background: #4CAF50; color: white; }
        .btn-off { background: #f44336; color: white; }
        .btn-move { background: #2196F3; color: white; }
        .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
        .status-on { background: #d4edda; color: #155724; }
        .status-off { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Control Robot Básico</h1>
            <p>Control simplificado del robot</p>
        </div>

        <div id="alert"></div>

        <div class="status" id="status">
            Estado: Conectado
        </div>

        <div>
            <h3>Control General</h3>
            <button class="btn btn-on" onclick="sendCommand('ON')">🔌 ENCENDER</button>
            <button class="btn btn-off" onclick="sendCommand('OFF')">⚙️ APAGAR</button>
            <button class="btn btn-off" onclick="sendCommand('STOP')">🛑 PARADA</button>
            <button class="btn btn-move" onclick="sendCommand('RESET')">🔄 REINICIAR</button>
        </div>

        <div>
            <h3>Control de Garra</h3>
            <button class="btn btn-on" onclick="sendCommand('ABRIR')">🔓 ABRIR</button>
            <button class="btn btn-off" onclick="sendCommand('CERRAR')">🔒 CERRAR</button>
        </div>

        <div>
            <h3>Movimiento Directo</h3>
            <select id="motor">
                <option value="1">Motor 1</option>
                <option value="2">Motor 2</option>
                <option value="3">Motor 3</option>
                <option value="4">Motor 4</option>
            </select>
            <input type="number" id="pasos" value="100" placeholder="Pasos">
            <input type="number" id="velocidad" value="500" placeholder="Velocidad">
            <button class="btn btn-move" onclick="moverMotor()">▶️ MOVER</button>
        </div>

        <div style="margin-top: 30px;">
            <h3>Estado del Sistema</h3>
            <p>Servidor: <span id="server-status">🟢 Conectado</span></p>
            <p>Base de datos: <span id="db-status">Probando...</span></p>
        </div>
    </div>

    <script>
        function showAlert(message, type = 'success') {
            const alert = document.getElementById('alert');
            alert.textContent = message;
            alert.style.background = type === 'success' ? '#d4edda' : '#f8d7da';
            alert.style.color = type === 'success' ? '#155724' : '#721c24';
            setTimeout(() => { alert.textContent = ''; }, 3000);
        }

        async function sendCommand(comando) {
            try {
                const response = await fetch(`/api/comando/${comando}`);
                const result = await response.json();
                if (result.status === 'success') {
                    showAlert(`✅ Comando ${comando} enviado`);
                } else {
                    showAlert(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showAlert('❌ Error de conexión', 'error');
            }
        }

        async function moverMotor() {
            const motor = document.getElementById('motor').value;
            const pasos = document.getElementById('pasos').value;
            const velocidad = document.getElementById('velocidad').value;
            
            if (!pasos || pasos < 1) {
                showAlert('⚠️ Ingresa pasos válidos', 'error');
                return;
            }

            try {
                const response = await fetch('/api/mover_motor', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        motor: parseInt(motor),
                        pasos: parseInt(pasos),
                        velocidad: parseInt(velocidad),
                        direccion: 'H'
                    })
                });
                const result = await response.json();
                if (result.status === 'success') {
                    showAlert(`✅ Motor M${motor} movido`);
                } else {
                    showAlert(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showAlert('❌ Error de conexión', 'error');
            }
        }

        // Probar conexión a la base de datos al cargar
        async function testDatabase() {
            try {
                const response = await fetch('/api/test_db');
                const result = await response.json();
                document.getElementById('db-status').textContent = result.status === 'success' ? '🟢 Conectada' : '🔴 Error';
                document.getElementById('db-status').style.color = result.status === 'success' ? 'green' : 'red';
            } catch (error) {
                document.getElementById('db-status').textContent = '🔴 Error de conexión';
                document.getElementById('db-status').style.color = 'red';
            }
        }

        // Ejecutar cuando se carga la página
        document.addEventListener('DOMContentLoaded', function() {
            testDatabase();
        });
    </script>
</body>
</html>
'''

# Conexión a la base de datos
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.environ.get('MYSQL_HOST', 'turntable.proxy.rlwy.net'),
            user=os.environ.get('MYSQL_USER', 'root'),
            password=os.environ.get('MYSQL_PASSWORD', 'QttFmgSWJcoJfFKJNFwuscHPWPSESxWs'),
            database=os.environ.get('MYSQL_DATABASE', 'railway'),
            port=int(os.environ.get('MYSQL_PORT', 57488)),
            connect_timeout=5
        )
        return conn
    except Exception as e:
        print(f"Error en conexión BD: {e}")
        return None

# Configurar base de datos inicial
def setup_database():
    try:
        conn = get_db_connection()
        if conn is None:
            return False
            
        cursor = conn.cursor()
        
        # Tabla simple de comandos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comandos_robot (
                id INT AUTO_INCREMENT PRIMARY KEY,
                esp32_id VARCHAR(50),
                comando VARCHAR(100),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla simple de estado
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS estado_robot (
                id INT AUTO_INCREMENT PRIMARY KEY,
                esp32_id VARCHAR(50),
                motores_activos BOOLEAN,
                emergency_stop BOOLEAN,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Estado inicial
        cursor.execute("SELECT * FROM estado_robot WHERE esp32_id = 'cobot_01'")
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO estado_robot (esp32_id, motores_activos, emergency_stop) 
                VALUES ('cobot_01', 0, 0)
            ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Base de datos configurada")
        return True
        
    except Exception as e:
        print(f"❌ Error configurando BD: {e}")
        return False

# Configurar al inicio
setup_database()

# Rutas principales
@app.route('/')
def dashboard():
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/comando/<accion>')
def enviar_comando(accion):
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "Sin conexión BD"}), 500
            
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO comandos_robot (esp32_id, comando) VALUES (%s, %s)",
            ('cobot_01', accion.upper())
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Comando guardado: {accion}")
        return jsonify({"status": "success", "comando": accion})
        
    except Exception as e:
        print(f"❌ Error en comando: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/mover_motor', methods=['POST'])
def mover_motor():
    try:
        data = request.json
        motor = data.get('motor')
        pasos = data.get('pasos')
        velocidad = data.get('velocidad')
        direccion = data.get('direccion')
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "Sin conexión BD"}), 500
            
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO comandos_robot (esp32_id, comando, motor_num, pasos, velocidad, direccion) VALUES (%s, %s, %s, %s, %s, %s)",
            ('cobot_01', 'MOVER_MOTOR', motor, pasos, velocidad, direccion)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Movimiento motor M{motor}: {pasos} pasos")
        return jsonify({"status": "success", "mensaje": f"Motor M{motor} movido"})
        
    except Exception as e:
        print(f"❌ Error moviendo motor: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/test_db')
def test_db():
    """Probar conexión a la base de datos"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No se pudo conectar"})
            
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "message": "Conexión exitosa"})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route('/api/estado')
def obtener_estado():
    """Obtener estado actual"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "Sin conexión BD"})
            
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM estado_robot WHERE esp32_id = 'cobot_01' ORDER BY timestamp DESC LIMIT 1")
        estado = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if estado:
            return jsonify({
                "motores_activos": bool(estado[2]),
                "emergency_stop": bool(estado[3])
            })
        else:
            return jsonify({"error": "No hay estado"})
            
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route('/api/health')
def health_check():
    """Endpoint de salud para Render"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "service": "cobot-dashboard"
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Servidor iniciado en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

     
