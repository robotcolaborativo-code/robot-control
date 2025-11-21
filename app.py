from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
import mysql.connector
import os
import time
import threading
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ======================= CONFIGURACIÓN =======================
ESP32_IP = "10.31.183.131"  # IP del ESP32
TCP_PORT = 8080
SERIAL_MODE = False  # Por defecto usamos WiFi

# ======================= CONEXIÓN MYSQL =======================
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
        return conn
    except Exception as e:
        print(f"❌ Error conectando a MySQL: {e}")
        return None

# ======================= CONFIGURACIÓN INICIAL =======================
def setup_database():
    try:
        conn = get_db_connection()
        if conn is None:
            print("❌ No se pudo conectar a la base de datos")
            return False
            
        cursor = conn.cursor()
        
        # Crear tablas si no existen
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
                garra_grados FLOAT,
                velocidad_actual INT,
                conexion_wifi BOOLEAN,
                senal_wifi INT,
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
        
        # Insertar estado inicial si no existe
        cursor.execute("SELECT * FROM moduls_tellis WHERE esp32_id = 'cobot_01'")
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO moduls_tellis 
                (esp32_id, motores_activos, emergency_stop, posicion_m1, posicion_m2, posicion_m3, posicion_m4, garra_abierta, garra_grados, velocidad_actual, conexion_wifi, senal_wifi) 
                VALUES 
                ('cobot_01', 0, 0, 0, 0, 0, 0, 1, 100, 500, 0, 0)
            ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ BASE DE DATOS CONFIGURADA CORRECTAMENTE")
        return True
        
    except Exception as e:
        print(f"❌ Error configurando BD: {e}")
        return False

# ======================= COMUNICACIÓN CON ESP32 =======================
def enviar_comando_esp32(comando):
    """Enviar comando directamente al ESP32 vía TCP"""
    try:
        if SERIAL_MODE:
            print(f"📡 [SERIAL] Comando enviado: {comando}")
            return True
            
        # Modo WiFi - enviar via TCP
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        try:
            sock.connect((ESP32_IP, TCP_PORT))
            sock.sendall(f"{comando}\n".encode())
            response = sock.recv(1024).decode().strip()
            sock.close()
            
            print(f"📡 [WiFi] Comando enviado: {comando} -> Respuesta: {response}")
            return True
            
        except socket.timeout:
            print(f"❌ [WiFi] Timeout enviando comando: {comando}")
            return False
        except ConnectionRefusedError:
            print(f"❌ [WiFi] Conexión rechazada. Verifica que el ESP32 esté ejecutando el servidor TCP")
            return False
        except Exception as e:
            print(f"❌ [WiFi] Error enviando comando: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error general enviando comando: {e}")
        return False

def procesar_comando_bd(comando_data):
    """Procesar comando desde la base de datos y enviarlo al ESP32"""
    try:
        comando = comando_data.get('comando', '')
        motor_num = comando_data.get('motor_num')
        pasos = comando_data.get('pasos')
        velocidad = comando_data.get('velocidad')
        direccion = comando_data.get('direccion')
        posiciones = [
            comando_data.get('posicion_m1'),
            comando_data.get('posicion_m2'), 
            comando_data.get('posicion_m3'),
            comando_data.get('posicion_m4')
        ]
        
        comando_final = ""
        
        # Comandos simples
        if comando in ['ON', 'OFF', 'STOP', 'RESET', 'ABRIR', 'CERRAR']:
            comando_final = comando
            
        # Comando de movimiento directo
        elif comando == 'MOVER_MOTOR' and motor_num and pasos and velocidad and direccion:
            comando_final = f"M{motor_num},{direccion},{pasos},{velocidad}"
            
        # Comando de posición
        elif comando == 'MOVIMIENTO_POSICION' and all(p is not None for p in posiciones):
            pos_str = ','.join(str(p) for p in posiciones)
            comando_final = f"POS,{pos_str},{velocidad}"
            
        # Comando de cambio de modo
        elif comando.startswith('MODE:'):
            comando_final = comando
            
        else:
            print(f"⚠️ Comando no reconocido: {comando_data}")
            return False
            
        # Enviar comando al ESP32
        if comando_final:
            return enviar_comando_esp32(comando_final)
        else:
            return False
            
    except Exception as e:
        print(f"❌ Error procesando comando: {e}")
        return False

