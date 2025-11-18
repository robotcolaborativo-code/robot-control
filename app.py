from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)

# Archivo para guardar las posiciones
POSITIONS_FILE = 'saved_positions.json'

def load_positions():
    try:
        with open(POSITIONS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_positions(positions):
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(positions, f)

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Control de Motores</title>
        <style>
            body { font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px; }
            .motor { border: 1px solid #ccc; padding: 10px; margin: 10px 0; }
            button { padding: 10px; margin: 5px; }
            .positions { border: 1px solid #ccc; padding: 10px; max-height: 200px; overflow-y: auto; }
        </style>
    </head>
    <body>
        <h1>Control de Posiciones de Motores</h1>
        
        <div id="motor-controls">
            <!-- M1 -->
            <div class="motor">
                <h3>M1</h3>
                <input type="number" id="m1-pos" value="0" min="0" max="360" placeholder="Grados">
                <input type="radio" name="m1-dir" value="H" checked> H
                <input type="radio" name="m1-dir" value="A"> A
                <button onclick="moveMotor('M1')">Mover M1</button>
            </div>
            
            <!-- M2 -->
            <div class="motor">
                <h3>M2</h3>
                <input type="number" id="m2-pos" value="0" min="0" max="360" placeholder="Grados">
                <input type="radio" name="m2-dir" value="H" checked> H
                <input type="radio" name="m2-dir" value="A"> A
                <button onclick="moveMotor('M2')">Mover M2</button>
            </div>
            
            <!-- M3 -->
            <div class="motor">
                <h3>M3</h3>
                <input type="number" id="m3-pos" value="0" min="0" max="360" placeholder="Grados">
                <input type="radio" name="m3-dir" value="H" checked> H
                <input type="radio" name="m3-dir" value="A"> A
                <button onclick="moveMotor('M3')">Mover M3</button>
            </div>
            
            <!-- M4 -->
            <div class="motor">
                <h3>M4</h3>
                <input type="number" id="m4-pos" value="0" min="0" max="360" placeholder="Grados">
                <input type="radio" name="m4-dir" value="H" checked> H
                <input type="radio" name="m4-dir" value="A"> A
                <button onclick="moveMotor('M4')">Mover M4</button>
            </div>
        </div>
        
        <!-- Garra -->
        <div class="motor">
            <h3>MS (Garra)</h3>
            <input type="radio" name="garra" value="ABRIR" checked> ABRIR
            <input type="radio" name="garra" value="CERRAR"> CERRAR
        </div>
        
        <!-- Velocidad -->
        <div class="motor">
            <h3>Velocidad (1-1000 RPM)</h3>
            <input type="number" id="speed" value="500" min="1" max="1000">
        </div>
        
        <!-- Botones -->
        <div>
            <button onclick="savePosition()" style="background: lightblue;">Guardar posición</button>
            <button onclick="moveSequential()" style="background: lightgreen;">MOVER SECUENCIAL</button>
            <button onclick="deletePosition()" style="background: lightcoral;">Eliminar posición</button>
        </div>
        
        <!-- Posiciones guardadas -->
        <div class="motor">
            <h3>Posiciones Guardadas</h3>
            <div id="positions-list" class="positions">
                <!-- Las posiciones se cargan aquí -->
            </div>
        </div>
        
        <!-- Botón Inicio -->
        <button onclick="homePosition()" style="background: yellow; width: 100%;">Inicio</button>
        
        <!-- Mensajes -->
        <div id="message" style="margin-top: 20px;"></div>

        <script>
            let selectedPosition = null;
            
            // Cargar posiciones al iniciar
            function loadPositions() {
                fetch('/get_positions')
                    .then(r => r.json())
                    .then(positions => {
                        const list = document.getElementById('positions-list');
                        list.innerHTML = '';
                        positions.forEach((pos, index) => {
                            const div = document.createElement('div');
                            div.innerHTML = `${pos.name} - Vel: ${pos.speed} RPM 
                                <button onclick="selectPosition(${index})">Seleccionar</button>`;
                            list.appendChild(div);
                        });
                    });
            }
            
            function selectPosition(index) {
                selectedPosition = index;
                document.getElementById('message').innerHTML = 
                    `<p style="color: green;">Posición ${index} seleccionada</p>`;
            }
            
            function moveMotor(motorName) {
                const pos = document.getElementById(`${motorName.toLowerCase()}-pos`).value;
                const dir = document.querySelector(`input[name="${motorName.toLowerCase()}-dir"]:checked`).value;
                const speed = document.getElementById('speed').value;
                
                fetch('/move_single', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({motor_name: motorName, position: pos, direction: dir, speed: speed})
                })
                .then(r => r.json())
                .then(data => {
                    document.getElementById('message').innerHTML = 
                        `<p style="color: green;">${data.message}</p>`;
                });
            }
            
            function savePosition() {
                const name = prompt('Nombre de la posición:');
                if (!name) return;
                
                const motors = [];
                for (let i = 1; i <= 4; i++) {
                    motors.push({
                        name: `M${i}`,
                        position: document.getElementById(`m${i}-pos`).value,
                        direction: document.querySelector(`input[name="m${i}-dir"]:checked`).value
                    });
                }
                
                const garra = document.querySelector('input[name="garra"]:checked').value;
                const speed = document.getElementById('speed').value;
                
                fetch('/save_position', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name, motors, garra, speed})
                })
                .then(r => r.json())
                .then(data => {
                    document.getElementById('message').innerHTML = 
                        `<p style="color: green;">${data.message}</p>`;
                    loadPositions();
                });
            }
            
            function moveSequential() {
                if (selectedPosition === null) {
                    alert('Selecciona una posición primero');
                    return;
                }
                
                fetch('/move_sequential', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({index: selectedPosition})
                })
                .then(r => r.json())
                .then(data => {
                    document.getElementById('message').innerHTML = 
                        `<p style="color: green;">${data.message}</p>`;
                });
            }
            
            function deletePosition() {
                if (selectedPosition === null) {
                    alert('Selecciona una posición primero');
                    return;
                }
                
                if (confirm('¿Eliminar esta posición?')) {
                    fetch('/delete_position', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({index: selectedPosition})
                    })
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('message').innerHTML = 
                            `<p style="color: green;">${data.message}</p>`;
                        selectedPosition = null;
                        loadPositions();
                    });
                }
            }
            
            function homePosition() {
                // Resetear valores
                for (let i = 1; i <= 4; i++) {
                    document.getElementById(`m${i}-pos`).value = 0;
                    document.querySelector(`input[name="m${i}-dir"][value="H"]`).checked = true;
                }
                document.querySelector('input[name="garra"][value="ABRIR"]').checked = true;
                document.getElementById('speed').value = 500;
                document.getElementById('message').innerHTML = 
                    '<p style="color: green;">Posición de inicio establecida</p>';
            }
            
            // Cargar posiciones al iniciar
            loadPositions();
        </script>
    </body>
    </html>
    '''

@app.route('/save_position', methods=['POST'])
def save_position():
    data = request.json
    positions = load_positions()
    
    position_data = {
        'name': data['name'],
        'motors': data['motors'],
        'garra': data['garra'],
        'speed': data['speed']
    }
    
    positions.append(position_data)
    save_positions(positions)
    
    return jsonify({'success': True, 'message': f'Posición "{data["name"]}" guardada'})

@app.route('/get_positions', methods=['GET'])
def get_positions():
    positions = load_positions()
    return jsonify(positions)

@app.route('/delete_position', methods=['POST'])
def delete_position():
    data = request.json
    index = data['index']
    
    positions = load_positions()
    if 0 <= index < len(positions):
        deleted_name = positions[index]['name']
        del positions[index]
        save_positions(positions)
        return jsonify({'success': True, 'message': f'Posición "{deleted_name}" eliminada'})
    
    return jsonify({'success': False, 'message': 'Error al eliminar'})

@app.route('/move_sequential', methods=['POST'])
def move_sequential():
    data = request.json
    position_index = data['index']
    
    positions = load_positions()
    if 0 <= position_index < len(positions):
        position = positions[position_index]
        
        # Simular movimiento
        movements = []
        for motor in position['motors']:
            movements.append(f"{motor['name']} → {motor['position']}° ({motor['direction']})")
        
        return jsonify({
            'success': True, 
            'message': f'Movimiento completado: {position["name"]}',
            'details': movements
        })
    
    return jsonify({'success': False, 'message': 'Posición no encontrada'})

@app.route('/move_single', methods=['POST'])
def move_single():
    data = request.json
    motor_name = data['motor_name']
    position = data['position']
    direction = data['direction']
    speed = data['speed']
    
    return jsonify({
        'success': True,
        'message': f'{motor_name} → {position}° ({direction}) a {speed} RPM'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
