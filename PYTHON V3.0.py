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
TRAYECTORIAS_FILE = "trayectorias.json"

class CobotApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🤖 Control Cobot 4DOF + Garra (Serial/Wi-Fi)")
        self.geometry("1100x680")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Conexiones / estado
        self.serial_port = None
        self.tcp_client = None
        self.stop_thread = False
        self.lock = threading.Lock()
        self.modo_conexion = ctk.StringVar(value="Serial")
        self.connected = False
        self.emergency_stop_active = False
        self.zero_set = False
        self.current_virtual_pos = [0.0, 0.0, 0.0, 0.0]
        
        # Control de ejecución en bucle
        self.ejecutando_bucle = False
        self.bucle_thread = None
        self.repeticiones_bucle = 1
        self.repeticion_actual = 0

        # Timing optimizado
        self.command_delay = 0.01
        self.move_delay = 0.4
        self.serial_timeout = 0.3

        # Control de terminal plegable
        self.terminal_visible = True

        # Posiciones
        self.positions = {}
        self.trayectorias = {}
        
        # Inicializar variables de UI primero
        self.tray_var = ctk.StringVar()
        self.tray_menu = None
        
        # Cargar datos DESPUÉS de inicializar variables
        self.load_positions_file()
        self.load_trayectorias_file()

        # Header
        header = ctk.CTkFrame(self, corner_radius=0)
        header.pack(side="top", fill="x", padx=6, pady=(6,0))

        # Logo izquierda
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
                ctk.CTkLabel(header, text="CORPORACIÓN UNIVERSITARIA COMFACAUCA").pack(side="left", padx=6)
        else:
            ctk.CTkLabel(header, text="LOGO UNIVERSIDAD").pack(side="left", padx=6)

        # Espaciador centro
        ctk.CTkLabel(header, text="", width=20).pack(side="left", expand=True)

        # Imagen robot derecha
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
                ctk.CTkLabel(header, text="ROBOT COLABORATIVO").pack(side="right", padx=6)
        else:
            ctk.CTkLabel(header, text="IMAGEN ROBOT").pack(side="right", padx=6)

        # ------------------- PANEL IZQUIERDO (CONEXIÓN + CONTROL PRINCIPAL) -------------------
        left_container = ctk.CTkFrame(self, corner_radius=10)
        left_container.pack(side="left", fill="y", padx=12, pady=12)
        
        self.left_canvas = ctk.CTkCanvas(
            left_container,
            width=450,
            height=630,
            bg="#1a1a1a",
            highlightthickness=0
        )
        self.left_canvas.pack(side="left", fill="y")

        self.left_scrollbar = ctk.CTkScrollbar(
            left_container,
            orientation="vertical",
            command=self.left_canvas.yview
        )
        self.left_scrollbar.pack(side="left", fill="x")

        self.left_canvas.configure(yscrollcommand=self.left_scrollbar.set)

        self.left_frame = ctk.CTkFrame(self.left_canvas, corner_radius=10)
        self.left_canvas.create_window((0, 0), window=self.left_frame, anchor="nw")
        
        def _update_scroll(event):
            self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))

        self.left_frame.bind("<Configure>", _update_scroll)
        
        def _on_mousewheel(event):
            self.left_canvas.yview_scroll(-1 * int(event.delta / 120), "units")

        self.left_frame.bind("<Enter>", lambda _: self.left_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.left_frame.bind("<Leave>", lambda _: self.left_canvas.unbind_all("<MouseWheel>"))

        left = self.left_frame

        # ==================== SECCIÓN CONEXIÓN ====================
        ctk.CTkLabel(left, text="🔌 Conexión", font=("Arial", 25, "bold")).pack(pady=6)

        modo_menu = ctk.CTkOptionMenu(left, variable=self.modo_conexion, values=["Serial", "Wi-Fi"], command=self.change_mode)
        modo_menu.pack(pady=6)

        self.frame_opts = ctk.CTkFrame(left)
        self.frame_opts.pack(pady=6, fill="x")
        self.create_serial_opts()

        # Frame para botones de conexión
        connect_frame = ctk.CTkFrame(left)
        connect_frame.pack(pady=10, fill="x")
        
        btn_connect = ctk.CTkButton(connect_frame, text="Conectar", command=self.connect, width=200, height=40)
        btn_connect.pack(side="left", padx=5, pady=5)
        btn_disconnect = ctk.CTkButton(connect_frame, text="Desconectar", command=self.disconnect, width=200, height=40)
        btn_disconnect.pack(side="left", padx=5, pady=5)

        # Separador
        ctk.CTkFrame(left, height=2, fg_color="gray").pack(fill="x", padx=20, pady=10)

        # ==================== SECCIÓN CONTROL PRINCIPAL ====================
        ctk.CTkLabel(left, text="🎮 Control Principal", font=("Arial", 22, "bold")).pack(pady=10)

        # Frame para botones de encendido/apagado
        power_frame = ctk.CTkFrame(left)
        power_frame.pack(pady=10, fill="x", padx=10)
        
        ctk.CTkButton(power_frame, text="🔌 ENERGIZAR (ON)", fg_color="#2e7d32", 
                     command=lambda: self.send_command("ON"), height=45).pack(side="left", padx=5, fill="x", expand=True)
        ctk.CTkButton(power_frame, text="⚙️ APAGAR (OFF)", fg_color="#d32f2f", 
                     command=lambda: self.send_command("OFF"), height=45).pack(side="left", padx=5, fill="x", expand=True)

        # NUEVO: Botón para establecer cero de referencia
        zero_frame = ctk.CTkFrame(left)
        zero_frame.pack(pady=10, fill="x", padx=10)
        
        ctk.CTkButton(zero_frame, text="🎯 ESTABLECER CERO", fg_color="#1E88E5", 
                     command=self.set_zero_reference, height=45).pack(fill="x", padx=5, pady=5)
        
        # Frame para paro de emergencia y reset
        emergency_frame = ctk.CTkFrame(left)
        emergency_frame.pack(pady=10, fill="x", padx=10)
        
        # PARO DE EMERGENCIA - ACCIÓN INMEDIATA
        self.emergency_btn = ctk.CTkButton(emergency_frame, text="🛑 PARO DE EMERGENCIA", 
                     fg_color="#eb640a", hover_color="#7f0000", font=("Arial", 14, "bold"),
                     command=self.emergency_stop_immediate, height=55)
        self.emergency_btn.pack(fill="x", padx=5, pady=5)
        
        
        # Botón RESET
        ctk.CTkButton(emergency_frame, text="🔄 REINICIAR SISTEMA (RESET)", fg_color="#2e7d32", 
                     command=self.reset_system, height=45).pack(fill="x", padx=5, pady=5)

        # Indicadores de estado
        status_frame = ctk.CTkFrame(left)
        status_frame.pack(pady=15, fill="x", padx=10)
        
        self.label_status = ctk.CTkLabel(status_frame, text="Estado: Desconectado", text_color="red", font=("Arial", 14))
        self.label_status.pack(pady=5)
        
        self.wifi_info_label = ctk.CTkLabel(status_frame, text="📶 WiFi: Desconectado", text_color="red")
        self.wifi_info_label.pack(pady=5)
        
        # Indicador de cero establecido
        self.zero_label = ctk.CTkLabel(status_frame, text="🎯 Cero: NO establecido", text_color="orange")
        self.zero_label.pack(pady=5)
        
        # Indicador de paro de emergencia
        self.emergency_label = ctk.CTkLabel(status_frame, text="", font=("Arial", 12, "bold"))
        self.emergency_label.pack(pady=5)
        
        # Indicador de ejecución en bucle
        self.bucle_label = ctk.CTkLabel(status_frame, text="", font=("Arial", 12))
        self.bucle_label.pack(pady=5)

        # ==================== PANEL DERECHO (PESTAÑAS CON SCROLL) ====================
        right_main = ctk.CTkFrame(self, corner_radius=10)
        right_main.pack(side="right", fill="both", expand=True, padx=12, pady=12)

        # ==================== SISTEMA DE PESTAÑAS CON SCROLL ====================
        self.tabview = ctk.CTkTabview(right_main, width=600, height=400)
        self.tabview.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Pestañas
        self.tab_control = self.tabview.add("⚙️ Control Motor")
        self.tab_trayectoria = self.tabview.add("🔄 Trayectorias")

        # ==================== PESTAÑA CONTROL DE MOTOR ====================
        # Contenedor con scroll para Control Motor
        control_scroll_frame = ctk.CTkScrollableFrame(self.tab_control, width=580, height=380)
        control_scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(control_scroll_frame, text="⚙️ Control de Motores", font=("Arial",25, "bold")).pack(pady=6)

        # Panel parámetros
        param_frame = ctk.CTkFrame(control_scroll_frame)
        param_frame.pack(pady=6, padx=6, fill="x")
        ctk.CTkLabel(param_frame, text="Pasos (comando directo)").grid(row=0, column=0, padx=6, pady=6)
        self.entry_steps = ctk.CTkEntry(param_frame, width=100)
        self.entry_steps.insert(0, "200")
        self.entry_steps.grid(row=0, column=1, padx=6, pady=6)
        ctk.CTkLabel(param_frame, text="Velocidad (1-1000 RPM)").grid(row=0, column=2, padx=6, pady=6)
        self.entry_vel_direct = ctk.CTkEntry(param_frame, width=100)
        self.entry_vel_direct.insert(0, "500")
        self.entry_vel_direct.grid(row=0, column=3, padx=6, pady=6)

        # Control directo
        f_direct = ctk.CTkFrame(control_scroll_frame)
        f_direct.pack(pady=30, padx=30, fill="x")
        ctk.CTkLabel(f_direct, text="CONTROL DIRECTO", width=250).pack(side="left", padx=15)
        self.direct_motor_var = ctk.StringVar(value="M1")
        self.direct_motor_menu = ctk.CTkOptionMenu(f_direct, variable=self.direct_motor_var,height=40, values=["M1", "M2", "M3", "M4"])
        self.direct_motor_menu.pack(side="left", padx=6)
        ctk.CTkButton(f_direct, text="⟲ Antihorario", command=lambda: self.direct_move("A"),height=40).pack(side="left", padx=15)
        ctk.CTkButton(f_direct, text="⟳ Horario", command=lambda: self.direct_move("H"),height=40).pack(side="left", padx=10)

        # Control de garra
        garra_frame = ctk.CTkFrame(control_scroll_frame)
        garra_frame.pack(pady=20, padx=30, fill="x")
        
        ctk.CTkLabel(garra_frame, text="CONTROL GARRA", width=250).pack(side="left", padx=15)
        ctk.CTkButton(garra_frame, text="🔓 ABRIR GARRA", fg_color="#388E3C", 
                     command=lambda: self.send_command("ABRIR"), height=40).pack(side="left", padx=15)
        ctk.CTkButton(garra_frame, text="🔒 CERRAR GARRA", fg_color="#D32F2F", 
                     command=lambda: self.send_command("CERRAR"), height=40).pack(side="left", padx=15)

        # ==================== PESTAÑA TRAYECTORIAS COORDINADAS CON SCROLL COMPLETO ====================
        # Contenedor principal con scroll para Trayectorias
        tray_scroll_frame = ctk.CTkScrollableFrame(self.tab_trayectoria, width=580, height=380)
        tray_scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(tray_scroll_frame, text="🔄 Movimiento Coordinado de Trayectorias", 
                    font=("Arial",20, "bold")).pack(pady=10)

        # Mensaje importante sobre cero
        warning_frame = ctk.CTkFrame(tray_scroll_frame, fg_color="#FFEB3B", corner_radius=8)
        warning_frame.pack(pady=5, padx=20, fill="x")
        
        warning_text = "⚠️ IMPORTANTE: Establece el CERO de referencia antes de usar trayectorias"
        ctk.CTkLabel(warning_frame, text=warning_text, text_color="#000000", 
                    font=("Arial", 12, "bold")).pack(pady=8, padx=10)

        # Frame para coordenadas (AHORA CON VALORES NEGATIVOS PERMITIDOS)
        tray_frame = ctk.CTkFrame(tray_scroll_frame)
        tray_frame.pack(pady=15, padx=20, fill="x")

        # Título de columnas
        title_frame = ctk.CTkFrame(tray_frame)
        title_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(title_frame, text="Motor", width=80).pack(side="left", padx=5)
        ctk.CTkLabel(title_frame, text="Ángulo Virtual (°)", width=120).pack(side="left", padx=5)
        ctk.CTkLabel(title_frame, text="Dirección", width=100).pack(side="left", padx=5)

        # Campos para cada motor CON DIRECCIÓN Y VALORES NEGATIVOS
        self.tray_entries = []
        self.tray_dir_vars = []
        for i in range(4):
            row_frame = ctk.CTkFrame(tray_frame)
            row_frame.pack(fill="x", pady=2)
            ctk.CTkLabel(row_frame, text=f"M{i+1}:", width=80).pack(side="left", padx=5)
            
            entry = ctk.CTkEntry(row_frame, width=120)
            entry.insert(0, "0.0")
            entry.pack(side="left", padx=5)
            self.tray_entries.append(entry)
            
            dir_var = ctk.StringVar(value="H")
            dir_menu = ctk.CTkOptionMenu(row_frame, variable=dir_var, values=["H", "A"], width=80)
            dir_menu.pack(side="left", padx=5)
            self.tray_dir_vars.append(dir_var)

        # Velocidad y Garra
        config_frame = ctk.CTkFrame(tray_frame)
        config_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(config_frame, text="Velocidad:", width=80).pack(side="left", padx=5)
        self.tray_vel_entry = ctk.CTkEntry(config_frame, width=100)
        self.tray_vel_entry.insert(0, "500")
        self.tray_vel_entry.pack(side="left", padx=5)
        
        ctk.CTkLabel(config_frame, text="Garra:", width=60).pack(side="left", padx=5)
        self.tray_garra_var = ctk.StringVar(value="ABRIR")
        garra_menu = ctk.CTkOptionMenu(config_frame, variable=self.tray_garra_var, values=["ABRIR", "CERRAR"], width=100)
        garra_menu.pack(side="left", padx=5)

        # Control de ejecución en bucle
        bucle_frame = ctk.CTkFrame(tray_scroll_frame)
        bucle_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(bucle_frame, text="🔄 Ejecución en Bucle:", font=("Arial", 14)).pack(pady=5)
        
        bucle_controls_frame = ctk.CTkFrame(bucle_frame)
        bucle_controls_frame.pack(pady=5)
        
        ctk.CTkLabel(bucle_controls_frame, text="Repeticiones:").pack(side="left", padx=5)
        self.bucle_repeticiones = ctk.CTkEntry(bucle_controls_frame, width=80)
        self.bucle_repeticiones.insert(0, "1")
        self.bucle_repeticiones.pack(side="left", padx=5)
        
        ctk.CTkLabel(bucle_controls_frame, text="Delay entre ciclos (s):").pack(side="left", padx=5)
        self.bucle_delay = ctk.CTkEntry(bucle_controls_frame, width=80)
        self.bucle_delay.insert(0, "1.0")
        self.bucle_delay.pack(side="left", padx=5)
        
        # Botones de ejecución (ahora con opción de bucle)
        ejecutar_frame = ctk.CTkFrame(tray_scroll_frame)
        ejecutar_frame.pack(pady=10)

        self.btn_ejecutar_trayectoria = ctk.CTkButton(
            ejecutar_frame,
            text="🚀 EJECUTAR 1 VEZ",
            fg_color="#388E3C",
            command=self.ejecutar_trayectoria_o_secuencia,
            height=50,
            width=180
        )
        self.btn_ejecutar_trayectoria.pack(side="left", padx=5)
        
        self.btn_ejecutar_bucle = ctk.CTkButton(
            ejecutar_frame,
            text="🔁 EJECUTAR EN BUCLE",
            fg_color="#FF9800",
            command=self.ejecutar_trayectoria_bucle,
            height=50,
            width=180
        )
        self.btn_ejecutar_bucle.pack(side="left", padx=5)
        
        self.btn_detener_bucle = ctk.CTkButton(
            ejecutar_frame,
            text="⏹️ DETENER BUCLE",
            fg_color="#D32F2F",
            command=self.detener_ejecucion_bucle,
            height=50,
            width=180,
            state="disabled"
        )
        self.btn_detener_bucle.pack(side="left", padx=5)

        # Botón para crear secuencias combinadas
        ctk.CTkButton(
            tray_scroll_frame,
            text="🔗 CREAR PICK-AND-PLACE",
            fg_color="#1E88E5",
            command=self.crear_trayectoria_pick_and_place,
            height=50,
            width=250
        ).pack(pady=5)

        # Separador
        ctk.CTkFrame(tray_scroll_frame, height=2, fg_color="gray").pack(fill="x", padx=20, pady=10)

        # ==================== SISTEMA COMPLETO DE GUARDAR TRAYECTORIAS ====================
        tray_save_section = ctk.CTkFrame(tray_scroll_frame)
        tray_save_section.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(tray_save_section, text="💾 SISTEMA DE TRAYECTORIAS GUARDADAS", 
                    font=("Arial", 16, "bold")).pack(pady=10)

        # Frame para posiciones rápidas
        tray_pos_frame = ctk.CTkFrame(tray_save_section)
        tray_pos_frame.pack(pady=10, fill="x")

        ctk.CTkLabel(tray_pos_frame, text="📋 Posiciones Rápidas:", font=("Arial",14)).pack(pady=5)
        
        pos_rapidas_frame = ctk.CTkFrame(tray_pos_frame)
        pos_rapidas_frame.pack(pady=5)
        
        # Botones de posiciones rápidas (2 filas)
        rapid_buttons_frame1 = ctk.CTkFrame(pos_rapidas_frame)
        rapid_buttons_frame1.pack(pady=5)
        
        ctk.CTkButton(rapid_buttons_frame1, text="🏠 CERO VIRTUAL", 
                     command=lambda: self.cargar_posicion_rapida([0, 0, 0, 0], "HHHH"), 
                     width=180, height=35).pack(side="left", padx=5)
        
        rapid_buttons_frame2 = ctk.CTkFrame(pos_rapidas_frame)
        rapid_buttons_frame2.pack(pady=5)
        
        ctk.CTkButton(rapid_buttons_frame2, text="🔄 TEST +45/-45", 
                     command=lambda: self.cargar_posicion_rapida([45, -45, 45, -45], "HAHA"), 
                     width=180, height=35).pack(side="left", padx=5)
        ctk.CTkButton(rapid_buttons_frame2, text="⚡ EXTENDIDO", 
                     command=lambda: self.cargar_posicion_rapida([180, 135, 90, 45], "HHHH"), 
                     width=180, height=35).pack(side="left", padx=5)
        ctk.CTkButton(rapid_buttons_frame2, text="📏 CUADRADO", 
                     command=lambda: self.cargar_posicion_rapida([90, 0, 90, 0], "HAHA"), 
                     width=180, height=35).pack(side="left", padx=5)

        # Separador
        ctk.CTkFrame(tray_save_section, height=2, fg_color="gray").pack(fill="x", pady=10)

        # ==================== SISTEMA DE GUARDAR/CARGAR TRAYECTORIAS ====================
        save_load_frame = ctk.CTkFrame(tray_save_section)
        save_load_frame.pack(pady=10, fill="x")

        ctk.CTkLabel(save_load_frame, text="📁 Administrar Trayectorias:", font=("Arial",14)).pack(pady=5)
        
        # Frame para botones de guardar/eliminar
        save_buttons_frame = ctk.CTkFrame(save_load_frame)
        save_buttons_frame.pack(pady=10)
        
        ctk.CTkButton(save_buttons_frame, text="💾 GUARDAR TRAYECTORIA", 
                     command=self.save_trayectoria, width=200, height=40,
                     fg_color="#1E88E5").pack(side="left", padx=10)
        
        ctk.CTkButton(save_buttons_frame, text="🗑️ ELIMINAR TRAYECTORIA", 
                     command=self.delete_trayectoria, width=200, height=40,
                     fg_color="#D32F2F").pack(side="left", padx=10)
        
        ctk.CTkButton(save_buttons_frame, text="📥 CARGAR TRAYECTORIA", 
                     command=self.cargar_trayectoria_selected, width=200, height=40,
                     fg_color="#388E3C").pack(side="left", padx=10)

        # Frame para selección de trayectorias guardadas
        selection_frame = ctk.CTkFrame(save_load_frame)
        selection_frame.pack(pady=10, fill="x")
        
        ctk.CTkLabel(selection_frame, text="Trayectorias Guardadas:", font=("Arial",12)).pack(pady=5)
        
        # Dropdown trayectorias guardadas 
        tray_keys = list(self.trayectorias.keys()) or ["Inicio"]
        self.tray_menu = ctk.CTkOptionMenu(selection_frame, variable=self.tray_var, 
                                          values=tray_keys, width=300, height=35,
                                          command=self.cargar_trayectoria)
        self.tray_menu.pack(pady=5)
        if tray_keys:
            self.tray_var.set(tray_keys[0])
        
        # Info de la trayectoria seleccionada
        self.tray_info_label = ctk.CTkLabel(selection_frame, text="", font=("Arial", 10))
        self.tray_info_label.pack(pady=5)

        # Actualizar info de trayectorias
        self.update_trayectorias_info()

        # ==================== TERMINAL PLEGABLE ====================
        terminal_controls = ctk.CTkFrame(right_main)
        terminal_controls.pack(fill="x", padx=8, pady=(10, 5))
        
        self.terminal_toggle_btn = ctk.CTkButton(
            terminal_controls, 
            text="📟 ▲ Ocultar Terminal", 
            fg_color="#1E88E5",
            command=self.toggle_terminal,
            width=180,
            height=35
        )
        self.terminal_toggle_btn.pack(side="left", padx=5)
        
        ctk.CTkButton(
            terminal_controls, 
            text="🧹 Limpiar", 
            command=self.clear_terminal,
            width=80,
            height=35
        ).pack(side="right", padx=5)
        
        self.terminal_frame = ctk.CTkFrame(right_main)
        self.terminal_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        
        self.text_terminal = ctk.CTkTextbox(self.terminal_frame, height=200)
        self.text_terminal.pack(fill="both", expand=True, padx=5, pady=5)
        self.text_terminal.insert("end", "Terminal lista...\n")
        self.text_terminal.configure(state="disabled")

        # Actualizar estado inicial
        self.update_emergency_display()
        self.update_zero_display()
        self.update_bucle_display()
        self.update_trayectorias_info()

    # ==================== FUNCIONES PARA EJECUCIÓN EN BUCLE ====================
    
    def ejecutar_trayectoria_bucle(self):
        """Ejecutar trayectoria en bucle repetitivo"""
        if not self.connected:
            self.log("⚠️ No conectado al robot")
            return
        
        if self.emergency_stop_active:
            self.log("⛔ Sistema en paro de emergencia - Comando rechazado")
            return
        
        if self.ejecutando_bucle:
            self.log("⚠️ Ya hay un bucle en ejecución")
            return
        
        # Obtener parámetros del bucle
        try:
            repeticiones = int(self.bucle_repeticiones.get())
            if repeticiones < 1:
                self.log("⚠️ El número de repeticiones debe ser mayor a 0")
                return
                
            delay = float(self.bucle_delay.get())
            if delay < 0:
                self.log("⚠️ El delay no puede ser negativo")
                return
                
        except ValueError:
            self.log("⚠️ Valores de bucle inválidos")
            return
        
        # Iniciar ejecución en bucle
        self.ejecutando_bucle = True
        self.repeticiones_bucle = repeticiones
        self.repeticion_actual = 0
        
        # Actualizar interfaz
        self.btn_ejecutar_bucle.configure(state="disabled", fg_color="#757575")
        self.btn_ejecutar_trayectoria.configure(state="disabled", fg_color="#757575")
        self.btn_detener_bucle.configure(state="normal", fg_color="#D32F2F")
        
        # Iniciar hilo de ejecución
        self.bucle_thread = threading.Thread(target=self._ejecutar_bucle_thread, 
                                            args=(repeticiones, delay), 
                                            daemon=True)
        self.bucle_thread.start()
        
        self.log(f"🔄 Iniciando ejecución en bucle: {repeticiones} repeticiones")
    
    def _ejecutar_bucle_thread(self, repeticiones, delay):
        """Hilo para ejecutar el bucle"""
        try:
            for i in range(repeticiones):
                if not self.ejecutando_bucle:
                    break
                    
                self.repeticion_actual = i + 1
                self.update_bucle_display()
                
                self.log(f"🔄 CICLO {i+1}/{repeticiones}")
                
                # EJECUTAR TRAYECTORIA CORRECTAMENTE (CON O SIN CERO)
                nombre = self.tray_var.get()
                if nombre in self.trayectorias:
                    tray = self.trayectorias[nombre]
                    
                    if tray.get("tipo") == "combinada":
                        # Para secuencias combinadas: ESTABLECER CERO al inicio del ciclo completo
                        self.log("🎯 Estableciendo CERO al inicio del ciclo...")
                        if not self.send_command("ZERO", pause=0.3):
                            self.log("❌ No se pudo establecer cero")
                            break
                        self.zero_set = True
                        self.current_virtual_pos = [0.0, 0.0, 0.0, 0.0]
                        self.update_zero_display()
                        
                        # Ejecutar secuencia combinada
                        self.ejecutar_secuencia_combinada_sincrona(tray)
                    else:
                        # Para trayectorias simples: ESTABLECER CERO antes de cada ejecución
                        self.log("🎯 Estableciendo CERO automáticamente...")
                        if not self.send_command("ZERO", pause=0.3):
                            self.log("❌ No se pudo establecer cero")
                            break
                        self.zero_set = True
                        self.current_virtual_pos = [0.0, 0.0, 0.0, 0.0]
                        self.update_zero_display()
                        
                        # Ejecutar trayectoria simple
                        self.ejecutar_trayectoria_como_comando(tray)
                else:
                    # Para trayectorias desde campos: ESTABLECER CERO antes de cada ejecución
                    self.log("🎯 Estableciendo CERO automáticamente...")
                    if not self.send_command("ZERO", pause=0.3):
                        self.log("❌ No se pudo establecer cero")
                        break
                    self.zero_set = True
                    self.current_virtual_pos = [0.0, 0.0, 0.0, 0.0]
                    self.update_zero_display()
                    
                    # Ejecutar desde campos
                    self._ejecutar_trayectoria_desde_campos()
                
                # Esperar entre ciclos (excepto en el último)
                if i < repeticiones - 1 and delay > 0 and self.ejecutando_bucle:
                    self.log(f"⏳ Esperando {delay} segundos antes del siguiente ciclo...")
                    
                    # Esperar en segmentos para permitir detener
                    segmentos = int(delay * 10)  # 10 verificaciones por segundo
                    for _ in range(segmentos):
                        if not self.ejecutando_bucle:
                            break
                        time.sleep(0.1)
                
            if self.ejecutando_bucle:
                self.log(f"✅ Bucle completado: {repeticiones} ciclos ejecutados")
                
        except Exception as e:
            self.log(f"❌ Error en el bucle: {e}")
            
        finally:
            # Restaurar estado
            self.finalizar_ejecucion_bucle()
    
    def ejecutar_secuencia_combinada_sincrona(self, tray):
        """Ejecutar secuencia combinada de forma síncrona (para bucle)"""
        try:
            pick_name = tray["pick"]
            place_name = tray["place"]
            
            if pick_name not in self.trayectorias:
                self.log(f"❌ Trayectoria de recogida '{pick_name}' no encontrada")
                return False
            
            if place_name not in self.trayectorias:
                self.log(f"❌ Trayectoria de dejada '{place_name}' no encontrada")
                return False
            
            pick_tray = self.trayectorias[pick_name]
            place_tray = self.trayectorias[place_name]
            
            self.log("➡️ Ejecutando trayectoria de RECOGIDA...")
            if not self.ejecutar_trayectoria_como_comando(pick_tray):
                self.log("❌ Error en trayectoria de recogida")
                return False
            
            # Acción de garra intermedia
            if tray["garra_accion"] != "NO CAMBIAR" and self.ejecutando_bucle:
                time.sleep(0.5)
                if not self.send_command(tray["garra_accion"]):
                    self.log("❌ Error en acción de garra")
                    return False
                self.log(f"  🔧 Garra: {tray['garra_accion']}")
            
            # Espera configurada
            delay = tray["delay"]
            if delay > 0 and self.ejecutando_bucle:
                self.log(f"  ⏳ Esperando {delay} segundos...")
                
                # Esperar en segmentos para permitir detener
                segmentos = int(delay * 10)
                for _ in range(segmentos):
                    if not self.ejecutando_bucle:
                        return False
                    time.sleep(0.1)
            
            # Ejecutar segunda trayectoria (PERO NO ESTABLECER CERO NUEVAMENTE)
            # La segunda trayectoria es relativa al MISMO cero que la primera
            self.log("➡️ Ejecutando trayectoria de DEJADA...")
            if not self.ejecutar_trayectoria_como_comando(place_tray):
                self.log("❌ Error en trayectoria de dejada")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"❌ Error en secuencia: {e}")
            return False
    
    def ejecutar_trayectoria_o_secuencia(self):
        """Ejecutar una sola vez con cero automático"""
        if not self.connected:
            self.log("⚠️ No conectado al robot")
            return
        
        if self.emergency_stop_active:
            self.log("⛔ Sistema en paro de emergencia - Comando rechazado")
            return
        
        if self.ejecutando_bucle:
            self.log("⚠️ Hay un bucle en ejecución - Use detener bucle primero")
            return
        
        # Obtener la trayectoria seleccionada
        nombre = self.tray_var.get()
        if nombre in self.trayectorias:
            tray = self.trayectorias[nombre]
            
            # Verificar si es una secuencia combinada
            if tray.get("tipo") == "combinada":
                # Para secuencias combinadas: ESTABLECER CERO una sola vez al inicio
                self.log("🎯 Estableciendo CERO al inicio de la secuencia...")
                if self.send_command("ZERO", pause=0.3):
                    self.zero_set = True
                    self.current_virtual_pos = [0.0, 0.0, 0.0, 0.0]
                    self.update_zero_display()
                    self.log("✅ Cero establecido")
                    
                    # Ejecutar secuencia combinada
                    self.ejecutar_secuencia_combinada()
                else:
                    self.log("❌ No se pudo establecer cero")
            else:
                # Para trayectorias simples: ESTABLECER CERO y ejecutar
                self.log("🎯 Estableciendo CERO automáticamente...")
                if self.send_command("ZERO", pause=0.3):
                    self.zero_set = True
                    self.current_virtual_pos = [0.0, 0.0, 0.0, 0.0]
                    self.update_zero_display()
                    self.log("✅ Cero establecido")
                    
                    # Ejecutar trayectoria simple
                    self.ejecutar_trayectoria_como_comando(tray)
                else:
                    self.log("❌ No se pudo establecer cero")
        else:
            # Para trayectorias desde campos: ESTABLECER CERO y ejecutar
            self.log("🎯 Estableciendo CERO automáticamente...")
            if self.send_command("ZERO", pause=0.3):
                self.zero_set = True
                self.current_virtual_pos = [0.0, 0.0, 0.0, 0.0]
                self.update_zero_display()
                self.log("✅ Cero establecido")
                
                # Ejecutar desde campos
                self._ejecutar_trayectoria_desde_campos()
            else:
                self.log("❌ No se pudo establecer cero")
    
    # ==================== FUNCION CORREGIDA PARA EJECUTAR SECUENCIAS ====================
    
    def ejecutar_secuencia_combinada(self):
        """Ejecutar una secuencia pick-and-place completa (corregida)"""
        if not self.connected:
            self.log("⚠️ No conectado al robot")
            return
        
        if self.emergency_stop_active:
            self.log("⛔ Sistema en paro de emergencia - Comando rechazado")
            return
        
        # Obtener la trayectoria seleccionada
        nombre = self.tray_var.get()
        if nombre not in self.trayectorias:
            self.log("⚠️ Trayectoria no encontrada")
            return
        
        tray = self.trayectorias[nombre]
        
        # Verificar si es una secuencia combinada
        if tray.get("tipo") != "combinada":
            self.log("⚠️ Esta no es una secuencia combinada (pick-and-place)")
            return
        
        # Verificar que existan las subtrayectorias
        pick_name = tray["pick"]
        place_name = tray["place"]
        
        if pick_name not in self.trayectorias:
            self.log(f"❌ Trayectoria de recogida '{pick_name}' no encontrada")
            return
        
        if place_name not in self.trayectorias:
            self.log(f"❌ Trayectoria de dejada '{place_name}' no encontrada")
            return
        
        # Obtener las trayectorias individuales
        pick_tray = self.trayectorias[pick_name]
        place_tray = self.trayectorias[place_name]
        
        self.log(f"🤖 Iniciando secuencia PICK-AND-PLACE: {nombre}")
        self.log(f"  1. Pick: {pick_name}")
        self.log(f"  2. Place: {place_name}")
        self.log(f"  Delay: {tray['delay']}s")
        
        # Ejecutar en un hilo separado para no bloquear la UI
        def ejecutar_secuencia_thread():
            try:
                # IMPORTANTE: NO establecer cero aquí, ya se estableció en ejecutar_trayectoria_o_secuencia
                
                # Paso 1: Ejecutar trayectoria de recogida
                self.log("➡️ Ejecutando trayectoria de RECOGIDA...")
                if not self.ejecutar_trayectoria_como_comando(pick_tray):
                    self.log("❌ Error en trayectoria de recogida")
                    return
                
                # Opcional: Acción de garra intermedia
                if tray["garra_accion"] != "NO CAMBIAR":
                    time.sleep(0.5)  # Pequeña pausa antes de cambiar garra
                    if not self.send_command(tray["garra_accion"]):
                        self.log("❌ Error en acción de garra")
                        return
                    self.log(f"  🔧 Garra: {tray['garra_accion']}")
                
                # Espera configurada
                delay = tray["delay"]
                if delay > 0:
                    self.log(f"  ⏳ Esperando {delay} segundos...")
                    time.sleep(delay)
                
                # Paso 2: Ejecutar trayectoria de dejada (RELATIVA AL MISMO CERO)
                self.log("➡️ Ejecutando trayectoria de DEJADA...")
                if not self.ejecutar_trayectoria_como_comando(place_tray):
                    self.log("❌ Error en trayectoria de dejada")
                    return
                
                self.log("✅ Secuencia PICK-AND-PLACE completada exitosamente!")
                
            except Exception as e:
                self.log(f"❌ Error en secuencia: {e}")
        
        # Iniciar el hilo
        threading.Thread(target=ejecutar_secuencia_thread, daemon=True).start()
    
    # ==================== FUNCIÓN PARA EJECUTAR TRAYECTORIAS ====================
    
    def ejecutar_trayectoria_como_comando(self, tray):
        """Ejecutar una trayectoria desde su diccionario (corregida)"""
        # Construir comando TRAY
        targets = tray["pos"]
        direcciones = tray.get("dirs", "HHHH")
        velocidad = tray.get("vel", 500)
        estado_garra = tray.get("garra", "ABRIR")
        
        comando = f"TRAY:{targets[0]},{targets[1]},{targets[2]},{targets[3]},{direcciones},{velocidad},{estado_garra}"
        
        if self.send_command(comando, pause=0.5):
            # Actualizar posiciones virtuales estimadas (solo para seguimiento en Python)
            for i, pos in enumerate(targets):
                if i < 4:
                    self.update_virtual_position(i, pos)
            
            self.log(f"  ✅ Trayectoria ejecutada: {targets}")
            return True
        else:
            self.log("  ❌ Error al ejecutar subtrayectoria")
            return False
    
    def _ejecutar_trayectoria_desde_campos(self):
        """Ejecutar trayectoria desde campos de entrada"""
        # Leer valores de los campos
        targets = []
        direcciones = ""
        
        for i, entry in enumerate(self.tray_entries):
            try:
                valor = float(entry.get())
                if valor < -360 or valor > 360:
                    self.log(f"⚠️ Valor fuera de rango para M{i+1}: {valor}")
                    return
                targets.append(valor)
                
                dir_char = self.tray_dir_vars[i].get()
                direcciones += dir_char
                
            except:
                self.log(f"⚠️ Valor inválido para M{i+1}")
                return
                
        try:
            velocidad = int(self.tray_vel_entry.get())
            velocidad = max(1, min(1000, velocidad))
        except:
            self.log("⚠️ Velocidad inválida para trayectoria")
            return
            
        estado_garra = self.tray_garra_var.get()
        
        # Construir comando
        comando = f"TRAY:{targets[0]},{targets[1]},{targets[2]},{targets[3]},{direcciones},{velocidad},{estado_garra}"
        
        if self.send_command(comando):
            # Actualizar posiciones virtuales estimadas
            for i, pos in enumerate(targets):
                if i < 4:
                    self.update_virtual_position(i, pos)
                    
            self.log(f"🔄 Enviada trayectoria coordinada: {targets} dirs:{direcciones} vel:{velocidad} garra:{estado_garra}")
        else:
            self.log("❌ Error al enviar trayectoria")
    
    def detener_ejecucion_bucle(self):
        """Detener la ejecución en bucle"""
        if self.ejecutando_bucle:
            self.ejecutando_bucle = False
            self.log("⏹️ Deteniendo ejecución en bucle...")
    
    def finalizar_ejecucion_bucle(self):
        """Finalizar la ejecución en bucle y restaurar interfaz"""
        self.ejecutando_bucle = False
        
        # Actualizar interfaz en el hilo principal
        self.after(0, self._actualizar_interfaz_despues_bucle)
    
    def _actualizar_interfaz_despues_bucle(self):
        """Actualizar interfaz después de finalizar bucle"""
        self.btn_ejecutar_bucle.configure(state="normal", fg_color="#FF9800")
        self.btn_ejecutar_trayectoria.configure(state="normal", fg_color="#388E3C")
        self.btn_detener_bucle.configure(state="disabled", fg_color="#757575")
        self.update_bucle_display()
    
    def update_bucle_display(self):
        """Actualizar la visualización del estado del bucle"""
        if self.ejecutando_bucle:
            texto = f"🔁 Bucle activo: {self.repeticion_actual}/{self.repeticiones_bucle}"
            self.bucle_label.configure(text=texto, text_color="#FF9800")
        else:
            self.bucle_label.configure(text="", text_color="gray")
    
    # ==================== FUNCIONES EXISTENTES  ====================
    
    def crear_trayectoria_pick_and_place(self):
        """Crear una trayectoria combinada pick-and-place"""
        nombre = simpledialog.askstring("Pick-and-Place", 
                                       "Nombre para la secuencia combinada:", 
                                       parent=self)
        if not nombre:
            return
        
        # Obtener trayectorias disponibles
        tray_keys = list(self.trayectorias.keys())
        if len(tray_keys) < 2:
            messagebox.showwarning("Error", "Necesita al menos 2 trayectorias guardadas")
            return
        
        # Diálogo para seleccionar trayectorias
        pick_window = ctk.CTkToplevel(self)
        pick_window.title("Seleccionar Trayectorias")
        pick_window.geometry("400x300")
        pick_window.transient(self)
        pick_window.grab_set()
        
        ctk.CTkLabel(pick_window, text="Selecciona la secuencia:", 
                    font=("Arial", 14, "bold")).pack(pady=10)
        
        # Frame para primera trayectoria (pick)
        frame_pick = ctk.CTkFrame(pick_window)
        frame_pick.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(frame_pick, text="1. Trayectoria de RECOGIDA:").pack(pady=5)
        pick_var = ctk.StringVar(value=tray_keys[0])
        pick_menu = ctk.CTkOptionMenu(frame_pick, variable=pick_var, 
                                      values=tray_keys, width=250)
        pick_menu.pack(pady=5)
        
        # Frame para segunda trayectoria (place)
        frame_place = ctk.CTkFrame(pick_window)
        frame_place.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(frame_place, text="2. Trayectoria de DEJADA:").pack(pady=5)
        place_var = ctk.StringVar(value=tray_keys[1] if len(tray_keys) > 1 else tray_keys[0])
        place_menu = ctk.CTkOptionMenu(frame_place, variable=place_var, 
                                       values=tray_keys, width=250)
        place_menu.pack(pady=5)
        
        # Frame para opciones
        frame_opts = ctk.CTkFrame(pick_window)
        frame_opts.pack(pady=10, padx=20, fill="x")
        
        # Tiempo de espera entre trayectorias
        ctk.CTkLabel(frame_opts, text="Tiempo de espera (seg):").pack(pady=5)
        delay_var = ctk.StringVar(value="1.0")
        delay_entry = ctk.CTkEntry(frame_opts, textvariable=delay_var, width=100)
        delay_entry.pack(pady=5)
        
        # Estado de garra intermedio
        garra_var = ctk.StringVar(value="CERRAR")
        ctk.CTkLabel(frame_opts, text="Acción garra entre movimientos:").pack(pady=5)
        garra_menu = ctk.CTkOptionMenu(frame_opts, variable=garra_var, 
                                       values=["CERRAR", "ABRIR", "NO CAMBIAR"])
        garra_menu.pack(pady=5)
        
        # Variables para almacenar resultados
        result = {"confirmed": False}
        
        def confirmar():
            try:
                delay = float(delay_var.get())
                if delay < 0 or delay > 10:
                    messagebox.showerror("Error", "Delay debe ser entre 0 y 10 segundos")
                    return
            except:
                messagebox.showerror("Error", "Delay inválido")
                return
            
            result.update({
                "confirmed": True,
                "pick": pick_var.get(),
                "place": place_var.get(),
                "delay": delay,
                "garra_accion": garra_var.get()
            })
            pick_window.destroy()
        
        def cancelar():
            pick_window.destroy()
        
        # Botones
        btn_frame = ctk.CTkFrame(pick_window)
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Crear", command=confirmar, 
                      fg_color="#1E88E5", width=100).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancelar", command=cancelar, 
                      fg_color="#757575", width=100).pack(side="left", padx=10)
        
        self.wait_window(pick_window)
        
        if not result["confirmed"]:
            return
        
        # Guardar la secuencia combinada
        self.trayectorias[nombre] = {
            "tipo": "combinada",
            "pick": result["pick"],
            "place": result["place"],
            "delay": result["delay"],
            "garra_accion": result["garra_accion"],
            "descripcion": f"Pick: {result['pick']} → Place: {result['place']}"
        }
        
        self.save_trayectorias_file()
        
        # Actualizar dropdown
        if hasattr(self, 'tray_menu') and self.tray_menu:
            tray_keys = list(self.trayectorias.keys())
            self.tray_menu.configure(values=tray_keys)
            self.tray_var.set(nombre)
            self.update_trayectorias_info()
        
        self.log(f"💾 Secuencia combinada '{nombre}' guardada:")
        self.log(f"  Pick: {result['pick']}")
        self.log(f"  Place: {result['place']}")
        self.log(f"  Delay: {result['delay']}s")
        self.log(f"  Garra: {result['garra_accion']}")
    
    def set_zero_reference(self):
        """Establecer la posición actual como cero de referencia"""
        if not self.connected:
            self.log("⚠️ No conectado al robot")
            return
        
        if self.send_command("ZERO", pause=0.3):
            self.zero_set = True
            self.current_virtual_pos = [0.0, 0.0, 0.0, 0.0]
            self.update_zero_display()
            self.log("🎯 Cero de referencia establecido en posición actual")
            self.log("💡 Ahora los movimientos son relativos a esta posición")
        else:
            self.log("❌ No se pudo establecer cero de referencia")

    def update_zero_display(self):
        """Actualizar la visualización del estado del cero"""
        if self.zero_set:
            self.zero_label.configure(text="🎯 Cero: ESTABLECIDO", text_color="green")
        else:
            self.zero_label.configure(text="🎯 Cero: NO establecido", text_color="orange")
            
    def check_zero_before_move(self):
        """Verificar si el cero está establecido antes de mover"""
        if not self.zero_set:
            self.log("⚠️ ADVERTENCIA: Cero de referencia NO establecido")
            self.log("⚠️ Los movimientos pueden no ser precisos")
            response = messagebox.askyesno("Cero no establecido", 
                                         "El cero de referencia no está establecido.\n"
                                         "¿Desea establecerlo ahora?")
            if response:
                self.set_zero_reference()
                return False
            else:
                self.log("⚠️ Continuando sin cero establecido...")
        return True

    def update_virtual_position(self, motor_idx, delta_degrees):
        """Actualizar la posición virtual después de un movimiento"""
        if 0 <= motor_idx < 4:
            self.current_virtual_pos[motor_idx] += delta_degrees
            # Mantener en rango -180 a 180
            while self.current_virtual_pos[motor_idx] > 180.0:
                self.current_virtual_pos[motor_idx] -= 360.0
            while self.current_virtual_pos[motor_idx] < -180.0:
                self.current_virtual_pos[motor_idx] += 360.0

    def update_emergency_display(self):
        if self.emergency_stop_active:
            self.emergency_btn.configure(fg_color="#ff0000", hover_color="#cc0000", 
                                       text="⛔ PARO DE EMERGENCIA ACTIVADO")
            self.emergency_label.configure(text="🚨 SISTEMA EN PARO DE EMERGENCIA", 
                                         text_color="#ff0000")
            self.label_status.configure(text="Estado: PARO DE EMERGENCIA", 
                                      text_color="#ff0000")
        else:
            self.emergency_btn.configure(fg_color="#b71c1c", hover_color="#7f0000",
                                       text="🛑 PARO DE EMERGENCIA")
            self.emergency_label.configure(text="", text_color="gray")
            if self.connected:
                self.label_status.configure(text="Estado: Conectado", text_color="green")
            else:
                self.label_status.configure(text="Estado: Desconectado", text_color="red")

    def emergency_stop_immediate(self):
        if not self.connected:
            self.log("⚠️ No conectado al robot - No se puede activar paro de emergencia")
            return
        
        # Detener cualquier bucle en ejecución primero
        if self.ejecutando_bucle:
            self.ejecutando_bucle = False
            self.log("⏹️ Bucle detenido por emergencia")
            time.sleep(0.2)
        
        # Enviar comando de paro de emergencia inmediatamente
        success = self.send_command("STOP", pause=0.2)
        
        if success:
            self.emergency_stop_active = True
            self.update_emergency_display()
            
            self.log("⛔⛔⛔ PARO DE EMERGENCIA ACTIVADO INMEDIATAMENTE ⛔⛔⛔")
            self.log("⛔ Todas las comunicaciones han sido cortadas en el ESP32")
            self.log("⛔ Solo comandos RESET u ON serán aceptados")
            self.log("⛔ Para recuperar: Enviar RESET u ON (sin reconectar)")
        else:
            self.log("❌ No se pudo enviar paro de emergencia")

    def reset_system(self):
        if not self.connected:
            self.log("⚠️ No conectado al robot - Conecte primero")
            return
        
        # Detener cualquier bucle en ejecución
        if self.ejecutando_bucle:
            self.ejecutando_bucle = False
            time.sleep(0.2)
        
        if self.send_command("RESET", pause=0.3):
            self.emergency_stop_active = False
            self.zero_set = False
            self.current_virtual_pos = [0.0, 0.0, 0.0, 0.0]
            self.update_emergency_display()
            self.update_zero_display()
            self.update_bucle_display()
            self.log("🔄 RESET enviado - Sistema y cero reiniciados.")
        else:
            self.log("⚠️ RESET no enviado (sin conexión).")

    def toggle_terminal(self):
        if self.terminal_visible:
            self.terminal_frame.pack_forget()
            self.terminal_visible = False
            self.terminal_toggle_btn.configure(text="📟 ▼ Mostrar Terminal")
            self.log("🔧 Terminal ocultada")
        else:
            self.terminal_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
            self.terminal_visible = True
            self.terminal_toggle_btn.configure(text="📟 ▲ Ocultar Terminal")
            self.log("🔧 Terminal mostrada")
    
    def clear_terminal(self):
        self.text_terminal.configure(state="normal")
        self.text_terminal.delete("0.0", "end")
        self.text_terminal.configure(state="disabled")
        self.log("🧹 Terminal limpiada")

    def log(self, text):
        ts = time.strftime("%H:%M:%S")
        try:
            self.text_terminal.configure(state="normal")
            self.text_terminal.insert("end", f"[{ts}] {text}\n")
            self.text_terminal.see("end")
            self.text_terminal.configure(state="disabled")
        except Exception:
            print(f"[{ts}] {text}")

    def ejecutar_trayectoria(self):
        """Ejecutar movimiento coordinado con sistema de coordenadas virtuales"""
        if not self.connected:
            self.log("⚠️ No conectado al robot")
            return
        
        if self.emergency_stop_active:
            self.log("⛔ Sistema en paro de emergencia - Comando rechazado")
            return
            
        # Verificar cero establecido
        if not self.check_zero_before_move():
            return
            
        # Leer valores de los campos (PUEDEN SER NEGATIVOS)
        targets = []
        direcciones = ""
        
        for i, entry in enumerate(self.tray_entries):
            try:
                valor = float(entry.get())
                # VALIDACIÓN: Permitir valores entre -360 y 360
                if valor < -360 or valor > 360:
                    self.log(f"⚠️ Valor fuera de rango para M{i+1}: {valor}")
                    return
                targets.append(valor)
                
                # Obtener dirección para este motor
                dir_char = self.tray_dir_vars[i].get()
                direcciones += dir_char
                
                # Actualizar posición virtual estimada
                self.update_virtual_position(i, valor)
                
            except:
                self.log(f"⚠️ Valor inválido para M{i+1}")
                return
                
        try:
            velocidad = int(self.tray_vel_entry.get())
            velocidad = max(1, min(1000, velocidad))
        except:
            self.log("⚠️ Velocidad inválida para trayectoria")
            return
            
        estado_garra = self.tray_garra_var.get()
        
        # Construir comando: TRAY:10,-10,20,-20,HHAA,500,ABRIR
        comando = f"TRAY:{targets[0]},{targets[1]},{targets[2]},{targets[3]},{direcciones},{velocidad},{estado_garra}"
        
        if self.send_command(comando):
            self.log(f"🔄 Enviada trayectoria coordinada: {targets} dirs:{direcciones} vel:{velocidad} garra:{estado_garra}")
            self.log("💡 Sistema de coordenadas virtuales activo")
            
            # Mostrar posiciones virtuales estimadas
            self.log("📊 Posiciones virtuales estimadas después del movimiento:")
            for i in range(4):
                self.log(f"  M{i+1}: {self.current_virtual_pos[i]:.1f}°")
        else:
            # Revertir posiciones virtuales si falló
            for i in range(4):
                self.update_virtual_position(i, -targets[i])

    def cargar_posicion_rapida(self, posiciones, direcciones):
        """Cargar posición rápida en los campos de trayectoria (con valores negativos)"""
        for i, pos in enumerate(posiciones):
            if i < len(self.tray_entries):
                self.tray_entries[i].delete(0, "end")
                self.tray_entries[i].insert(0, str(pos))
                
            if i < len(self.tray_dir_vars):
                self.tray_dir_vars[i].set(direcciones[i])
                
        self.log(f"📥 Cargada posición rápida: {posiciones} dirs:{direcciones}")

    def update_wifi_info(self):
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
        self.update_emergency_display()

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
            self.emergency_stop_active = False
            self.zero_set = False
            self.ejecutando_bucle = False
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
            self.emergency_stop_active = False
            self.zero_set = False
            self.ejecutando_bucle = False
            self.label_status.configure(text=f"Conectado (Wi-Fi {ip}:{port})", text_color="green")
            self.log(f"🌐 Conectado a {ip}:{port} (Wi-Fi).")
            self.stop_thread = False
            
            threading.Thread(target=self.read_wifi_fast, daemon=True).start()
            self.update_wifi_info()
            
        except Exception as e:
            self.log(f"❌ Error al conectar Wi-Fi: {e}")

    def disconnect(self):
        # Detener cualquier bucle en ejecución
        if self.ejecutando_bucle:
            self.ejecutando_bucle = False
            time.sleep(0.3)
            
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
        self.emergency_stop_active = False
        self.zero_set = False
        self.ejecutando_bucle = False
        self.label_status.configure(text="Estado: Desconectado", text_color="red")
        self.update_wifi_info()
        self.update_emergency_display()
        self.update_zero_display()
        self.update_bucle_display()
        self.log("🔴 Desconectado.")

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
                            if "PARO DE EMERGENCIA ACTIVADO" in line or "EMERGENCY STOP ACTIVATED" in line:
                                self.emergency_stop_active = True
                                self.update_emergency_display()
                            if "RESET completado" in line or "ON recibido" in line or "Sistema recuperado" in line:
                                self.emergency_stop_active = False
                                self.update_emergency_display()
                            if "Cero referencia establecido" in line or "Cero de referencia establecido" in line:
                                self.zero_set = True
                                self.update_zero_display()
                                self.current_virtual_pos = [0.0, 0.0, 0.0, 0.0]
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
                            if "PARO DE EMERGENCIA ACTIVADO" in line or "EMERGENCY STOP ACTIVATED" in line:
                                self.emergency_stop_active = True
                                self.update_emergency_display()
                            if "RESET completado" in line or "ON recibido" in line or "Sistema recuperado" in line:
                                self.emergency_stop_active = False
                                self.update_emergency_display()
                            if "Cero referencia establecido" in line or "Cero de referencia establecido" in line:
                                self.zero_set = True
                                self.update_zero_display()
                                self.current_virtual_pos = [0.0, 0.0, 0.0, 0.0]
            except socket.timeout:
                continue
            except Exception:
                break

    def send_command(self, cmd, pause=None):
        if pause is None:
            pause = self.command_delay
            
        if self.emergency_stop_active and cmd.upper() not in ["RESET", "ON", "STOP", "ESTOP", "E-STOP", "EMERGENCY", "ZERO", "SETZERO"]:
            self.log(f"⛔ Sistema en paro de emergencia - Comando '{cmd}' rechazado")
            return False
            
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

    def direct_move(self, direction):
        if self.emergency_stop_active:
            self.log("⛔ Sistema en paro de emergencia - Movimiento rechazado")
            return
            
        # Verificar cero establecido
        if not self.check_zero_before_move():
            return
            
        motor = self.direct_motor_var.get()
        pasos = self.entry_steps.get()
        vel = self.entry_vel_direct.get()
        try:
            pasos_i = int(pasos)
            vel_i = int(vel)
            vel_i = max(1, min(1000, vel_i))
        except:
            self.log("⚠️ Pasos/vel inválidos.")
            return
            
        # Calcular grados aproximados movidos
        grados_aproximados = (pasos_i / 6600.0) * 360.0
        if direction == "A":
            grados_aproximados = -grados_aproximados
            
        # Actualizar posición virtual estimada
        motor_idx = int(motor[1]) - 1  # "M1" -> 0, "M2" -> 1, etc.
        self.update_virtual_position(motor_idx, grados_aproximados)
            
        if motor == "M5":
            estado = self.garra_state_var.get()
            if estado not in ["ABRIR", "CERRAR"]:
                estado = "ABRIR"
            self.send_command(estado)
        else:
            dir_char = "H" if direction == "H" else "A"
            cmd = f"{motor},{dir_char},{pasos_i},{vel_i}"
            self.send_command(cmd)
            
            # Mostrar posición virtual estimada
            self.log(f"📊 Posición virtual estimada M{motor_idx+1}: {self.current_virtual_pos[motor_idx]:.1f}°")

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

    # ==================== FUNCIONES PARA SISTEMA DE TRAYECTORIAS ====================
    
    def load_trayectorias_file(self):
        """Cargar trayectorias desde archivo"""
        if os.path.exists(TRAYECTORIAS_FILE):
            try:
                with open(TRAYECTORIAS_FILE, "r") as f:
                    self.trayectorias = json.load(f)
            except Exception:
                self.trayectorias = {}
        else:
            # Trayectorias por defecto
            self.trayectorias = {
                "Inicio": {
                    "pos": [0, 0, 0, 0],
                    "dirs": "HHHH", 
                    "vel": 500,
                    "garra": "ABRIR"
                },
                "Test Positivo": {
                    "pos": [45, -45, 30, -30],
                    "dirs": "HAHA",
                    "vel": 400,
                    "garra": "ABRIR"
                },
                "Posición Extendida": {
                    "pos": [180, 135, 90, 45],
                    "dirs": "HHHH",
                    "vel": 300,
                    "garra": "ABRIR"
                },
                "Movimiento Alternado": {
                    "pos": [90, -90, 60, -60],
                    "dirs": "HAHA",
                    "vel": 350,
                    "garra": "CERRAR"
                }
            }
            self.save_trayectorias_file()
    
    def update_trayectorias_info(self):
        """Actualizar información de trayectorias guardadas"""
        if not hasattr(self, 'tray_info_label') or self.tray_info_label is None:
            return
            
        tray_name = self.tray_var.get() if hasattr(self, 'tray_var') else ""
        if tray_name in self.trayectorias:
            tray = self.trayectorias[tray_name]
            
            # Verificar si es una secuencia combinada
            if tray.get("tipo") == "combinada":
                info_text = f"🔗 SECUENCIA COMBINADA: {tray.get('descripcion', tray_name)}"
                info_text += f"\n  Pick: {tray.get('pick', 'N/A')}"
                info_text += f"  |  Place: {tray.get('place', 'N/A')}"
                info_text += f"\n  Delay: {tray.get('delay', 0)}s"
                info_text += f"  |  Garra: {tray.get('garra_accion', 'NO CAMBIAR')}"
            else:
                info_text = f"📊 {tray_name}: Pos={tray['pos']}, Dir={tray['dirs']}, Vel={tray['vel']}, Garra={tray['garra']}"
                info_text = info_text[:80] + "..." if len(info_text) > 80 else info_text
            
            self.tray_info_label.configure(text=info_text)
        else:
            self.tray_info_label.configure(text="")
    
    def cargar_trayectoria_selected(self):
        """Cargar trayectoria seleccionada desde el menú"""
        self.cargar_trayectoria(self.tray_var.get())
    
    def save_trayectorias_file(self):
        """Guardar trayectorias en archivo"""
        try:
            with open(TRAYECTORIAS_FILE, "w") as f:
                json.dump(self.trayectorias, f, indent=2)
        except Exception as e:
            self.log(f"❌ Error al guardar trayectorias: {e}")

    def save_trayectoria(self):
        """Guardar trayectoria actual"""
        name = simpledialog.askstring("Nombre trayectoria", "Introduce un nombre para la trayectoria:", parent=self)
        if not name:
            self.log("⚠️ Guardado cancelado.")
            return
            
        try:
            # Leer posiciones (pueden ser negativas)
            posiciones = []
            for entry in self.tray_entries:
                valor = float(entry.get())
                if valor < -360 or valor > 360:
                    self.log("⚠️ Valores fuera de rango (-360° a 360°)")
                    return
                posiciones.append(valor)
                
            # Leer direcciones
            direcciones = ""
            for dir_var in self.tray_dir_vars:
                direcciones += dir_var.get()
                
            # Leer velocidad y garra
            velocidad = int(self.tray_vel_entry.get())
            velocidad = max(1, min(1000, velocidad))
            estado_garra = self.tray_garra_var.get()
            
        except Exception:
            self.log("⚠️ Valores inválidos al guardar trayectoria.")
            return
            
        # Guardar trayectoria
        self.trayectorias[name] = {
            "pos": posiciones,
            "dirs": direcciones,
            "vel": velocidad,
            "garra": estado_garra
        }
        
        self.save_trayectorias_file()
        
        # Actualizar dropdown si ya existe
        if hasattr(self, 'tray_menu') and self.tray_menu:
            tray_keys = list(self.trayectorias.keys())
            self.tray_menu.configure(values=tray_keys)
            self.tray_var.set(name)
            self.update_trayectorias_info()
        
        self.log(f"💾 Trayectoria '{name}' guardada:")
        self.log(f"  Posiciones: {posiciones}")
        self.log(f"  Direcciones: {direcciones}")
        self.log(f"  Velocidad: {velocidad}")
        self.log(f"  Garra: {estado_garra}")

    def cargar_trayectoria(self, nombre):
        """Cargar trayectoria o secuencia seleccionada"""
        if nombre in self.trayectorias:
            tray = self.trayectorias[nombre]
            
            # Verificar si es una secuencia combinada
            if tray.get("tipo") == "combinada":
                # Mostrar información de la secuencia combinada
                info_text = f"🔗 SECUENCIA COMBINADA: {tray.get('descripcion', nombre)}"
                info_text += f"\n  Pick: {tray.get('pick', 'N/A')}"
                info_text += f"  |  Place: {tray.get('place', 'N/A')}"
                info_text += f"\n  Delay: {tray.get('delay', 0)}s"
                info_text += f"  |  Garra: {tray.get('garra_accion', 'NO CAMBIAR')}"
                
                self.tray_info_label.configure(text=info_text)
                self.log(f"📥 Cargada secuencia combinada: {nombre}")
                return
            
            # Cargar trayectoria normal
            posiciones = tray.get("pos", [0, 0, 0, 0])
            
            for i, pos in enumerate(posiciones):
                if i < len(self.tray_entries):
                    self.tray_entries[i].delete(0, "end")
                    self.tray_entries[i].insert(0, str(pos))
            
            if "dirs" in tray:
                for i, dir_char in enumerate(tray["dirs"]):
                    if i < len(self.tray_dir_vars):
                        self.tray_dir_vars[i].set(dir_char)
            
            if "vel" in tray:
                self.tray_vel_entry.delete(0, "end")
                self.tray_vel_entry.insert(0, str(tray["vel"]))
            
            if "garra" in tray:
                self.tray_garra_var.set(tray["garra"])
            
            self.update_trayectorias_info()
            self.log(f"📥 Cargada trayectoria: {nombre}")

    def delete_trayectoria(self):
        """Eliminar trayectoria seleccionada"""
        key = self.tray_var.get()
        if not key or key not in self.trayectorias:
            self.log("⚠️ Selecciona una trayectoria válida para eliminar.")
            return
            
        if key == "Inicio":
            messagebox.showwarning("No eliminar", "No se puede eliminar la trayectoria 'Inicio'")
            return
            
        confirm = messagebox.askyesno("Eliminar trayectoria", f"¿Eliminar la trayectoria '{key}'?")
        if not confirm:
            return
            
        del self.trayectorias[key]
        self.save_trayectorias_file()
        
        if hasattr(self, 'tray_menu') and self.tray_menu:
            tray_keys = list(self.trayectorias.keys())
            self.tray_menu.configure(values=tray_keys)
            if tray_keys:
                self.tray_var.set(tray_keys[0])
            self.update_trayectorias_info()
        
        self.log(f"🗑️ Trayectoria '{key}' eliminada.")

    def on_close(self):
        self.disconnect()
        self.destroy()

if __name__ == "__main__":
    app = CobotApp()
    app.mainloop()
