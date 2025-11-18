from flask import Flask, jsonify, render_template_string, request
import mysql.connector
import os
import threading
import time

app = Flask(__name__)

# ======================= CONEXIÓN MYSQL =======================
def get_db_connection():
    return mysql.connector.connect(
        host='turntable.proxy.rlwy.net',
        user='root',
        password='QttFmgSWJcoJfFKJNFwuscHPWPSESxWs',
        database='railway',
        port=57488
    )

# ======================= CONFIGURACIÓN INICIAL =======================
def setup_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Eliminar y recrear tablas para empezar fresco
        cursor.execute("DROP TABLE IF EXISTS comandos_robot")
        cursor.execute("DROP TABLE IF EXISTS moduls_tellis")
        
        # Tabla de comandos EXPANDIDA
        cursor.execute('''
            CREATE TABLE comandos_robot (
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
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de estado del robot
        cursor.execute('''
            CREATE TABLE moduls_tellis (
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
        
        # Insertar estado inicial
        cursor.execute('''
            INSERT INTO moduls_tellis 
            (esp32_id, motores_activos, emergency_stop, posicion_m1, posicion_m2, posicion_m3, posicion_m4, garra_abierta, velocidad_actual) 
            VALUES 
            ('CDBOT_001', 1, 0, 0, 0, 0, 0, 1, 500)
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ BASE DE DATOS CONFIGURADA CORRECTAMENTE")
        
    except Exception as e:
        print(f"❌ Error configurando BD: {e}")

# Configurar base de datos al inicio
setup_database()

# ======================= HTML DASHBOARD COMPLETO =======================
HTML_DASHBOARD = '''
<!DOCTYPE html>
<html>
<head>
    <title>🤖 Dashboard Control Robot 4DOF</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        body {
            background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(45deg, #00b4db, #0083b0);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        }

        .header p {
            font-size: 1.2em;
            opacity: 0.8;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }

        @media (max-width: 1024px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }

        .panel {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 25px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .panel:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }

        .panel h2 {
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #00b4db;
            border-bottom: 2px solid #00b4db;
            padding-bottom: 10px;
        }

        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .status-item {
            background: rgba(0, 0, 0, 0.3);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            border-left: 4px solid #00b4db;
        }

        .status-item .label {
            font-size: 0.9em;
            opacity: 0.8;
            margin-bottom: 5px;
        }

        .status-item .value {
            font-size: 1.3em;
            font-weight: bold;
            color: #00b4db;
        }

        .status-item.emergency .value {
            color: #ff4444;
        }

        .status-item.active .value {
            color: #00C851;
        }

        .control-group {
            margin-bottom: 25px;
        }

        .control-group h3 {
            font-size: 1.3em;
            margin-bottom: 15px;
            color: #00b4db;
        }

        .btn-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
            margin-bottom: 15px;
        }

        .btn {
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            text-align: center;
            background: linear-gradient(45deg, #00b4db, #0083b0);
            color: white;
            border: 2px solid transparent;
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 180, 219, 0.4);
        }

        .btn:active {
            transform: translateY(0);
        }

        .btn-emergency {
            background: linear-gradient(45deg, #ff4444, #cc0000);
        }

        .btn-emergency:hover {
            box-shadow: 0 5px 15px rgba(255, 68, 68, 0.4);
        }

        .btn-success {
            background: linear-gradient(45deg, #00C851, #007E33);
        }

        .btn-warning {
            background: linear-gradient(45deg, #ffbb33, #FF8800);
        }

        .input-group {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            align-items: center;
            margin-bottom: 10px;
        }

        .input-group label {
            font-weight: bold;
        }

        .input-group input, .input-group select {
            padding: 10px;
            border: none;
            border-radius: 5px;
            background: rgba(255, 255, 255, 0.1);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }

        .input-group input:focus, .input-group select:focus {
            outline: none;
            border-color: #00b4db;
            box-shadow: 0 0 10px rgba(0, 180, 219, 0.3);
        }

        .motor-control {
            background: rgba(0, 0, 0, 0.2);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
        }

        .motor-control h4 {
            margin-bottom: 10px;
            color: #00b4db;
        }

        .animation-container {
            text-align: center;
            padding: 20px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 10px;
            margin-top: 20px;
        }

        .robot-visual {
            width: 200px;
            height: 200px;
            margin: 0 auto;
            background: linear-gradient(45deg, #2c5364, #203a43);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 3em;
            border: 3px solid #00b4db;
            box-shadow: 0 0 20px rgba(0, 180, 219, 0.5);
        }

        .alert {
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            font-weight: bold;
            text-align: center;
        }

        .alert.success {
            background: rgba(0, 200, 81, 0.2);
            border: 1px solid #00C851;
            color: #00C851;
        }

        .alert.error {
            background: rgba(255, 68, 68, 0.2);
            border: 1px solid #ff4444;
            color: #ff4444;
        }

        .alert.warning {
            background: rgba(255, 187, 51, 0.2);
            border: 1px solid #ffbb33;
            color: #ffbb33;
        }

        .hidden {
            display: none;
        }

        .loading {
            opacity: 0.7;
            pointer-events: none;
        }

        .pulse {
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 DASHBOARD CONTROL ROBOT 4DOF</h1>
            <p>Control completo del robot colaborativo desde la web</p>
        </div>

        <div id="alert-container"></div>

        <div class="dashboard-grid">
            <!-- PANEL IZQUIERDO: ESTADO Y CONTROL BÁSICO -->
            <div class="panel">
                <h2>📊 Estado del Robot</h2>
                
                <div class="status-grid" id="estado-container">
                    <div class="status-item">
                        <div class="label">🏃 Motores</div>
                        <div class="value" id="motores-activos">Cargando...</div>
                    </div>
                    <div class="status-item emergency">
                        <div class="label">🛑 Emergencia</div>
                        <div class="value" id="emergency-stop">Cargando...</div>
                    </div>
                    <div class="status-item">
                        <div class="label">🤖 Garra</div>
                        <div class="value" id="garra-estado">Cargando...</div>
                    </div>
                    <div class="status-item">
                        <div class="label">⚡ Velocidad</div>
                        <div class="value" id="velocidad-actual">Cargando...</div>
                    </div>
                </div>

                <div class="status-grid">
                    <div class="status-item">
                        <div class="label">📍 M1 Posición</div>
                        <div class="value" id="posicion-m1">0°</div>
                    </div>
                    <div class="status-item">
                        <div class="label">📍 M2 Posición</div>
                        <div class="value" id="posicion-m2">0°</div>
                    </div>
                    <div class="status-item">
                        <div class="label">📍 M3 Posición</div>
                        <div class="value" id="posicion-m3">0°</div>
                    </div>
                    <div class="status-item">
                        <div class="label">📍 M4 Posición</div>
                        <div class="value" id="posicion-m4">0°</div>
                    </div>
                </div>

                <div class="control-group">
                    <h3>🎮 Control General</h3>
                    <div class="btn-grid">
                        <button class="btn btn-success" onclick="sendCommand('ON')">🔌 ENERGIZAR</button>
                        <button class="btn btn-warning" onclick="sendCommand('OFF')">⚙️ APAGAR</button>
                        <button class="btn btn-emergency" onclick="sendCommand('STOP')">🛑 PARADA EMERGENCIA</button>
                        <button class="btn" onclick="sendCommand('RESET')">🔄 REINICIAR</button>
                    </div>
                </div>

                <div class="control-group">
                    <h3>🦾 Control de Garra</h3>
                    <div class="btn-grid">
                        <button class="btn" onclick="controlGarra('ABRIR')">🔓 ABRIR GARRA</button>
                        <button class="btn" onclick="controlGarra('CERRAR')">🔒 CERRAR GARRA</button>
                    </div>
                </div>

                <div class="animation-container">
                    <div class="robot-visual pulse">
                        🤖
                    </div>
                    <p style="margin-top: 15px; opacity: 0.8;">Robot 4DOF + Garra</p>
                </div>
            </div>

            <!-- PANEL DERECHO: CONTROL AVANZADO -->
            <div class="panel">
                <h2>⚙️ Control Avanzado</h2>

                <div class="control-group">
                    <h3>🔧 Control Directo por Motor</h3>
                    
                    <div class="input-group">
                        <label for="motor-select">Motor:</label>
                        <select id="motor-select">
                            <option value="1">M1 - Motor 1</option>
                            <option value="2">M2 - Motor 2</option>
                            <option value="3">M3 - Motor 3</option>
                            <option value="4">M4 - Motor 4</option>
                        </select>
                    </div>

                    <div class="input-group">
                        <label for="pasos-input">Pasos:</label>
                        <input type="number" id="pasos-input" value="200" min="1" max="10000">
                    </div>

                    <div class="input-group">
                        <label for="velocidad-input">Velocidad (RPM):</label>
                        <input type="number" id="velocidad-input" value="500" min="1" max="1000">
                    </div>

                    <div class="btn-grid">
                        <button class="btn" onclick="moverMotorDirecto('H')">⟳ HORARIO</button>
                        <button class="btn" onclick="moverMotorDirecto('A')">⟲ ANTIHORARIO</button>
                    </div>
                </div>

                <div class="control-group">
                    <h3>🎯 Control por Posición</h3>
                    
                    <div class="motor-control">
                        <h4>Motor 1 (M1)</h4>
                        <div class="input-group">
                            <label>Posición (0-360°):</label>
                            <input type="number" id="pos-m1" value="0" min="0" max="360" step="1">
                        </div>
                    </div>

                    <div class="motor-control">
                        <h4>Motor 2 (M2)</h4>
                        <div class="input-group">
                            <label>Posición (0-360°):</label>
                            <input type="number" id="pos-m2" value="0" min="0" max="360" step="1">
                        </div>
                    </div>

                    <div class="motor-control">
                        <h4>Motor 3 (M3)</h4>
                        <div class="input-group">
                            <label>Posición (0-360°):</label>
                            <input type="number" id="pos-m3" value="0" min="0" max="360" step="1">
                        </div>
                    </div>

                    <div class="motor-control">
                        <h4>Motor 4 (M4)</h4>
                        <div class="input-group">
                            <label>Posición (0-360°):</label>
                            <input type="number" id="pos-m4" value="0" min="0" max="360" step="1">
                        </div>
                    </div>

                    <div class="input-group">
                        <label for="velocidad-pos">Velocidad (RPM):</label>
                        <input type="number" id="velocidad-pos" value="500" min="1" max="1000">
                    </div>

                    <button class="btn" onclick="moverPosicion()" style="width: 100%; margin-top: 10px;">
                        🧭 MOVER A POSICIÓN
                    </button>
                </div>

                <div class="control-group">
                    <h3>💾 Posiciones Guardadas</h3>
                    <div class="btn-grid">
                        <button class="btn" onclick="guardarPosicion()">💾 GUARDAR POSICIÓN</button>
                        <button class="btn btn-warning" onclick="cargarPosicionInicio()">📥 CARGAR INICIO</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // ======================= FUNCIONES PRINCIPALES =======================
        
        function showAlert(message, type = 'success') {
            const alertContainer = document.getElementById('alert-container');
            const alert = document.createElement('div');
            alert.className = `alert ${type}`;
            alert.textContent = message;
            alertContainer.appendChild(alert);
            
            setTimeout(() => {
                alert.remove();
            }, 5000);
        }

        // Actualizar estado del robot
        async function actualizarEstado() {
            try {
                const response = await fetch('/api/estado');
                const estado = await response.json();
                
                if (estado.error) {
                    document.getElementById('estado-container').innerHTML = 
                        `<div class="alert error">❌ ${estado.error}</div>`;
                    return;
                }

                // Actualizar interfaz
                document.getElementById('motores-activos').textContent = 
                    estado.motores_activos ? 'ACTIVOS' : 'INACTIVOS';
                document.getElementById('motores-activos').className = 
                    estado.motores_activos ? 'value active' : 'value';
                
                document.getElementById('emergency-stop').textContent = 
                    estado.emergency_stop ? 'ACTIVADA' : 'NORMAL';
                
                document.getElementById('garra-estado').textContent = 
                    estado.garra_abierta ? 'ABIERTA' : 'CERRADA';
                
                document.getElementById('velocidad-actual').textContent = 
                    estado.velocidad_actual + ' RPM';
                
                document.getElementById('posicion-m1').textContent = estado.posicion_m1 + '°';
                document.getElementById('posicion-m2').textContent = estado.posicion_m2 + '°';
                document.getElementById('posicion-m3').textContent = estado.posicion_m3 + '°';
                document.getElementById('posicion-m4').textContent = estado.posicion_m4 + '°';

            } catch (error) {
                console.error('Error actualizando estado:', error);
            }
        }

        // Enviar comando general
        async function sendCommand(comando) {
            try {
                const response = await fetch(`/api/comando/${comando}`);
                const result = await response.json();
                
                if (result.status === 'success') {
                    showAlert(`✅ Comando ${comando} enviado correctamente`);
                    actualizarEstado();
                } else {
                    showAlert(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showAlert('❌ Error de conexión con el servidor', 'error');
            }
        }

        // Control de garra
        async function controlGarra(estado) {
            await sendCommand(estado);
        }

        // Mover motor directo
        async function moverMotorDirecto(direccion) {
            const motor = document.getElementById('motor-select').value;
            const pasos = document.getElementById('pasos-input').value;
            const velocidad = document.getElementById('velocidad-input').value;

            if (!pasos || pasos < 1) {
                showAlert('⚠️ Ingresa un número válido de pasos', 'warning');
                return;
            }

            try {
                const response = await fetch('/api/mover_motor', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        motor: parseInt(motor),
                        pasos: parseInt(pasos),
                        velocidad: parseInt(velocidad),
                        direccion: direccion
                    })
                });

                const result = await response.json();
                
                if (result.status === 'success') {
                    showAlert(`✅ Motor M${motor} movido ${direccion === 'H' ? 'horario' : 'antihorario'}`);
                    actualizarEstado();
                } else {
                    showAlert(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showAlert('❌ Error de conexión', 'error');
            }
        }

        // Mover a posición específica
        async function moverPosicion() {
            const posiciones = [
                parseFloat(document.getElementById('pos-m1').value),
                parseFloat(document.getElementById('pos-m2').value),
                parseFloat(document.getElementById('pos-m3').value),
                parseFloat(document.getElementById('pos-m4').value)
            ];

            const velocidad = parseInt(document.getElementById('velocidad-pos').value);

            // Validar posiciones
            for (let i = 0; i < posiciones.length; i++) {
                if (posiciones[i] < 0 || posiciones[i] > 360) {
                    showAlert(`⚠️ Posición M${i+1} fuera de rango (0-360°)`, 'warning');
                    return;
                }
            }

            try {
                const response = await fetch('/api/mover_posicion', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        posiciones: posiciones,
                        velocidad: velocidad
                    })
                });

                const result = await response.json();
                
                if (result.status === 'success') {
                    showAlert('✅ Movimiento a posición ejecutado');
                    actualizarEstado();
                } else {
                    showAlert(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showAlert('❌ Error de conexión', 'error');
            }
        }

        // Guardar posición actual
        async function guardarPosicion() {
            const nombre = prompt('Nombre para la posición:');
            if (!nombre) return;

            try {
                const response = await fetch('/api/guardar_posicion', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        nombre: nombre
                    })
                });

                const result = await response.json();
                
                if (result.status === 'success') {
                    showAlert(`✅ Posición "${nombre}" guardada`);
                } else {
                    showAlert(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showAlert('❌ Error de conexión', 'error');
            }
        }

        // Cargar posición de inicio
        function cargarPosicionInicio() {
            document.getElementById('pos-m1').value = 0;
            document.getElementById('pos-m2').value = 0;
            document.getElementById('pos-m3').value = 0;
            document.getElementById('pos-m4').value = 0;
            showAlert('📥 Posición de inicio cargada');
        }

        // Actualizar estado cada 3 segundos
        setInterval(actualizarEstado, 3000);
        
        // Actualizar al cargar la página
        document.addEventListener('DOMContentLoaded', actualizarEstado);
    </script>
</body>
</html>
'''

# ======================= RUTAS PRINCIPALES =======================
@app.route('/')
def dashboard():
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/comando/<accion>')
def enviar_comando(accion):
    """Comandos generales: ON, OFF, STOP, RESET, ABRIR, CERRAR"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO comandos_robot (esp32_id, comando) VALUES (%s, %s)",
            ('CDBOT_001', accion.upper())
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "comando": accion})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route('/api/mover_motor', methods=['POST'])
def mover_motor():
    """Mover motor específico con pasos y dirección"""
    try:
        data = request.json
        motor = data.get('motor')
        pasos = data.get('pasos')
        velocidad = data.get('velocidad')
        direccion = data.get('direccion')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO comandos_robot 
            (esp32_id, comando, motor_num, pasos, velocidad, direccion) 
            VALUES (%s, %s, %s, %s, %s, %s)""",
            ('CDBOT_001', 'MOVER_MOTOR', motor, pasos, velocidad, direccion)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success", 
            "mensaje": f"Motor M{motor} movido {direccion}"
        })
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route('/api/mover_posicion', methods=['POST'])
def mover_posicion():
    """Mover a posición específica de todos los motores"""
    try:
        data = request.json
        posiciones = data.get('posiciones', [])
        velocidad = data.get('velocidad', 500)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO comandos_robot 
            (esp32_id, comando, posicion_m1, posicion_m2, posicion_m3, posicion_m4, velocidad) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            ('CDBOT_001', 'MOVIMIENTO_POSICION', 
             posiciones[0], posiciones[1], posiciones[2], posiciones[3], velocidad)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "mensaje": "Movimiento a posición ejecutado"})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route('/api/guardar_posicion', methods=['POST'])
def guardar_posicion():
    """Guardar posición actual"""
    try:
        data = request.json
        nombre = data.get('nombre')
        
        # En una implementación real, aquí guardarías en una tabla de posiciones
        # Por ahora solo registramos el comando
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO comandos_robot (esp32_id, comando, parametros) VALUES (%s, %s, %s)",
            ('CDBOT_001', 'GUARDAR_POSICION', nombre)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "mensaje": f"Posición '{nombre}' guardada"})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route('/api/estado')
def obtener_estado():
    """Obtener estado actual del robot"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM moduls_tellis WHERE esp32_id = 'CDBOT_001' ORDER BY timestamp DESC LIMIT 1")
        estado = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if estado:
            return jsonify({
                "motores_activos": bool(estado[2]),
                "emergency_stop": bool(estado[3]), 
                "posicion_m1": float(estado[4]),
                "posicion_m2": float(estado[5]),
                "posicion_m3": float(estado[6]),
                "posicion_m4": float(estado[7]),
                "garra_abierta": bool(estado[8]),
                "velocidad_actual": int(estado[9])
            })
        else:
            return jsonify({"error": "No se encontró estado del robot"})
            
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

# ======================= INICIALIZACIÓN =======================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
