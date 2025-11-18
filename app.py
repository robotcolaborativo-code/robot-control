from flask import Flask, render_template_string, request, jsonify
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
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Control de Posiciones de Motores</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 500px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f0f0f0;
        }
        .container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 20px;
        }
        .motor-row {
            display: flex;
            align-items: center;
            margin: 5px 0;
            padding: 5px;
        }
        .motor-label {
            width: 40px;
            font-weight: bold;
        }
        .motor-input {
            width: 50px;
            margin: 0 10px;
            padding: 5px;
        }
        .radio-group {
            margin: 0 10px;
        }
        .garra-row {
            display: flex;
            align-items: center;
            margin: 10px 0;
            padding: 5px;
        }
        .speed-row {
            display: flex;
            align-items: center;
            margin: 10px 0;
            padding: 5px;
        }
        .speed-label {
            width: 180px;
        }
        .speed-input {
            width: 60px;
            padding: 5px;
            margin-left: 10px;
        }
        .buttons-row {
            display: flex;
            justify-content: space-between;
            margin: 15px 0;
        }
        .button {
            padding: 10px 15px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            width: 30%;
        }
        .save-btn { background-color: lightblue; }
        .sequential-btn { background-color: lightgreen; }
        .delete-btn { background-color: lightcoral; }
        .positions-container {
            margin: 15px 0;
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 10px;
        }
        .positions-list {
            max-height: 150px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 5px;
            margin: 10px 0;
        }
        .position-item {
            padding: 5px;
            margin: 2px 0;
            cursor: pointer;
            border-radius: 3px;
        }
        .position-item:hover {
            background-color: #f0f0f0;
        }
        .position-item.selected {
            background-color: #e3f2fd;
        }
        .home-btn {
            background-color: yellow;
            padding: 12px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            width: 100%;
            margin-top: 10px;
        }
        .message {
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
            text-align: center;
        }
        .success { background-color: #d4edda; color: #155724; }
        .error { background-color: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Posiciones (grados°)</h1>
        
        <!-- Motores M1 a M4 -->
        <div id="motors-container">
            <div class="motor-row">
                <div class="motor-label">M1</div>
                <input type="number" class="motor-input" id="m1-pos" value="0" min="0" max="360">
                <div class="radio-group">
                    <input type="radio" name="m1-dir" value="H" checked> H
                    <input type="radio" name="m1-dir" value="A"> A
                </div>
            </div>
            <div class="motor-row">
                <div class="motor-label">M2</div>
                <input type="number" class="motor-input" id="m2-pos" value="0" min="0" max="360">
                <div class="radio-group">
                    <input type="radio" name="m2-dir" value="H" checked> H
                    <input type="radio" name="m2-dir" value="A"> A
                </div>
            </div>
            <div class="motor-row">
                <div class="motor-label">M3</div>
                <input type="number" class="motor-input" id="m3-pos" value="0" min="0" max="360">
                <div class="radio-group">
                    <input type="radio" name="m3-dir" value="H" checked> H
                    <input type="radio" name="m3-dir" value="A"> A
                </div>
            </div>
            <div class="motor-row">
                <div class="motor-label">M4</div>
                <input type="number" class="motor-input" id="m4-pos" value="0" min="0" max="360">
                <div class="radio-group">
                    <input type="radio" name="m4-dir" value="H" checked> H
                    <input type="radio" name="m4-dir" value="A"> A
                </div>
            </div>
        </div>
        
        <!-- Garra -->
        <div class="garra-row">
            <div class="motor-label">MS (Garra)</div>
            <div class="radio-group">
                <input type="radio" name="garra" value="ABRIR" checked> ABRIR
                <input type="radio" name="garra" value="CERRAR"> CERRAR
            </div>
        </div>
        
        <!-- Velocidad -->
        <div class="speed-row">
            <div class="speed-label">Velocidad (1-1000 RPM)</div>
            <input type="number" class="speed-input" id="speed" value="500" min="1" max="1000">
        </div>
        
        <!-- Botones -->
        <div class="buttons-row">
            <button class="button save-btn" onclick="savePosition()">Guardar posición</button>
            <button class="button sequential-btn" onclick="moveSequential()">MOVER SECUENCIAL</button>
            <button class="button delete-btn" onclick="deletePosition()">Eliminar posición</button>
        </div>
        
        <!-- Posiciones Guardadas -->
        <div class="positions-container">
            <strong>Posiciones Guardadas:</strong>
            <div id="positions-list" class="positions-list">
                <!-- Las posiciones se cargarán aquí -->
            </div>
        </div>
        
        <!-- Botón Inicio -->
        <button class="home-btn" onclick="homePosition()">Inicio</button>
        
        <!-- Mensajes -->
        <div id="message"></div>
    </div>

    <script>
        let selectedPosition = null;
        
        // Cargar posiciones al iniciar
        function loadPositions() {
            fetch('/get_positions')
                .then(response => response.json())
                .then(positions => {
                    const list = document.getElementById('positions-list');
                    list.innerHTML = '';
                    
                    positions.forEach((pos, index) => {
                        const div = document.createElement('div');
                        div.className = 'position-item';
                        div.textContent = `${pos.name} - Vel: ${pos.speed} RPM`;
                        div.onclick = () => selectPosition(index);
                        list.appendChild(div);
                    });
                });
        }
        
        function selectPosition(index) {
            selectedPosition = index;
            // Remover selección anterior
            document.querySelectorAll('.position-item').forEach(item => {
                item.classList.remove('selected');
            });
            // Agregar selección actual
            document.querySelectorAll('.position-item')[index].classList.add('selected');
            showMessage(`Posición "${positionsCache[index].name}" seleccionada`, 'success');
        }
        
        let positionsCache = [];
        
        function savePosition() {
            const name = prompt('Nombre de la posición:');
            if (!name) return;
            
            const motors = [];
            for (let i = 1; i <= 4; i++) {
                const pos = document.getElementById(`m${i}-pos`).value;
                const dir = document.querySelector(`input[name="m${i}-dir"]:checked`).value;
                motors.push({
                    name: `M${i}`,
                    position: pos,
                    direction: dir
                });
            }
            
            const garra = document.querySelector('input[name="garra"]:checked').value;
            const speed = document.getElementById('speed').value;
            
            fetch('/save_position', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name, motors, garra, speed})
            })
            .then(response => response.json())
            .then(data => {
                showMessage(data.message, 'success');
                loadPositions();
            });
        }
        
        function moveSequential() {
            if (selectedPosition === null) {
                showMessage('Selecciona una posición de la lista primero', 'error');
                return;
            }
            
            fetch('/move_sequential', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index: selectedPosition})
            })
            .then(response => response.json())
            .then(data => {
                showMessage(data.message, 'success');
            });
        }
        
        function deletePosition() {
            if (selectedPosition === null) {
                showMessage('Selecciona una posición para eliminar', 'error');
                return;
            }
            
            if (confirm('¿Estás seguro de que quieres eliminar esta posición?')) {
                fetch('/delete_position', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({index: selectedPosition})
                })
                .then(response => response.json())
                .then(data => {
                    showMessage(data.message, 'success');
                    selectedPosition = null;
                    loadPositions();
                });
            }
        }
        
        function homePosition() {
            // Resetear todos los valores
            for (let i = 1; i <= 4; i++) {
                document.getElementById(`m${i}-pos`).value = 0;
                document.querySelector(`input[name="m${i}-dir"][value="H"]`).checked = true;
            }
            document.querySelector('input[name="garra"][value="ABRIR"]').checked = true;
            document.getElementById('speed').value = 500;
            showMessage('Todos los motores en posición de inicio', 'success');
        }
        
        function showMessage(message, type) {
            const messageDiv = document.getElementById('message');
            messageDiv.innerHTML = `<div class="message ${type}">${message}</div>`;
            setTimeout(() => {
                messageDiv.innerHTML = '';
            }, 3000);
        }
        
        // Cargar posiciones al iniciar y cachearlas
        fetch('/get_positions')
            .then(response => response.json())
            .then(positions => {
                positionsCache = positions;
                loadPositions();
            });
    </script>
</body>
</html>
    ''')

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
    
    return jsonify({'success': True, 'message': f'Posición "{data["name"]}" guardada correctamente'})

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
        
        # Simular movimiento secuencial
        movements = []
        for motor in position['motors']:
            movements.append(f"Moviendo {motor['name']} a {motor['position']}°, dirección {motor['direction']}")
        
        movements.append(f"Garra: {position['garra']}")
        movements.append(f"Velocidad: {position['speed']} RPM")
        
        return jsonify({
            'success': True, 
            'message': f'Movimiento secuencial completado para {position["name"]}',
            'movements': movements
        })
    
    return jsonify({'success': False, 'message': 'Posición no encontrada'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
