from flask import Flask, jsonify, render_template_string
import mysql.connector
import os

app = Flask(__name__)

# Conexión QUE SÍ FUNCIONA
def get_db_connection():
    return mysql.connector.connect(
        host='turntable.proxy.rlwy.net',
        user='root',
        password='QttFmgSWJcoJfFKJNFwuscHPWPSESxWs',
        database='railway',
        port=57488
    )

# Crear tablas automáticamente
def crear_tablas():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Tabla de comandos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comandos_robot (
                id INT AUTO_INCREMENT PRIMARY KEY,
                esp32_id VARCHAR(50),
                comando VARCHAR(100),
                parametros TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de estado
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS moduls_tellis (
                id INT AUTO_INCREMENT PRIMARY KEY,
                esp32_id VARCHAR(50),
                motores_activos BOOLEAN,
                emergency_stop BOOLEAN,
                posicion_m1 INT,
                posicion_m2 INT,
                posicion_m3 INT,
                posicion_m4 INT,
                garra_abierta BOOLEAN
            )
        ''')
        
        # Insertar datos de ejemplo
        cursor.execute("SELECT COUNT(*) FROM moduls_tellis")
        count = cursor.fetchone()[0]
        
        if count == 0:
            cursor.execute('''
                INSERT INTO moduls_tellis 
                (esp32_id, motores_activos, emergency_stop, posicion_m1, posicion_m2, posicion_m3, posicion_m4, garra_abierta) 
                VALUES 
                ('CDBOT_001', 1, 0, 100, 200, 150, 250, 1)
            ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Tablas listas")
    except Exception as e:
        print(f"Error: {e}")

# Llamar al iniciar
crear_tablas()

# HTML del dashboard
HTML_DASHBOARD = '''
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard Robot</title>
    <style>
        body { font-family: Arial; margin: 40px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .btn { padding: 15px 25px; margin: 10px; font-size: 16px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 5px; transition: all 0.3s; }
        .btn:hover { background: #0056b3; transform: translateY(-2px); }
        .emergency { background: #dc3545; }
        .emergency:hover { background: #c82333; }
        .status { padding: 20px; background: #f8f9fa; margin: 20px 0; border-radius: 5px; border-left: 4px solid #007bff; }
        h1 { color: #333; text-align: center; margin-bottom: 30px; }
        .controls { text-align: center; margin: 30px 0; }
        .status-item { margin: 10px 0; padding: 10px; background: white; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Dashboard Control Robot</h1>
        
        <div class="status" id="estado">
            <h3>📊 Estado del Robot:</h3>
            <div id="datos-estado">Cargando...</div>
        </div>

        <div class="controls">
            <h3>🎮 Comandos de Movimiento:</h3>
            <button class="btn" onclick="enviarComando('forward')">⬆ Adelante</button>
            <button class="btn" onclick="enviarComando('backward')">⬇ Atrás</button>
            <br>
            <button class="btn" onclick="enviarComando('left')">⬅ Izquierda</button>
            <button class="btn" onclick="enviarComando('right')">➡ Derecha</button>
            <br>
            <button class="btn" onclick="enviarComando('stop')">⏹ Detener</button>
            <button class="btn emergency" onclick="enviarComando('emergency_stop')">🛑 PARADA EMERGENCIA</button>
        </div>
    </div>

    <script>
        async function enviarComando(accion) {
            try {
                const response = await fetch(`/api/comando/${accion}`);
                const result = await response.json();
                if (result.status === 'success') {
                    alert(`✅ Comando ${accion} enviado correctamente`);
                } else {
                    alert(`❌ Error: ${result.error}`);
                }
                actualizarEstado();
            } catch (error) {
                alert('❌ Error de conexión con el servidor');
            }
        }

        async function actualizarEstado() {
            try {
                const response = await fetch('/api/estado');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('datos-estado').innerHTML = 
                        `<div class="status-item">❌ ${data.error}</div>`;
                } else {
                    document.getElementById('datos-estado').innerHTML = `
                        <div class="status-item">🏃 Motores: <strong>${data.motores_activos ? 'ACTIVOS' : 'INACTIVOS'}</strong></div>
                        <div class="status-item">🛑 Emergencia: <strong>${data.emergency_stop ? 'ACTIVADA' : 'NORMAL'}</strong></div>
                        <div class="status-item">📊 Posición M1: <strong>${data.posicion_m1}</strong></div>
                        <div class="status-item">📊 Posición M2: <strong>${data.posicion_m2}</strong></div>
                        <div class="status-item">📊 Posición M3: <strong>${data.posicion_m3}</strong></div>
                        <div class="status-item">📊 Posición M4: <strong>${data.posicion_m4}</strong></div>
                        <div class="status-item">🤖 Garra: <strong>${data.garra_abierta ? 'ABIERTA' : 'CERRADA'}</strong></div>
                    `;
                }
            } catch (error) {
                document.getElementById('datos-estado').innerHTML = 
                    '<div class="status-item">❌ Error cargando estado del robot</div>';
            }
        }

        // Actualizar cada 3 segundos
        setInterval(actualizarEstado, 3000);
        actualizarEstado();
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/comando/<accion>')
def enviar_comando(accion):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
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
    try:
        conn = get_db_connection()
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
            return jsonify({"error": "No se encontró estado del robot"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