# ======================= THREAD PARA PROCESAR COMANDOS =======================
def procesador_comandos():
    """Thread que procesa comandos pendientes cada 2 segundos"""
    while True:
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                
                # Obtener comandos pendientes
                cursor.execute(
                    "SELECT * FROM comandos_robot WHERE ejecutado = FALSE ORDER BY timestamp ASC LIMIT 5"
                )
                comandos = cursor.fetchall()
                
                for cmd in comandos:
                    cmd_id = cmd[0]
                    comando_data = {
                        'comando': cmd[2],
                        'motor_num': cmd[4],
                        'pasos': cmd[5],
                        'velocidad': cmd[6],
                        'direccion': cmd[7],
                        'posicion_m1': cmd[8],
                        'posicion_m2': cmd[9],
                        'posicion_m3': cmd[10],
                        'posicion_m4': cmd[11]
                    }
                    
                    # Procesar comando
                    if procesar_comando_bd(comando_data):
                        # Marcar como ejecutado
                        cursor.execute(
                            "UPDATE comandos_robot SET ejecutado = TRUE WHERE id = %s",
                            (cmd_id,)
                        )
                        conn.commit()
                        print(f"✅ Comando {cmd_id} ejecutado: {comando_data['comando']}")
                    else:
                        print(f"❌ Error ejecutando comando {cmd_id}")
                
                cursor.close()
                conn.close()
                
        except Exception as e:
            print(f"❌ Error en procesador de comandos: {e}")
            
        time.sleep(2)  # Esperar 2 segundos entre ciclos

# Iniciar thread de procesamiento de comandos
threading.Thread(target=procesador_comandos, daemon=True).start()

# Configurar base de datos al inicio
setup_database()

