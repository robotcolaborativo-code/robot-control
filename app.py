from flask import Flask, jsonify, render_template_string, request
import mysql.connector
import os
import time

app = Flask(__name__)

# ======================= CONEXIÓN MYSQL CON VARIABLES DE ENTORNO =======================
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.environ.get('MYSQL_HOST', 'turntable.proxy.rlwy.net'),
            user=os.environ.get('MYSQL_USER', 'root'),
            password=os.environ.get('MYSQL_PASSWORD', 'QttFmgSWJcoJfFKJNFwuscHPWPSESxWs'),
            database=os.environ.get('MYSQL_DATABASE', 'railway'),
            port=int(os.environ.get('MYSQL_PORT', 57488))
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
            return
            
        cursor = conn.cursor()
        
        # Verificar si las tablas ya existen
        cursor.execute("SHOW TABLES LIKE 'comandos_robot'")
        if cursor.fetchone():
            print("✅ Tablas ya existen, saltando creación")
            cursor.close()
            conn.close()
            return
            
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
        
        # Insertar estado inicial si no existe
        cursor.execute("SELECT * FROM moduls_tellis WHERE esp32_id = 'CDBOT_001'")
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO moduls_tellis 
                (esp32_id, motores_activos, emergency_stop, posicion_m1, posicion_m2, posicion_m3, posicion_m4, garra_abierta, velocidad_actual) 
                VALUES 
                ('CDBOT_001', 1, 0, 0, 0, 0, 0, 1, 500)
            ''')
        
        # Insertar posiciones de ejemplo si no existen
        cursor.execute("SELECT COUNT(*) FROM posiciones_guardadas")
        if cursor.fetchone()[0] == 0:
            posiciones_ejemplo = [
                ('Inicio', 0, 0, 0, 0, 'ABRIR', 500),
                ('Posición 1', 90, 45, 60, 30, 'CERRAR', 400),
                ('Posición 2', 180, 90, 120, 60, 'ABRIR', 600),
                ('Esquina', 270, 135, 180, 90, 'CERRAR', 300)
            ]
            
            for pos in posiciones_ejemplo:
                cursor.execute('''
                    INSERT INTO posiciones_guardadas 
                    (nombre, posicion_m1, posicion_m2, posicion_m3, posicion_m4, garra_estado, velocidad) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', pos)
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ BASE DE DATOS CONFIGURADA CORRECTAMENTE")
        
    except Exception as e:
        print(f"❌ Error configurando BD: {e}")

# Configurar base de datos al inicio
setup_database()

# ======================= RUTAS PRINCIPALES =======================
@app.route('/')
def dashboard():
    # Tu HTML_DASHBOARD completo aquí (lo mantienes igual)
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/comando/<accion>')
def enviar_comando(accion):
    """Comandos generales: ON, OFF, STOP, RESET, ABRIR, CERRAR"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"})
            
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

@app.route('/api/comandos_pendientes/<esp32_id>')
def obtener_comandos_pendientes(esp32_id):
    """Obtener comandos pendientes para un ESP32 - RUTA CRÍTICA"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"})
            
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
                "parametros": cmd[3],
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
        return jsonify({"status": "error", "error": str(e)})

@app.route('/api/actualizar_estado', methods=['POST'])
def actualizar_estado():
    """Actualizar estado del robot desde el ESP32 - RUTA CRÍTICA"""
    try:
        data = request.json
        print(f"📊 Estado recibido del ESP32: {data}")
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "error": "No database connection"})
            
        cursor = conn.cursor()
        
        # Verificar si existe un registro para este ESP32
        cursor.execute("SELECT id FROM moduls_tellis WHERE esp32_id = %s", (data.get('esp32_id', 'CDBOT_001'),))
        existing = cursor.fetchone()
        
        if existing:
            # Actualizar registro existente
            cursor.execute(
                """UPDATE moduls_tellis SET 
                motores_activos = %s, emergency_stop = %s, 
                posicion_m1 = %s, posicion_m2 = %s, posicion_m3 = %s, posicion_m4 = %s,
                garra_abierta = %s, velocidad_actual = %s, timestamp = CURRENT_TIMESTAMP
                WHERE esp32_id = %s""",
                (
                    data.get('motors_active', False),
                    data.get('emergency_stop', False),
                    data.get('motor1_deg', 0),
                    data.get('motor2_deg', 0), 
                    data.get('motor3_deg', 0),
                    data.get('motor4_deg', 0),
                    data.get('garra_state') == 'ABIERTA',
                    data.get('velocidad_actual', 500),
                    data.get('esp32_id', 'CDBOT_001')
                )
            )
        else:
            # Insertar nuevo registro
            cursor.execute(
                """INSERT INTO moduls_tellis 
                (esp32_id, motores_activos, emergency_stop, posicion_m1, posicion_m2, posicion_m3, posicion_m4, garra_abierta, velocidad_actual) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    data.get('esp32_id', 'CDBOT_001'),
                    data.get('motors_active', False),
                    data.get('emergency_stop', False),
                    data.get('motor1_deg', 0),
                    data.get('motor2_deg', 0), 
                    data.get('motor3_deg', 0),
                    data.get('motor4_deg', 0),
                    data.get('garra_state') == 'ABIERTA',
                    data.get('velocidad_actual', 500)
                )
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"status": "success", "message": "Estado actualizado"})
        
    except Exception as e:
        print(f"❌ Error actualizando estado: {e}")
        return jsonify({"status": "error", "error": str(e)})

# ... (mantén todas las demás rutas igual)

@app.route('/api/test')
def test_api():
    """Ruta de prueba para verificar que la API funciona"""
    return jsonify({
        "status": "success", 
        "message": "✅ API funcionando correctamente",
        "timestamp": time.time()
    })

# ======================= INICIALIZACIÓN =======================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
