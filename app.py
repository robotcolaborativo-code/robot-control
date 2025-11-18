import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

class MotorControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Control de Posiciones de Motores")
        self.root.geometry("500x650")
        
        # Almacenar posiciones guardadas
        self.saved_positions = []
        
        self.create_widgets()
        
    def create_widgets(self):
        # Título
        title_label = tk.Label(self.root, text="Posiciones (grados°)", font=("Arial", 14, "bold"))
        title_label.pack(pady=10)
        
        # Frame principal
        main_frame = tk.Frame(self.root)
        main_frame.pack(pady=10, fill="both", expand=True)
        
        # Motores M1 a M4
        motors_frame = tk.Frame(main_frame)
        motors_frame.pack(pady=5)
        
        self.motors = []
        for i in range(1, 5):
            motor_frame = tk.Frame(motors_frame)
            motor_frame.pack(pady=2)
            
            tk.Label(motor_frame, text=f"M{i}", width=3).pack(side="left")
            
            pos_var = tk.StringVar(value="0")
            pos_entry = tk.Entry(motor_frame, textvariable=pos_var, width=5)
            pos_entry.pack(side="left", padx=2)
            
            dir_var = tk.StringVar(value="H")
            tk.Radiobutton(motor_frame, text="H", variable=dir_var, value="H").pack(side="left")
            tk.Radiobutton(motor_frame, text="A", variable=dir_var, value="A").pack(side="left")
            
            self.motors.append({
                "name": f"M{i}",
                "pos_var": pos_var,
                "dir_var": dir_var
            })
        
        # Garra
        garra_frame = tk.Frame(main_frame)
        garra_frame.pack(pady=5)
        
        tk.Label(garra_frame, text="MS (Garra)", width=10).pack(side="left")
        self.garra_var = tk.StringVar(value="ABRIR")
        tk.Radiobutton(garra_frame, text="ABRIR", variable=self.garra_var, value="ABRIR").pack(side="left")
        tk.Radiobutton(garra_frame, text="CERRAR", variable=self.garra_var, value="CERRAR").pack(side="left")
        
        # Velocidad
        speed_frame = tk.Frame(main_frame)
        speed_frame.pack(pady=5)
        
        tk.Label(speed_frame, text="Velocidad (1-1000 RPM)").pack(side="left")
        self.speed_var = tk.StringVar(value="500")
        speed_entry = tk.Entry(speed_frame, textvariable=self.speed_var, width=10)
        speed_entry.pack(side="left", padx=5)
        
        # Botones
        buttons_frame = tk.Frame(main_frame)
        buttons_frame.pack(pady=10)
        
        tk.Button(buttons_frame, text="Guardar posición", command=self.save_position, 
                 bg="lightblue", width=15).pack(side="left", padx=2)
        tk.Button(buttons_frame, text="MOVER SECUENCIAL", command=self.move_sequential,
                 bg="lightgreen", width=15).pack(side="left", padx=2)
        tk.Button(buttons_frame, text="Eliminar posición", command=self.delete_position,
                 bg="lightcoral", width=15).pack(side="left", padx=2)
        
        # Lista de posiciones guardadas
        list_frame = tk.Frame(main_frame)
        list_frame.pack(pady=5, fill="both", expand=True)
        
        tk.Label(list_frame, text="Posiciones Guardadas:", font=("Arial", 10, "bold")).pack()
        
        # Scrollbar para la lista
        list_scroll = tk.Scrollbar(list_frame)
        list_scroll.pack(side="right", fill="y")
        
        self.positions_listbox = tk.Listbox(list_frame, yscrollcommand=list_scroll.set, height=8)
        self.positions_listbox.pack(fill="both", expand=True)
        list_scroll.config(command=self.positions_listbox.yview)
        
        # Botón Inicio
        tk.Button(main_frame, text="Inicio", command=self.home_position,
                 bg="yellow", font=("Arial", 12, "bold"), width=20).pack(pady=10)
    
    def save_position(self):
        name = simpledialog.askstring("Guardar Posición", "Nombre de la posición:")
        if not name:
            return
        
        # Recoger datos de todos los motores
        position_data = {
            "name": name,
            "motors": [],
            "garra": self.garra_var.get(),
            "speed": self.speed_var.get()
        }
        
        for motor in self.motors:
            motor_data = {
                "name": motor["name"],
                "position": motor["pos_var"].get(),
                "direction": motor["dir_var"].get()
            }
            position_data["motors"].append(motor_data)
        
        self.saved_positions.append(position_data)
        self.update_positions_list()
        
        messagebox.showinfo("Éxito", f"Posición '{name}' guardada")
    
    def update_positions_list(self):
        self.positions_listbox.delete(0, tk.END)
        for pos in self.saved_positions:
            self.positions_listbox.insert(tk.END, f"{pos['name']} - Vel: {pos['speed']} RPM")
    
    def move_sequential(self):
        selection = self.positions_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona una posición de la lista")
            return
        
        position = self.saved_positions[selection[0]]
        
        # Mostrar ventana de progreso
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Movimiento en Progreso")
        progress_window.geometry("300x150")
        
        progress_label = tk.Label(progress_window, text=f"Moviendo a: {position['name']}")
        progress_label.pack(pady=10)
        
        progress = ttk.Progressbar(progress_window, orient="horizontal", length=250, mode="determinate")
        progress.pack(pady=10)
        
        # Simular movimiento secuencial
        total_steps = len(position["motors"]) + 1  # +1 para la garra
        
        for i, motor in enumerate(position["motors"]):
            progress['value'] = (i / total_steps) * 100
            progress_window.update()
            
            print(f"Moviendo {motor['name']} a {motor['position']}°, dirección {motor['direction']}")
            # Aquí iría el comando real al motor
        
        # Mover garra
        progress['value'] = ((total_steps - 1) / total_steps) * 100
        progress_window.update()
        print(f"Garra: {position['garra']}")
        
        progress['value'] = 100
        progress_label.config(text="Movimiento completado!")
        
        self.root.after(1000, progress_window.destroy)
        messagebox.showinfo("Éxito", f"Movimiento a '{position['name']}' completado")
    
    def delete_position(self):
        selection = self.positions_listbox.curselection()
        if not selection:
            messagebox.showwarning("Advertencia", "Selecciona una posición para eliminar")
            return
        
        position_name = self.saved_positions[selection[0]]["name"]
        if messagebox.askyesno("Confirmar", f"¿Eliminar posición '{position_name}'?"):
            del self.saved_positions[selection[0]]
            self.update_positions_list()
            messagebox.showinfo("Éxito", f"Posición '{position_name}' eliminada")
    
    def home_position(self):
        # Resetear todos los valores a cero
        for motor in self.motors:
            motor["pos_var"].set("0")
            motor["dir_var"].set("H")
        
        self.garra_var.set("ABRIR")
        self.speed_var.set("500")
        
        messagebox.showinfo("Inicio", "Todos los motores en posición inicial")

if __name__ == "__main__":
    root = tk.Tk()
    app = MotorControlApp(root)
    root.mainloop()