# ======================= HTML DASHBOARD =======================
HTML_DASHBOARD = '''
<!DOCTYPE html>
<html>
<head>
    <title>🤖 Dashboard Control Robot 4DOF</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: linear-gradient(135deg, #0f2027, #203a43, #2c5364); color: white; min-height: 100vh; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; padding: 20px; background: rgba(255, 255, 255, 0.1); border-radius: 15px; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; background: linear-gradient(45deg, #00b4db, #0083b0); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3); }
        .dashboard-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        @media (max-width: 1024px) { .dashboard-grid { grid-template-columns: 1fr; } }
        .panel { background: rgba(255, 255, 255, 0.1); border-radius: 15px; padding: 25px; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); }
        .panel h2 { font-size: 1.8em; margin-bottom: 20px; color: #00b4db; border-bottom: 2px solid #00b4db; padding-bottom: 10px; }
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .status-item { background: rgba(0, 0, 0, 0.3); padding: 15px; border-radius: 10px; text-align: center; border-left: 4px solid #00b4db; }
        .status-item .label { font-size: 0.9em; opacity: 0.8; margin-bottom: 5px; }
        .status-item .value { font-size: 1.3em; font-weight: bold; color: #00b4db; }
        .status-item.emergency .value { color: #ff4444; }
        .status-item.active .value { color: #00C851; }
        .status-item.warning .value { color: #ffbb33; }
        .control-group { margin-bottom: 25px; }
        .control-group h3 { font-size: 1.3em; margin-bottom: 15px; color: #00b4db; }
        .btn-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-bottom: 15px; }
        .btn { padding: 12px 20px; border: none; border-radius: 8px; font-size: 1em; font-weight: bold; cursor: pointer; transition: all 0.3s ease; text-align: center; background: linear-gradient(45deg, #00b4db, #0083b0); color: white; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0, 180, 219, 0.4); }
        .btn-emergency { background: linear-gradient(45deg, #ff4444, #cc0000); }
        .btn-success { background: linear-gradient(45deg, #00C851, #007E33); }
        .btn-warning { background: linear-gradient(45deg, #ffbb33, #FF8800); }
        .input-group { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; align-items: center; margin-bottom: 10px; }
        .input-group input, .input-group select { padding: 10px; border: none; border-radius: 5px; background: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.3); }
        .input-group input:focus, .input-group select:focus { outline: none; border-color: #00b4db; }
        .motor-control { background: rgba(0, 0, 0, 0.2); padding: 15px; border-radius: 10px; margin-bottom: 15px; }
        .alert { padding: 15px; margin: 10px 0; border-radius: 5px; font-weight: bold; text-align: center; }
        .alert.success { background: rgba(0, 200, 81, 0.2); border: 1px solid #00C851; color: #00C851; }
        .alert.error { background: rgba(255, 68, 68, 0.2); border: 1px solid #ff4444; color: #ff4444; }
        .alert.warning { background: rgba(255, 187, 51, 0.2); border: 1px solid #ffbb33; color: #ffbb33; }
        .conexion-status { display: flex; align-items: center; gap: 10px; margin-bottom: 15px; }
        .status-indicator { width: 12px; height: 12px; border-radius: 50%; }
        .status-connected { background: #00C851; box-shadow: 0 0 10px #00C851; }
        .status-disconnected { background: #ff4444; box-shadow: 0 0 10px #ff4444; }
        .status-connecting { background: #ffbb33; box-shadow: 0 0 10px #ffbb33; animation: pulse 1s infinite; }
        .posiciones-container { background: rgba(0, 0, 0, 0.2); padding: 15px; border-radius: 10px; margin-top: 15px; }
        .posicion-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; margin: 5px 0; background: rgba(255, 255, 255, 0.1); border-radius: 5px; }
        .posicion-info { flex-grow: 1; }
        .posicion-actions { display: flex; gap: 5px; }
        .btn-small { padding: 5px 10px; font-size: 0.8em; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 DASHBOARD CONTROL ROBOT 4DOF</h1>
            <p>Control completo del robot colaborativo desde la nube</p>
        </div>

        <div id="alert-container"></div>

        <div class="dashboard-grid">
            <!-- PANEL IZQUIERDO: ESTADO Y CONTROL BÁSICO -->
            <div class="panel">
                <h2>📊 Estado del Robot</h2>
                
                <div class="conexion-status">
                    <div class="status-indicator status-connecting" id="status-indicator"></div>
                    <span id="conexion-text">Conectando al robot...</span>
                </div>
                
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
            </div>

            <!-- PANEL DERECHO: CONTROL AVANZADO -->
            <div class="panel">
                <h2>⚙️ Control Avanzado</h2>

                <div class="control-group">
                    <h3>🔧 Control Directo por Motor</h3>
                    
                    <div class="input-group">
                        <label for="motor-select">Motor:</label>
                        <select id="motor-select">
                            <option value="1">M1</option>
                            <option value="2">M2</option>
                            <option value="3">M3</option>
                            <option value="4">M4</option>
                        </select>
                    </div>

                    <div class="input-group">
                        <label for="pasos-input">Pasos:</label>
                        <input type="number" id="pasos-input" value="200" min="1" max="10000">
                    </div>

                    <div class="input-group">
                        <label for="velocidad-input">Velocidad (RPM):</label>
                        <input type="number" id="velocidad-input" value="500" min="1" max="1500">
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
                        <input type="number" id="velocidad-pos" value="500" min="1" max="1500">
                    </div>

                    <button class="btn" onclick="moverPosicion()" style="width: 100%; margin-top: 10px;">🧭 MOVER A POSICIÓN</button>
                </div>

                <div class="control-group">
                    <h3>💾 Posiciones Guardadas</h3>
                    
                    <div class="btn-grid">
                        <button class="btn" onclick="guardarPosicion()">💾 GUARDAR POSICIÓN</button>
                    </div>

                    <div class="posiciones-container">
                        <div id="lista-posiciones">Cargando posiciones...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function showAlert(message, type = 'success') {
            const alertContainer = document.getElementById('alert-container');
            const alert = document.createElement('div');
            alert.className = `alert ${type}`;
            alert.textContent = message;
            alertContainer.appendChild(alert);
            
            setTimeout(() => { alert.remove(); }, 5000);
        }

        function actualizarIndicadorConexion(estado) {
            const indicator = document.getElementById('status-indicator');
            const text = document.getElementById('conexion-text');
            
            if (estado === 'conectado') {
                indicator.className = 'status-indicator status-connected';
                text.textContent = 'Conectado al robot';
            } else if (estado === 'conectando') {
                indicator.className = 'status-indicator status-connecting';
                text.textContent = 'Conectando al robot...';
            } else {
                indicator.className = 'status-indicator status-disconnected';
                text.textContent = 'Desconectado';
            }
        }

        async function actualizarEstado() {
            try {
                const response = await fetch('/api/estado');
                const estado = await response.json();
                if (estado.error) {
                    document.getElementById('estado-container').innerHTML = `<div class="alert error">❌ ${estado.error}</div>`;
                    actualizarIndicadorConexion('desconectado');
                    return;
                }
                
                // Actualizar UI con estado
                document.getElementById('motores-activos').textContent = estado.motores_activos ? 'ACTIVOS' : 'INACTIVOS';
                document.getElementById('motores-activos').className = estado.motores_activos ? 'value active' : 'value';
                document.getElementById('emergency-stop').textContent = estado.emergency_stop ? 'ACTIVADA' : 'NORMAL';
                document.getElementById('garra-estado').textContent = estado.garra_abierta ? 'ABIERTA' : 'CERRADA';
                document.getElementById('velocidad-actual').textContent = estado.velocidad_actual + ' RPM';
                document.getElementById('posicion-m1').textContent = estado.posicion_m1 + '°';
                document.getElementById('posicion-m2').textContent = estado.posicion_m2 + '°';
                document.getElementById('posicion-m3').textContent = estado.posicion_m3 + '°';
                document.getElementById('posicion-m4').textContent = estado.posicion_m4 + '°';
                
                actualizarIndicadorConexion('conectado');
                
            } catch (error) {
                console.error('Error actualizando estado:', error);
                actualizarIndicadorConexion('desconectado');
            }
        }

        async function cargarPosiciones() {
            try {
                const response = await fetch('/api/posiciones');
                const result = await response.json();
                if (result.status === 'success') {
                    actualizarListaPosiciones(result.posiciones);
                }
            } catch (error) {
                console.error('Error cargando posiciones:', error);
            }
        }

        function actualizarListaPosiciones(posiciones) {
            const lista = document.getElementById('lista-posiciones');
            lista.innerHTML = '';
            if (posiciones.length === 0) {
                lista.innerHTML = '<div style="text-align: center; opacity: 0.7;">No hay posiciones guardadas</div>';
                return;
            }
            posiciones.forEach((pos) => {
                const item = document.createElement('div');
                item.className = 'posicion-item';
                item.innerHTML = `
                    <div class="posicion-info">
                        <strong>${pos.nombre}</strong><br>
                        <small>M1:${pos.posicion_m1}° M2:${pos.posicion_m2}° M3:${pos.posicion_m3}° M4:${pos.posicion_m4}°</small>
                    </div>
                    <div class="posicion-actions">
                        <button class="btn btn-small" onclick="cargarPosicion(${pos.id})">📥</button>
                        <button class="btn btn-small btn-warning" onclick="eliminarPosicion(${pos.id})">🗑️</button>
                    </div>
                `;
                lista.appendChild(item);
            });
        }

        async function cargarPosicion(id) {
            try {
                const response = await fetch(`/api/cargar_posicion/${id}`);
                const result = await response.json();
                if (result.status === 'success') {
                    const pos = result.posicion;
                    document.getElementById('pos-m1').value = pos.posicion_m1;
                    document.getElementById('pos-m2').value = pos.posicion_m2;
                    document.getElementById('pos-m3').value = pos.posicion_m3;
                    document.getElementById('pos-m4').value = pos.posicion_m4;
                    document.getElementById('velocidad-pos').value = pos.velocidad;
                    showAlert(`✅ Posición "${pos.nombre}" cargada`);
                } else {
                    showAlert(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showAlert('❌ Error de conexión', 'error');
            }
        }

        async function eliminarPosicion(id) {
            if (!confirm('¿Estás seguro de que quieres eliminar esta posición?')) return;
            try {
                const response = await fetch(`/api/eliminar_posicion/${id}`, { method: 'DELETE' });
                const result = await response.json();
                if (result.status === 'success') {
                    showAlert('✅ Posición eliminada');
                    cargarPosiciones();
                } else {
                    showAlert(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showAlert('❌ Error de conexión', 'error');
            }
        }

        async function sendCommand(comando) {
            try {
                const response = await fetch(`/api/comando/${comando}`);
                const result = await response.json();
                if (result.status === 'success') {
                    showAlert(`✅ Comando ${comando} enviado correctamente`);
                    setTimeout(actualizarEstado, 1000);
                } else {
                    showAlert(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showAlert('❌ Error de conexión con el servidor', 'error');
            }
        }

        async function controlGarra(estado) {
            await sendCommand(estado);
        }

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
                    headers: { 'Content-Type': 'application/json' },
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
                    setTimeout(actualizarEstado, 2000);
                } else {
                    showAlert(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showAlert('❌ Error de conexión', 'error');
            }
        }

        async function moverPosicion() {
            const posiciones = [
                parseFloat(document.getElementById('pos-m1').value),
                parseFloat(document.getElementById('pos-m2').value),
                parseFloat(document.getElementById('pos-m3').value),
                parseFloat(document.getElementById('pos-m4').value)
            ];
            const velocidad = parseInt(document.getElementById('velocidad-pos').value);
            for (let i = 0; i < posiciones.length; i++) {
                if (posiciones[i] < 0 || posiciones[i] > 360) {
                    showAlert(`⚠️ Posición M${i+1} fuera de rango (0-360°)`, 'warning');
                    return;
                }
            }
            try {
                const response = await fetch('/api/mover_posicion', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ posiciones: posiciones, velocidad: velocidad })
                });
                const result = await response.json();
                if (result.status === 'success') {
                    showAlert('✅ Movimiento a posición ejecutado');
                    setTimeout(actualizarEstado, 3000);
                } else {
                    showAlert(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showAlert('❌ Error de conexión', 'error');
            }
        }

        async function guardarPosicion() {
            const nombre = prompt('Nombre para la posición:');
            if (!nombre) return;
            const posiciones = [
                parseFloat(document.getElementById('pos-m1').value),
                parseFloat(document.getElementById('pos-m2').value),
                parseFloat(document.getElementById('pos-m3').value),
                parseFloat(document.getElementById('pos-m4').value)
            ];
            const velocidad = parseInt(document.getElementById('velocidad-pos').value);
            try {
                const response = await fetch('/api/guardar_posicion', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        nombre: nombre,
                        posiciones: posiciones,
                        velocidad: velocidad
                    })
                });
                const result = await response.json();
                if (result.status === 'success') {
                    showAlert(`✅ Posición "${nombre}" guardada`);
                    cargarPosiciones();
                } else {
                    showAlert(`❌ Error: ${result.error}`, 'error');
                }
            } catch (error) {
                showAlert('❌ Error de conexión', 'error');
            }
        }

        // Actualizar estado cada 3 segundos
        setInterval(actualizarEstado, 3000);
        setInterval(cargarPosiciones, 5000);
        
        document.addEventListener('DOMContentLoaded', function() {
            actualizarEstado();
            cargarPosiciones();
            actualizarIndicadorConexion('conectando');
        });
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
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"}), 500
            
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO comandos_robot (esp32_id, comando) VALUES (%s, %s)",
            ('cobot_01', accion.upper())
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "comando": accion})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

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
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"}), 500
            
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO comandos_robot 
            (esp32_id, comando, motor_num, pasos, velocidad, direccion) 
            VALUES (%s, %s, %s, %s, %s, %s)""",
            ('cobot_01', 'MOVER_MOTOR', motor, pasos, velocidad, direccion)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success", 
            "mensaje": f"Motor M{motor} movido {direccion}"
        })
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/mover_posicion', methods=['POST'])
def mover_posicion():
    """Mover a posición específica de todos los motores"""
    try:
        data = request.json
        posiciones = data.get('posiciones', [])
        velocidad = data.get('velocidad', 500)
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"}), 500
            
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO comandos_robot 
            (esp32_id, comando, posicion_m1, posicion_m2, posicion_m3, posicion_m4, velocidad) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            ('cobot_01', 'MOVIMIENTO_POSICION', 
             posiciones[0], posiciones[1], posiciones[2], posiciones[3], velocidad)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "mensaje": "Movimiento a posición ejecutado"})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/guardar_posicion', methods=['POST'])
def guardar_posicion():
    """Guardar posición en la base de datos"""
    try:
        data = request.json
        nombre = data.get('nombre')
        posiciones = data.get('posiciones', [])
        velocidad = data.get('velocidad', 500)
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"}), 500
            
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO posiciones_guardadas 
            (nombre, posicion_m1, posicion_m2, posicion_m3, posicion_m4, velocidad) 
            VALUES (%s, %s, %s, %s, %s, %s)""",
            (nombre, posiciones[0], posiciones[1], posiciones[2], posiciones[3], velocidad)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "mensaje": f"Posición '{nombre}' guardada"})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/posiciones')
def obtener_posiciones():
    """Obtener lista de posiciones guardadas"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"}), 500
            
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM posiciones_guardadas ORDER BY nombre")
        posiciones = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        posiciones_list = []
        for pos in posiciones:
            posiciones_list.append({
                "id": pos[0],
                "nombre": pos[1],
                "posicion_m1": float(pos[2]),
                "posicion_m2": float(pos[3]),
                "posicion_m3": float(pos[4]),
                "posicion_m4": float(pos[5]),
                "velocidad": int(pos[7])
            })
        
        return jsonify({"status": "success", "posiciones": posiciones_list})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/cargar_posicion/<int:posicion_id>')
def cargar_posicion(posicion_id):
    """Cargar una posición específica"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"}), 500
            
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM posiciones_guardadas WHERE id = %s", (posicion_id,))
        posicion = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if posicion:
            posicion_data = {
                "id": posicion[0],
                "nombre": posicion[1],
                "posicion_m1": float(posicion[2]),
                "posicion_m2": float(posicion[3]),
                "posicion_m3": float(posicion[4]),
                "posicion_m4": float(posicion[5]),
                "velocidad": int(posicion[7])
            }
            return jsonify({"status": "success", "posicion": posicion_data})
        else:
            return jsonify({"status": "error", "error": "Posición no encontrada"})
            
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/eliminar_posicion/<int:posicion_id>', methods=['DELETE'])
def eliminar_posicion(posicion_id):
    """Eliminar una posición guardada"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"}), 500
            
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM posiciones_guardadas WHERE id = %s", (posicion_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "mensaje": "Posición eliminada"})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/estado')
def obtener_estado():
    """Obtener estado actual del robot"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"}), 500
            
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM moduls_tellis WHERE esp32_id = 'cobot_01' ORDER BY timestamp DESC LIMIT 1")
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
                "garra_grados": float(estado[9]),
                "velocidad_actual": int(estado[10]),
                "conexion_wifi": bool(estado[11]),
                "senal_wifi": int(estado[12]),
                "timestamp": estado[13].isoformat() if estado[13] else datetime.now().isoformat()
            })
        else:
            return jsonify({"error": "No se encontró estado del robot"})
            
    except Exception as e:
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
        
        # Determinar estado de garra basado en grados
        garra_grados = data.get('garra_deg', 100)
        garra_abierta = garra_grados >= 50  # 100° = abierto, 0° = cerrado
        
        cursor.execute('''
            INSERT INTO moduls_tellis 
            (esp32_id, motores_activos, emergency_stop, posicion_m1, posicion_m2, posicion_m3, posicion_m4, garra_abierta, garra_grados, velocidad_actual, conexion_wifi, senal_wifi) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            data.get('esp32_id', 'cobot_01'),
            data.get('motors_active', False),
            data.get('emergency_stop', False),
            data.get('motor1_deg', 0),
            data.get('motor2_deg', 0), 
            data.get('motor3_deg', 0),
            data.get('motor4_deg', 0),
            garra_abierta,
            garra_grados,
            data.get('velocidad_actual', 500),
            data.get('connection_mode') == 'WIFI',
            data.get('wifi_signal', 0)
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "message": "Estado actualizado"})
        
    except Exception as e:
        print(f"❌ Error actualizando estado: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/test')
def test_api():
    """Ruta de prueba"""
    return jsonify({
        "status": "success", 
        "message": "✅ API funcionando correctamente",
        "timestamp": time.time()
    })

# ======================= INICIALIZACIÓN =======================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Iniciando servidor Flask en puerto {port}")
    print("✅ Dashboard disponible en: http://localhost:5000")
    app.run(host='0.0.0.0', port=port, debug=False)
