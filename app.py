from flask import Flask, request
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
DATABASE = 'robot.db'

def crear_tablas():
    conn = sqlite3.connect(DATABASE)  # ✅ CORREGIDO
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS moduls_tellis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            esp32_id TEXT DEFAULT 'CDBOT_001',
            motores_activos BOOLEAN DEFAULT 0,
            emergency_stop BOOLEAN DEFAULT 0,
            posicion_m1 REAL DEFAULT 0,
            posicion_m2 REAL DEFAULT 0,
            posicion_m3 REAL DEFAULT 0,
            posicion_m4 REAL DEFAULT 0,
            garra_abierta BOOLEAN DEFAULT 1,
            fecha DATE
        )
    ''')
    
    cursor.execute('''
        INSERT OR IGNORE INTO moduls_tellis 
        (id, esp32_id, motores_activos, garra_abierta, fecha) 
        VALUES (1, 'CDBOT_001', 1, 0, ?)
    ''', (datetime.now().date(),))
    
    conn.commit()
    conn.close()

def actualizar_estado(campo, valor):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE moduls_tellis SET {campo} = ? WHERE id = 1", (valor,))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    crear_tablas()
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM moduls_tellis WHERE id = 1")
    fila = cursor.fetchone()
    
    # Crear HTML con botones de control
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Control del Robot</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f0f2f5; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            .estado {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }}
            .activo {{ color: green; font-weight: bold; }}
            .inactivo {{ color: red; font-weight: bold; }}
            .robot-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
            .botones {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 20px 0; }}
            .btn {{ padding: 15px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; font-weight: bold; text-decoration: none; text-align: center; }}
            .btn-activar {{ background: #28a745; color: white; }}
            .btn-desactivar {{ background: #dc3545; color: white; }}
            .btn-garra {{ background: #17a2b8; color: white; }}
            .btn-emergencia {{ background: #ffc107; color: black; grid-column: span 2; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Control del Robot Inteligente</h1>
            
            <div class="robot-card">
                <h2>Estado Actual del Robot</h2>
                <div class="estado">
                    <p><strong>ID:</strong> {fila[1] if fila else 'CDBOT_001'}</p>
                    <p><strong>Motores:</strong> 
                        <span class="{'activo' if (fila and fila[2]) else 'inactivo'}">
                            {'🟢 ACTIVOS' if (fila and fila[2]) else '🔴 INACTIVOS'}
                        </span>
                    </p>
                    <p><strong>Garra:</strong> 
                        <span class="{'activo' if (fila and fila[8]) else 'inactivo'}">
                            {'🟢 ABIERTA' if (fila and fila[8]) else '🔴 CERRADA'}
                        </span>
                    </p>
                    <p><strong>Paro Emergencia:</strong> 
                        <span class="{'inactivo' if (fila and fila[3]) else 'activo'}">
                            {'🔴 ACTIVADO' if (fila and fila[3]) else '🟢 NORMAL'}
                        </span>
                    </p>
                    <p><strong>Posiciones:</strong> M1={fila[4] if fila else 0}° | M2={fila[5] if fila else 0}° | M3={fila[6] if fila else 0}° | M4={fila[7] if fila else 0}°</p>
                </div>
            </div>

            <div class="botones">
                <a href="/activar_motores" class="btn btn-activar">✅ ACTIVAR MOTORES</a>
                <a href="/desactivar_motores" class="btn btn-desactivar">⛔ DESACTIVAR MOTORES</a>
                <a href="/abrir_garra" class="btn btn-garra">🔓 ABRIR GARRA</a>
                <a href="/cerrar_garra" class="btn btn-garra">🔒 CERRAR GARRA</a>
                <a href="/emergencia" class="btn btn-emergencia">🚨 PARO DE EMERGENCIA</a>
            </div>

            <div style="text-align: center; margin-top: 20px;">
                <p><strong>Última actualización:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    conn.close()
    return html

# --- BOTONES DE CONTROL ---
@app.route('/activar_motores')
def activar_motores():
    actualizar_estado('motores_activos', 1)
    return '''
    <script>
        alert("Motores activados ✅");
        window.location.href = "/";
    </script>
    '''

@app.route('/desactivar_motores')
def desactivar_motores():
    actualizar_estado('motores_activos', 0)
    return '''
    <script>
        alert("Motores desactivados ⛔");
        window.location.href = "/";
    </script>
    '''

@app.route('/abrir_garra')
def abrir_garra():
    actualizar_estado('garra_abierta', 1)
    return '''
    <script>
        alert("Garra abierta 🔓");
        window.location.href = "/";
    </script>
    '''

@app.route('/cerrar_garra')
def cerrar_garra():
    actualizar_estado('garra_abierta', 0)
    return '''
    <script>
        alert("Garra cerrada 🔒");
        window.location.href = "/";
    </script>
    '''

@app.route('/emergencia')
def emergencia():
    actualizar_estado('emergency_stop', 1)
    actualizar_estado('motores_activos', 0)
    return '''
    <script>
        alert("🚨 PARO DE EMERGENCIA ACTIVADO");
        window.location.href = "/";
    </script>
    '''

if __name__ == '__main__':
    # Para producción en Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
