import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading
import time
import socket
import json
import os
import tkinter.simpledialog as simpledialog
from tkinter import messagebox
from PIL import Image, ImageTk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

POSITIONS_FILE = "positions.json"

class CobotApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🤖 Control Cobot 4DOF + Garra (Serial/Wi-Fi + POS)")
        self.geometry("1100x680")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Conexiones / estado
        self.serial_port = None
        self.tcp_client = None
        self.stop_thread = False
        self.lock = threading.Lock()
        self.modo_conexion = ctk.StringVar(value="Serial")
        self.connected = False

        # OPTIMIZACIÓN: Timing mejorado
        self.command_delay = 0.01
        self.move_delay = 0.4
        self.serial_timeout = 0.3

        # ✅ INFORMACIÓN DE MODOS DE VELOCIDAD
        self.modo_velocidad_info = {
            "M1": "Control completo (1-1500 RPM)",
            "M2": "Control completo (1-1500 RPM)", 
            "M3": "Velocidad fija 35 RPM",
            "M4": "Velocidad fija 1000 RPM",
            "M5": "Garra (100°=Abierto, 0°=Cerrado)"
        }

        # Posiciones (nombre -> {pos: [m1..m5], vel: v})
        self.positions = {}
        self.load_positions_file()

        # Header: logo left, title center (keeps existing title), robot image right
        header = ctk.CTkFrame(self, corner_radius=0)
        header.pack(side="top", fill="x", padx=6, pady=(6,0))

        # logo (left) - try several filename variants
        logo_candidates = ["LogoUniversidad.png", "logo.png", "Logo.png", "logo_universidad.png", "logo_universidad.PNG"]
        self.logo_img = None
        logo_found = None
        for logo_path in logo_candidates:
            if os.path.exists(logo_path):
                logo_found = logo_path
                break
        if logo_found:
            try:
                img = Image.open(logo_found)
                img.thumbnail((120, 60), Image.ANTIALIAS)
                self.logo_img = ImageTk.PhotoImage(img)
                self.logo_label = ctk.CTkLabel(header, image=self.logo_img, text="")
                self.logo_label.pack(side="left", padx=6)
            except Exception:
                ctk.CTkLabel(header, text="LOGO UNIVERSIDAD").pack(side="left", padx=6)
        else:
            ctk.CTkLabel(header, text="LOGO UNIVERSIDAD").pack(side="left", padx=6)

        # spacer center (keeps title in window title bar unchanged)
        ctk.CTkLabel(header, text="", width=20).pack(side="left", expand=True)

        # robot image (right) - try several filename variants
        robot_candidates = ["ImagenRobot.png", "robot.png", "Robot.png", "imagen_robot.png", "robot.PNG"]
        self.robot_img = None
        robot_found = None
        for robot_path in robot_candidates:
            if os.path.exists(robot_path):
                robot_found = robot_path
                break
        if robot_found:
            try:
                img2 = Image.open(robot_found)
                img2.thumbnail((160, 80), Image.ANTIALIAS)
                self.robot_img = ImageTk.PhotoImage(img2)
                self.robot_label = ctk.CTkLabel(header, image=self.robot_img, text="")
                self.robot_label.pack(side="right", padx=6)
            except Exception:
                ctk.CTkLabel(header, text="IMAGEN ROBOT").pack(side="right", padx=6)
        else:
            ctk.CTkLabel(header, text="IMAGEN ROBOT").pack(side="right", padx=6)

     
        # ------------------- LEFT PANEL (CONEXIÓN + POS) -------------------
        # CONTENEDOR con scroll
        left_container = ctk.CTkFrame(self, corner_radius=10)
        left_container.pack(side="left", fill="y", padx=12, pady=12)
        # Canvas que permite desplazar el contenido
        self.left_canvas = ctk.CTkCanvas(
        left_container,
        width=450,
        height=630,
        bg="#1a1a1a",
        highlightthickness=0
        )
        self.left_canvas.pack(side="left", fill="y")

        # Barra de scroll
        self.left_scrollbar = ctk.CTkScrollbar(
        left_container,
        orientation="vertical",
        command=self.left_canvas.yview
        )
        self.left_scrollbar.pack(side="left", fill="x")

        self.left_canvas.configure(yscrollcommand=self.left_scrollbar.set)

       # Frame interno donde irán todos los widgets ORIGINALES
        self.left_frame = ctk.CTkFrame(self.left_canvas, corner_radius=10)
        self.left_canvas.create_window((0, 0), window=self.left_frame, anchor="nw")
       # Para actualizar el tamaño del scroll
        def _update_scroll(event):
         self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))

        self.left_frame.bind("<Configure>", _update_scroll)
       # Permitir mover el scroll con rueda del mouse
        def _on_mousewheel(event):
         self.left_canvas.yview_scroll(-1 * int(event.delta / 120), "units")

        self.left_frame.bind("<Enter>", lambda _: self.left_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.left_frame.bind("<Leave>", lambda _: self.left_canvas.unbind_all("<MouseWheel>"))

# IMPORTANTÍSIMO: aquí dejamos "left" apuntando a tu frame original
        left = self.left_frame

        ctk.CTkLabel(left, text="🔌 Conexión", font=("Arial", 25, "bold")).pack(pady=6)

        modo_menu = ctk.CTkOptionMenu(left, variable=self.modo_conexion, values=["Serial", "Wi-Fi"], command=self.change_mode)
        modo_menu.pack(pady=6)

        self.frame_opts = ctk.CTkFrame(left)
        self.frame_opts.pack(pady=6, fill="x")
        self.create_serial_opts()

        btn_connect = ctk.CTkButton(left, text="Conectar", command=self.connect, width=140)
        btn_connect.pack(pady=6)
        btn_disconnect = ctk.CTkButton(left, text="Desconectar", command=self.disconnect, width=140)
        btn_disconnect.pack(pady=6)

        # Indicador visual superior (Estado)
        self.label_status = ctk.CTkLabel(left, text="Estado: Desconectado", text_color="red")
        self.label_status.pack(pady=8)
        
        # NUEVO: Indicador de estado WiFi
        self.wifi_info_label = ctk.CTkLabel(left, text="📶 WiFi: Desconectado", text_color="red")
        self.wifi_info_label.pack(pady=4)

        # ✅ NUEVO: Información de modos de velocidad
        info_frame = ctk.CTkFrame(left)
        info_frame.pack(pady=8, fill="x", padx=6)
        ctk.CTkLabel(info_frame, text="ℹ️ Modos de Velocidad", font=("Arial", 16, "bold")).pack(pady=4)
        for motor, info in self.modo_velocidad_info.items():
            label_text = f"{motor}: {info}"
            label_color = "#4CAF50" if motor in ["M1", "M2"] else "#FF9800" if motor in ["M3", "M4"] else "#2196F3"
            ctk.CTkLabel(info_frame, text=label_text, text_color=label_color, font=("Arial", 12)).pack(anchor="w", pady=1)

        # Posiciones UI: M1..M4 con selector sentido, M5 garra como segmented button
        ctk.CTkLabel(left, text="📍 Posiciones (grados°)", font=("Arial", 25, "bold")).pack(pady=8)

        self.pos_entries = []
        self.dir_vars = []
        for i in range(4):
            f = ctk.CTkFrame(left)
            f.pack(fill="x", pady=2, padx=6)
            motor_label = f"M{i+1}"
            if i == 2: motor_label += " (35 RPM)"
            elif i == 3: motor_label += " (1000 RPM)"
            ctk.CTkLabel(f, text=motor_label, width=60).pack(side="left")
            e = ctk.CTkEntry(f, width=100)
            e.insert(0, "0")
            e.pack(side="left", padx=8)
            # direccion selector (H/A)
            dir_var = ctk.StringVar(value="H")
            seg = ctk.CTkSegmentedButton(f, values=["H","A"], variable=dir_var, width=100)
            seg.pack(side="left", padx=6)
            self.pos_entries.append(e)
            self.dir_vars.append(dir_var)

        # ✅ GARRA CORREGIDA: 100° = Abierto, 0° = Cerrado
        f_garra = ctk.CTkFrame(left)
        f_garra.pack(fill="x", pady=2, padx=6)
        ctk.CTkLabel(f_garra, text="M5 (Garra):", width=70).pack(side="left")
        ctk.CTkLabel(f_garra, text="100°=Abierto, 0°=Cerrado", text_color="#2196F3", font=("Arial", 10)).pack(side="left", padx=5)
        self.garra_state_var = ctk.StringVar(value="ABRIR")
        self.garra_segment = ctk.CTkSegmentedButton(f_garra, values=["ABRIR", "CERRAR"], variable=self.garra_state_var)
        self.garra_segment.pack(side="left", padx=8)

        # ✅ VELOCIDAD ACTUALIZADA: 1-1500 RPM para M1 y M2
        ctk.CTkLabel(left, text="Velocidad M1/M2 (1-1500 RPM)").pack(pady=6)
        self.entry_vel = ctk.CTkEntry(left, width=120)
        self.entry_vel.insert(0, "500")
        self.entry_vel.pack(pady=6)

        # Guardar / Mover / Eliminar posición
        fbtn = ctk.CTkFrame(left)
        fbtn.pack(pady=6)
        ctk.CTkButton(fbtn, text="💾 Guardar posición", command=self.save_position).pack(side="left", padx=4)
        # mover secuencial (izquierda) - grande
        ctk.CTkButton(fbtn, text="🧭 MOVER SECUENCIAL", command=self.move_position_thread, fg_color="#1E88E5", width=140).pack(side="left", padx=4)
        ctk.CTkButton(fbtn, text="🗑️ Eliminar posición", command=self.delete_position).pack(side="left", padx=4)

        # Dropdown posiciones
        pos_keys = list(self.positions.keys()) or ["Inicio"]
        self.pos_var = ctk.StringVar()
        self.pos_menu = ctk.CTkOptionMenu(left, variable=self.pos_var, values=pos_keys)
        self.pos_menu.pack(pady=6, fill="x", padx=6)
        if pos_keys:
            self.pos_var.set(pos_keys[0])

        self.progress = ctk.CTkProgressBar(left, width=220)
        self.progress.set(0.0)
        self.progress.pack(pady=8)

        # ------------------- RIGHT PANEL (CONTROL + TERMINAL) -------------------
        right = ctk.CTkFrame(self, corner_radius=10)
        right.pack(side="right", fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(right, text="⚙️ Control de Motores", font=("Arial",25, "bold")).pack(pady=6)

        # Panel pequeño para mover por pasos
        param_frame = ctk.CTkFrame(right)
        param_frame.pack(pady=6, padx=6, fill="x")
        ctk.CTkLabel(param_frame, text="Pasos (comando directo)").grid(row=0, column=0, padx=6, pady=6)
        self.entry_steps = ctk.CTkEntry(param_frame, width=100)
        self.entry_steps.insert(0, "200")
        self.entry_steps.grid(row=0, column=1, padx=6, pady=6)
        # ✅ VELOCIDAD ACTUALIZADA: 1-1500 RPM
        ctk.CTkLabel(param_frame, text="Velocidad M1/M2 (1-1500 RPM)").grid(row=0, column=2, padx=6, pady=6)
        self.entry_vel_direct = ctk.CTkEntry(param_frame, width=100)
        self.entry_vel_direct.insert(0, "500")
        self.entry_vel_direct.grid(row=0, column=3, padx=6, pady=6)

        # Control directo por motor (dropdown para seleccionar motor)
        f_direct = ctk.CTkFrame(right)
        f_direct.pack(pady=30, padx=30, fill="x")
        ctk.CTkLabel(f_direct, text="CONTROL DIRECTO", width=250).pack(side="left", padx=15)
        self.direct_motor_var = ctk.StringVar(value="M1")
        self.direct_motor_menu = ctk.CTkOptionMenu(f_direct, variable=self.direct_motor_var,height=40, values=["M1", "M2", "M3", "M4"])
        self.direct_motor_menu.pack(side="left", padx=6)
        ctk.CTkButton(f_direct, text="⟲ Antihorario", command=lambda: self.direct_move("A"),height=40).pack(side="left", padx=15)
        ctk.CTkButton(f_direct, text="⟳ Horario", command=lambda: self.direct_move("H"),height=40).pack(side="left", padx=15)

        # ✅ NUEVO: Indicador de modo de velocidad para motor seleccionado
        self.modo_velocidad_label = ctk.CTkLabel(f_direct, text="M1: Control completo (1-1500 RPM)", text_color="#4CAF50")
        self.modo_velocidad_label.pack(side="left", padx=15)
        
        # Actualizar indicador cuando cambie el motor
        self.direct_motor_var.trace('w', self.actualizar_indicador_velocidad)

        # Botones generales: ON/OFF/ABRIR/CERRAR
        f_g = ctk.CTkFrame(right)
        f_g.pack(pady=15)
        ctk.CTkButton(f_g, text="🔌 ON (energizar)", fg_color="#2e7d32", command=lambda: self.send_command("ON"),height=40).pack(side="left", padx=30)
        ctk.CTkButton(f_g, text="⚙️ OFF (apagar)", fg_color="#d32f2f", command=lambda: self.send_command("OFF"),height=40).pack(side="left", padx=30)
        ctk.CTkButton(f_g, text="🔓 ABRIR", command=lambda: self.send_command("ABRIR"),height=40).pack(side="left", padx=15)
        ctk.CTkButton(f_g, text="🔒 CERRAR", command=lambda: self.send_command("CERRAR"),height=40).pack(side="left", padx=15)
        # STOP y RESET (emergencia/reset)
        f_em = ctk.CTkFrame(right)
        f_em.pack(pady=30)
        ctk.CTkButton(f_em, text="🛑 PARO EMERGENCIA (STOP)", fg_color="#d32f2f", command=self.emergency_stop, height=50).pack(side="left", padx=15)
        ctk.CTkButton(f_em, text="🔄 REINICIAR (RESET)", fg_color="#2e7d32", command=self.reset_system, height=50).pack(side="left", padx=15)

        # Limpiar terminal (derecha)
        ctk.CTkButton(right, text="🧹 Limpiar terminal", fg_color="#9E9E9E", height=40, command=self.clear_terminal).pack(pady=10, padx=8)

        # Toggle terminal button (blue with icon)
        self.terminal_visible = True
        toggle_frame = ctk.CTkFrame(right)
        toggle_frame.pack(pady=(0,6), padx=8, fill="x")
        self.btn_toggle_terminal = ctk.CTkButton(toggle_frame, text="🖥 Mostrar/Ocultar terminal", fg_color="#1E88E5", command=self.toggle_terminal, height=36)
        self.btn_toggle_terminal.pack(side="right")

        # Terminal frame (plegable)
        self.terminal_frame = ctk.CTkFrame(right)
        self.terminal_frame.pack(fill="both", expand=True, padx=8, pady=6)

        ctk.CTkLabel(self.terminal_frame, text="📟 Terminal").pack(pady=6)
        self.text_terminal = ctk.CTkTextbox(self.terminal_frame, height=300)
        self.text_terminal.pack(fill="both", expand=True, padx=8, pady=6)
        self.text_terminal.insert("end", "Terminal lista...\n")

    # ✅ NUEVA FUNCIÓN: Actualizar indicador de modo de velocidad
    def actualizar_indicador_velocidad(self, *args):
        motor = self.direct_motor_var.get()
        info = self.modo_velocidad_info.get(motor, "")
        colors = {
            "M1": "#4CAF50", "M2": "#4CAF50",  # Verde para control completo
            "M3": "#FF9800", "M4": "#FF9800",  # Naranja para velocidad fija
            "M5": "#2196F3"                    # Azul para garra
        }
        color = colors.get(motor, "white")
        self.modo_velocidad_label.configure(text=f"{motor}: {info}", text_color=color)

    # ------------------- NUEVAS FUNCIONES WIFI OPTIMIZADAS -------------------
    def update_wifi_info(self):
        """Actualizar información WiFi en la interfaz"""
        if self.connected and self.modo_conexion.get() == "Wi-Fi":
            self.wifi_info_label.configure(
                text="📶 WiFi: Conectado | Modo: Cliente",
                text_color="green"
            )
        else:
            self.wifi_info_label.configure(
                text="📶 WiFi: Desconectado",
                text_color="red"
            )

    def get_wifi_status(self):
        """Obtener estado WiFi del ESP32"""
        if self.connected:
            try:
                self.send_command("STATUS:WIFI")
            except:
                pass

    # ------------------- Conexión UI helpers -------------------
    def create_serial_opts(self):
        for w in self.frame_opts.winfo_children(): w.destroy()
        ctk.CTkLabel(self.frame_opts, text="Puerto Serial:").pack(pady=2)
        ports = self.list_serial_ports()
        self.port_menu = ctk.CTkOptionMenu(self.frame_opts, values=ports or ["Ninguno"])
        self.port_menu.pack(pady=2)

    def create_wifi_opts(self):
        for w in self.frame_opts.winfo_children(): w.destroy()
        ctk.CTkLabel(self.frame_opts, text="IP ESP32:").pack(pady=2)
        self.entry_ip = ctk.CTkEntry(self.frame_opts, width=160)
        self.entry_ip.insert(0, "10.31.183.131")
        self.entry_ip.pack(pady=2)
        ctk.CTkLabel(self.frame_opts, text="Puerto (TCP):").pack(pady=1)
        self.entry_port = ctk.CTkEntry(self.frame_opts, width=100)
        self.entry_port.insert(0, "8080")
        self.entry_port.pack(pady=2)

    def change_mode(self, modo):
        if modo == "Serial":
            self.create_serial_opts()
        else:
            self.create_wifi_opts()
        self.update_wifi_info()

    def list_serial_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self):
        modo = self.modo_conexion.get()
        if modo == "Serial":
            self.connect_serial()
        else:
            self.connect_wifi()
        self.update_wifi_info()

    # OPTIMIZACIÓN: Conexión serial más rápida
    def connect_serial(self):
        try:
            puerto = self.port_menu.get()
            if puerto == "Ninguno":
                self.log("⚠️ No hay puerto serial disponible.")
                return
            
            self.serial_port = serial.Serial(
                puerto, 
                115200, 
                timeout=self.serial_timeout,
                write_timeout=1.0
            )
            self.connected = True
            self.label_status.configure(text=f"Conectado (Serial {puerto})", text_color="green")
            self.log(f"🔌 Conectado a {puerto} (Serial).")
            self.stop_thread = False
            
            threading.Thread(target=self.read_serial_fast, daemon=True).start()

            try:
                if self.serial_port and self.serial_port.is_open:
                    self.serial_port.write(b"MODE:SERIAL\n")
                    self.log("➡ Enviado MODE:SERIAL al ESP")
                    time.sleep(0.1)
            except Exception as e:
                self.log(f"⚠️ No se pudo enviar MODE:SERIAL: {e}")

        except Exception as e:
            self.log(f"❌ Error al conectar Serial: {e}")

    # OPTIMIZACIÓN: Conexión WiFi más rápida
    def connect_wifi(self):
        try:
            ip = self.entry_ip.get()
            port = int(self.entry_port.get())

            try:
                if self.serial_port and self.serial_port.is_open:
                    self.serial_port.write(b"MODE:WIFI\n")
                    self.log("➡ Enviado MODE:WIFI al ESP")
                    time.sleep(0.5)
            except Exception as e:
                self.log(f"⚠️ No se pudo enviar MODE:WIFI: {e}")

            self.tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_client.settimeout(4)
            self.tcp_client.connect((ip, port))
            self.connected = True
            self.label_status.configure(text=f"Conectado (Wi-Fi {ip}:{port})", text_color="green")
            self.log(f"🌐 Conectado a {ip}:{port} (Wi-Fi).")
            self.stop_thread = False
            
            threading.Thread(target=self.read_wifi_fast, daemon=True).start()
            self.update_wifi_info()
            
        except Exception as e:
            self.log(f"❌ Error al conectar Wi-Fi: {e}")

    def disconnect(self):
        self.stop_thread = True
        try:
            if self.serial_port and self.serial_port.is_open:
                try:
                    self.serial_port.write(b"MODE:SERIAL\n")
                    self.log("➡ Enviado MODE:SERIAL al ESP antes de cerrar puerto.")
                    time.sleep(0.05)
                except Exception:
                    pass
                self.serial_port.close()
        except:
            pass
        try:
            if self.tcp_client:
                try:
                    self.tcp_client.close()
                except:
                    pass
        except:
            pass
        self.connected = False
        self.label_status.configure(text="Estado: Desconectado", text_color="red")
        self.update_wifi_info()
        self.log("🔴 Desconectado.")

    # ------------------- LECTURA OPTIMIZADA -------------------
    def read_serial_fast(self):
        buffer = ""
        while not self.stop_thread and self.serial_port and self.serial_port.is_open:
            try:
                data = self.serial_port.read(self.serial_port.in_waiting or 1).decode(errors='ignore')
                if data:
                    buffer += data
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self.log(line)
                            if "Conectado al Wi-Fi" in line or "WiFi desconectado" in line:
                                self.update_wifi_info()
            except Exception:
                break

    def read_wifi_fast(self):
        buffer = ""
        while not self.stop_thread and self.tcp_client:
            try:
                data = self.tcp_client.recv(512).decode(errors='ignore')
                if data:
                    buffer += data
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self.log(line)
                            if "Conectado al Wi-Fi" in line or "WiFi desconectado" in line:
                                self.update_wifi_info()
            except socket.timeout:
                continue
            except Exception:
                break

    # ------------------- ENVÍO OPTIMIZADO -------------------
    def send_command(self, cmd, pause=None):
        if pause is None:
            pause = self.command_delay
            
        try:
            with self.lock:
                modo = self.modo_conexion.get()
                success = False
                
                if modo == "Serial":
                    if self.serial_port and self.serial_port.is_open:
                        self.serial_port.write((cmd + "\n").encode())
                        success = True
                    elif self.tcp_client:
                        try:
                            self.tcp_client.sendall((cmd + "\n").encode())
                            success = True
                        except Exception:
                            self.log("⚠️ No conectado por Serial ni Wi-Fi.")
                            return False
                    else:
                        self.log("⚠️ No conectado por Serial ni Wi-Fi.")
                        return False
                else:
                    if self.tcp_client:
                        try:
                            self.tcp_client.sendall((cmd + "\n").encode())
                            success = True
                        except Exception as e:
                            if self.serial_port and self.serial_port.is_open:
                                self.serial_port.write((cmd + "\n").encode())
                                success = True
                            else:
                                self.log(f"❌ Error al enviar por Wi-Fi: {e}")
                                return False
                    elif self.serial_port and self.serial_port.is_open:
                        self.serial_port.write((cmd + "\n").encode())
                        success = True
                    else:
                        self.log("⚠️ No conectado por Wi-Fi ni Serial.")
                        return False

                if success:
                    self.log(f"> {cmd}")
                    time.sleep(pause)
                    return True
                else:
                    return False
                    
        except Exception as e:
            self.log(f"❌ Error al enviar comando: {e}")
            return False

    # ------------------- Comandos directos -------------------
    def direct_move(self, direction):
        motor = self.direct_motor_var.get()
        pasos = self.entry_steps.get()
        vel = self.entry_vel_direct.get()
        try:
            pasos_i = int(pasos)
            # ✅ VALIDACIÓN MEJORADA DE VELOCIDAD
            if motor in ["M1", "M2"]:
                vel_i = max(1, min(1500, int(vel)))  # 1-1500 RPM para M1 y M2
            else:
                vel_i = int(vel)  # Para M3 y M4 se ignora (pero se envía)
        except:
            self.log("⚠️ Pasos/vel inválidos.")
            return
            
        if motor == "M5":
            estado = self.garra_state_var.get()
            if estado not in ["ABRIR", "CERRAR"]:
                estado = "ABRIR"
            self.send_command(estado)
        else:
            dir_char = "H" if direction == "H" else "A"
            cmd = f"{motor},{dir_char},{pasos_i},{vel_i}"
            self.send_command(cmd)
            # ✅ INFORMAR MODO DE VELOCIDAD APLICADO
            if motor == "M3":
                self.log(f"ℹ️ M3: Velocidad fija 35 RPM (solicitado: {vel_i} RPM)")
            elif motor == "M4":
                self.log(f"ℹ️ M4: Velocidad fija 1000 RPM (solicitado: {vel_i} RPM)")

    # ------------------- Posiciones (guardar / cargar / eliminar) ----
    def load_positions_file(self):
        if os.path.exists(POSITIONS_FILE):
            try:
                with open(POSITIONS_FILE, "r") as f:
                    self.positions = json.load(f)
            except Exception:
                self.positions = {}
        else:
            self.positions = {"Inicio": {"pos": [0, 0, 0, 0, "ABRIR"], "vel": 500}}
            self.save_positions_file()

    def save_positions_file(self):
        try:
            with open(POSITIONS_FILE, "w") as f:
                json.dump(self.positions, f, indent=2)
        except Exception as e:
            self.log(f"❌ Error al guardar posiciones: {e}")

    def save_position(self):
        name = simpledialog.askstring("Nombre posición", "Introduce un nombre para la posición:", parent=self)
        if not name:
            self.log("⚠️ Guardado cancelado.")
            return
        try:
            vals = []
            for i, e in enumerate(self.pos_entries):
                txt = e.get().strip()
                v = float(txt)
                if v < 0 or v > 360:
                    self.log(f"⚠️ Valor fuera de rango para M{i+1}: {v}")
                    return
                vals.append(v)
            garra_state = self.garra_state_var.get()
            if garra_state not in ["ABRIR", "CERRAR"]:
                garra_state = "ABRIR"
            vals.append(garra_state)
            # ✅ VALIDACIÓN VELOCIDAD M1/M2
            vel = int(self.entry_vel.get())
            vel = max(1, min(1500, vel))
        except Exception:
            self.log("⚠️ Valores inválidos al guardar posición.")
            return
        self.positions[name] = {"pos": vals, "vel": vel}
        self.save_positions_file()
        vals_list = list(self.positions.keys())
        self.pos_menu.configure(values=vals_list)
        self.pos_menu.set(name)
        self.log(f"💾 Posición '{name}' guardada: {vals} vel={vel}")

    def delete_position(self):
        key = self.pos_menu.get()
        if not key or key not in self.positions:
            self.log("⚠️ Selecciona una posición válida para eliminar.")
            return
        confirm = messagebox.askyesno("Eliminar posición", f"¿Eliminar '{key}'?")
        if not confirm:
            return
        del self.positions[key]
        self.save_positions_file()
        vals_list = list(self.positions.keys())
        if not vals_list:
            self.positions["Inicio"] = {"pos":[0,0,0,0,"ABRIR"], "vel":500}
            self.save_positions_file()
            vals_list = list(self.positions.keys())
        self.pos_menu.configure(values=vals_list)
        self.pos_menu.set(vals_list[0])
        self.log(f"🗑️ Posición '{key}' eliminada.")

    # ------------------- MOVER SECUENCIAL OPTIMIZADO -------------------
    def move_position_thread(self):
        t = threading.Thread(target=self.move_to_position_fast, daemon=True)
        t.start()

    def move_to_position_fast(self):
        key = self.pos_menu.get()
        if key not in self.positions:
            self.log("⚠️ Selecciona una posición válida.")
            return
        pos = self.positions[key]["pos"]
        vel = int(self.positions[key]["vel"])
        self.log(f"➡ Enviando posición '{key}': {pos} vel={vel}")
        total_steps = 5
        step_idx = 0
        
        for i in range(4):
            motor_id = i + 1
            val = pos[i]
            try:
                vnum = float(val)
            except:
                self.log(f"⚠️ Valor inválido para M{motor_id}: {val}")
                continue
            if vnum < 0 or vnum > 360:
                self.log(f"⚠️ Fuera de rango M{motor_id}: {vnum}")
                continue
            
            pasos = int(round(vnum))
            dir_choice = self.dir_vars[i].get() if i < len(self.dir_vars) else "H"
            cmd = f"M{motor_id},{dir_choice},{pasos},{vel}"
            
            ok = self.send_command(cmd, pause=0.03)
            if not ok:
                self.log("⚠️ No se pudo enviar comando. Abortando secuencia.")
                return
                
            # ✅ INFORMAR MODO DE VELOCIDAD
            if motor_id == 3:
                self.log(f"Motor {motor_id} movido (grados={vnum}) - MODO: 35 RPM FIJO")
            elif motor_id == 4:
                self.log(f"Motor {motor_id} movido (grados={vnum}) - MODO: 1000 RPM FIJO")
            else:
                self.log(f"Motor {motor_id} movido (grados={vnum}, vel={vel})")
                
            step_idx += 1
            self.progress.set(step_idx / total_steps)
            time.sleep(self.move_delay)

        # ✅ GARRA CORREGIDA
        gval = pos[4]
        if isinstance(gval, str):
            gcmd = gval.upper()
            if gcmd not in ["ABRIR", "CERRAR"]:
                gcmd = "ABRIR"
        else:
            try:
                gnum = float(gval)
                gcmd = "CERRAR" if gnum < 50 else "ABRIR"  # Umbral a 50°
            except:
                gcmd = "ABRIR"
                
        ok = self.send_command(gcmd, pause=0.03)
        if not ok:
            self.log("⚠️ Error al enviar comando garra.")
            return
            
        step_idx += 1
        self.progress.set(step_idx / total_steps)
        time.sleep(self.move_delay)

        self.log("✅ Movimiento secuencial completado.")
        self.progress.set(0.0)

    # ------------------- STOP / RESET -------------------
    def emergency_stop(self):
        if self.send_command("STOP"):
            self.label_status.configure(text="ESTADO: EMERGENCIA", text_color="red")
            self.log("🛑 STOP enviado.")
        else:
            self.log("⚠️ STOP no enviado (sin conexión).")

    def reset_system(self):
        if self.send_command("RESET"):
            self.label_status.configure(text="ESTADO: RESET (usar ON)", text_color="orange")
            self.log("🔄 RESET enviado.")
        else:
            self.log("⚠️ RESET no enviado (sin conexión).")

    # ------------------- Utilidades UI -------------------
    def clear_terminal(self):
        self.text_terminal.delete("0.0", "end")

    def toggle_terminal(self):
        if self.terminal_visible:
            self.terminal_frame.pack_forget()
            self.terminal_visible = False
            self.btn_toggle_terminal.configure(text="🖥 Mostrar terminal")
        else:
            self.terminal_frame.pack(fill="both", expand=True, padx=8, pady=6)
            self.terminal_visible = True
            self.btn_toggle_terminal.configure(text="🖥 Ocultar terminal")

    def log(self, text):
        ts = time.strftime("%H:%M:%S")
        try:
            self.text_terminal.insert("end", f"[{ts}] {text}\n")
            self.text_terminal.see("end")
        except Exception:
            print(f"[{ts}] {text}")

    def on_close(self):
        self.disconnect()
        self.destroy()

if __name__ == "__main__":
    app = CobotApp()
    app.mainloop()
