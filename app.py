import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

class MotorControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Control de Posiciones de Motores")
        self.root.geometry("600x700")
        
        # Almacenar posiciones guardadas
        self.saved_positions = []
        
        self.create_widgets()
        
    def create_widgets(self):
        # Título
        title_label = tk.Label(self.root, text="Posiciones (grados°)", font=("Arial", 14, "bold"))
        title_label.pack(pady=10)
        
        # Frame principal para motores
        main_frame = tk.Frame(self.root)
        main_frame.pack(pady=10, fill="both", expand=True)
        
        # Crear controles para M1 a M4
        self.motor_frames = []
        for i in range(1, 5):
            motor_frame = self.create_motor_control(main_frame, f"M{i}")
            motor_frame.pack(pady=5, fill="x")
            self.motor_frames.append(motor_frame)
        
        # Control para M5 (Garra)
        garra_frame = tk.LabelFrame(main_frame, text="MS (Garra)", font=("Arial", 10, "bold"))
        garra_frame.pack(pady=10, fill="x")
        
        self.garra_var = tk.StringVar(value="ABRIR")
        tk.Radiobutton(garra_frame, text="ABRIR", variable=self.garra_var, value="ABRIR").pack(side="left", padx=10)
        tk.Radiobutton(garra_frame, text="CERRAR", variable=self.garra_var, value="CERRAR").pack(side="left", padx=10)
        
        # Control de velocidad
        speed_frame = tk.LabelFrame(main_frame, text="Velocidad (1-1000 RPM)", font=("Arial", 10, "bold"))
        speed_frame.pack(pady=10, fill="x")
        
        self.speed_var = tk.StringVar(value="500")
        speed_entry = tk.Entry(speed_frame, textvariable=self.speed_var, font=("Arial", 12), justify="center")
        speed_entry.pack(pady=5, padx=10, fill="x")
        
        # Botones de control
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=10, fill="x")
        
        tk.Button(button_frame, text="Guardar posición", command=self.save_position, 
                  bg="lightblue", font=("Arial", 10)).pack(side="left", padx=5, fill="x", expand=True)
        
        tk.Button(button_frame, text="MOVER SECUENCIAL", command=self.move_sequential, 
                  bg="lightgreen", font=("Arial", 10)).pack(side="left", padx=5, fill="x", expand=True)
        
        tk.Button(button_frame, text="Eliminar posición", command=self.delete_position, 
                  bg="lightcoral", font=("Arial", 10)).pack(side="left", padx=5, fill="x", expand=True)
        
        # Lista de posiciones guardadas
        positions_frame = tk.LabelFrame(main_frame, text="Posiciones Guardadas", font=("Arial", 10, "bold"))
        positions_frame.pack(pady=10, fill="both", expand=True)
        
        # Listbox para mostrar posiciones guardadas
        self.positions_listbox = tk.Listbox(positions_frame, font=("Arial", 10))
        self.positions_listbox.pack(pady=5, padx=10, fill="both", expand=True)
        
        # Botón de inicio
        tk.Button(main_frame, text="Inicio", command=self.home_position, 
                  bg="yellow", font=("Arial", 12, "bold")).pack(pady=10, fill="x")
    
    def create_motor_control(self, parent, motor_name):
        frame = tk.LabelFrame(parent, text=motor_name, font=("Arial", 10, "bold"))
        
        # Entrada de posición
        position_frame = tk.Frame(frame)
        position_frame.pack(fill="x", pady=5)
        
        tk.Label(position_frame, text="Posición (grados):", font=("Arial", 9)).pack(side="left", padx=5)
        
        position_var = tk.StringVar(value="0")
        position_entry = tk.Entry(position_frame, textvariable=position_var, width=10, font=("Arial", 10))
        position_entry.pack(side="left", padx=5)
        
        # Selector de dirección
        direction_frame = tk.Frame(frame)
        direction_frame.pack(fill="x", pady=5)
        
        direction_var = tk.StringVar(value="H")
        tk.Radiobutton(direction_frame, text="H", variable=direction_var, value="H").pack(side="left", padx=10)
        tk.Radiobutton(direction_frame, text="A", variable=direction_var, value="A").pack(side="left", padx=10)
        
        # Botón para mover motor individual
        move_button = tk.Button(frame, text=f"Mover {motor_name}", 
                                command=lambda: self.move_single_motor(motor_name, position_var.get(), direction_var.get()))
        move_button.pack(pady=5, fill="x", padx=10)
        
        # Guardar referencias para acceso posterior
        frame.position_var = position_var
        frame.direction_var = direction_var
        frame.motor_name = motor_name
        
        return frame
    
    def move_single_motor(self, motor_name, position, direction):
        try:
            pos = int(position)
            if pos < 0 or pos > 360:
                messagebox.showerror("Error", "La posición debe estar entre 0 y 360 grados")
                return
                
            speed = self.speed_var.get()
            # Aquí iría el código para enviar el comando al motor específico
            print(f"Moviendo {motor_name} a {pos} grados, dirección {direction}, velocidad {speed} RPM")
            
            # Simulación de movimiento exitoso
            messagebox.showinfo("Movimiento", f"{motor_name} moviéndose a {pos}°")
            
        except ValueError:
            messagebox.showerror("Error", "Por favor ingresa un valor numérico válido para la posición")
    
    def save_position(self):
        # Obtener nombre para la posición
        position_name = simpledialog.askstring("Guardar Posición", "Nombre de la posición:")
        if not position_name:
            return
            
        # Recopilar datos de todos los motores
        position_data = {
            "name": position_name,
            "motors": [],
            "garra": self.garra_var.get(),
            "speed": self.speed_var.get()
        }
        
        for frame in self.motor_frames:
            motor_data = {
                "name": frame.motor_name,
                "position": frame.position_var.get(),
                "direction": frame.direction_var.get()
            }
            position_data["motors"].append(motor_data)
        
        # Agregar a la lista de posiciones guardadas
        self.saved_positions.append(position_data)
        
        # Actualizar la lista visual
        self.update_positions_list()
        
        messagebox.showinfo("Éxito", f"Posición '{position_name}' guardada correctamente")
        print(f"Posición '{position_name}' guardada")
    
    def update_positions_list(self):
        self.positions_listbox.delete(0, tk.END)
        for pos in self.saved_positions:
            self.positions_listbox.insert(tk.END, f"{pos['name']} - Vel: {pos['speed']} RPM")
    
    def move_sequential(self):
        if not self.saved_positions:
            messagebox.showwarning("Advertencia", "No hay posiciones guardadas para mover")
            return
            
        # Obtener la posición seleccionada
        selection = self.positions_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Por favor selecciona una posición de la lista")
            return
            
        selected_position = self.saved_positions[selection[0]]
        
        # Mover cada motor secuencialmente
        print(f"Iniciando movimiento secuencial a posición: {selected_position['name']}")
        
        # Mostrar progreso
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Movimiento en Progreso")
        progress_window.geometry("300x150")
        
        progress_label = tk.Label(progress_window, text=f"Moviendo a posición: {selected_position['name']}")
        progress_label.pack(pady=10)
        
        progress = ttk.Progressbar(progress_window, orient="horizontal", length=250, mode="determinate")
        progress.pack(pady=10)
        
        # Simular movimiento secuencial
        total_motors = len(selected_position["motors"]) + 1  # +1 para la garra
        current_progress = 0
        
        for i, motor in enumerate(selected_position["motors"]):
            current_progress = (i / total_motors) * 100
            progress['value'] = current_progress
            progress_window.update()
            
            print(f"Moviendo {motor['name']} a {motor['position']} grados, dirección {motor['direction']}")
            # Aquí iría el código real para mover cada motor
        
        # Mover garra
        current_progress = ((total_motors - 1) / total_motors) * 100
        progress['value'] = current_progress
        progress_window.update()
        
        print(f"Configurando garra: {selected_position['garra']}")
        print(f"Velocidad: {selected_position['speed']} RPM")
        
        # Completar progreso
        progress['value'] = 100
        progress_window.update()
        
        progress_label.config(text="Movimiento completado!")
        self.root.after(1000, progress_window.destroy)  # Cerrar después de 1 segundo
        
        print("Movimiento secuencial completado")
        messagebox.showinfo("Éxito", f"Movimiento a '{selected_position['name']}' completado")
    
    def delete_position(self):
        selection = self.positions_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Por favor selecciona una posición para eliminar")
            return
            
        position_name = self.saved_positions[selection[0]]["name"]
        confirm = messagebox.askyesno("Confirmar", f"¿Estás seguro de que quieres eliminar la posición '{position_name}'?")
        
        if confirm:
            del self.saved_positions[selection[0]]
            self.update_positions_list()
            messagebox.showinfo("Éxito", f"Posición '{position_name}' eliminada")
            print(f"Posición '{position_name}' eliminada")
    
    def home_position(self):
        # Regresar todos los motores a posición 0
        for frame in self.motor_frames:
            frame.position_var.set("0")
            frame.direction_var.set("H")
        
        self.garra_var.set("ABRIR")
        self.speed_var.set("500")
        
        print("Todos los motores en posición de inicio")
        messagebox.showinfo("Inicio", "Todos los motores regresaron a posición de inicio")

if __name__ == "__main__":
    root = tk.Tk()
    app = MotorControlApp(root)
    root.mainloop()
