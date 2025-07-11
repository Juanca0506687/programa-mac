import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from datetime import datetime
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import letter
import os

# --- BASE DE DATOS ---
conn = sqlite3.connect("inventario_cuba.db")
cursor = conn.cursor()

# Crear tablas
cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT UNIQUE,
    password TEXT,
    rol TEXT CHECK(rol IN ('admin','vendedor'))
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT,
    cantidad INTEGER,
    precio REAL,
    moneda TEXT CHECK(moneda IN ('USD','CUP')),
    imagen TEXT,
    stock_minimo INTEGER DEFAULT 5
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ventas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id INTEGER,
    cantidad INTEGER,
    total REAL,
    fecha TEXT,
    cliente_nombre TEXT,
    cliente_ci TEXT,
    cliente_dir TEXT,
    usuario_id INTEGER,
    FOREIGN KEY(producto_id) REFERENCES productos(id),
    FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS configuracion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_cambio REAL
)
""")

conn.commit()

# Crear usuario admin por defecto si no existe
cursor.execute("SELECT * FROM usuarios WHERE usuario='admin'")
if not cursor.fetchone():
    cursor.execute("INSERT INTO usuarios (usuario, password, rol) VALUES (?, ?, ?)", ("admin", "admin123", "admin"))
    conn.commit()

# Crear config tipo cambio si no existe
cursor.execute("SELECT * FROM configuracion")
if not cursor.fetchone():
    cursor.execute("INSERT INTO configuracion (tipo_cambio) VALUES (?)", (24.0,))
    conn.commit()

# --- Variables globales ---
usuario_actual = None

def get_tipo_cambio():
    cursor.execute("SELECT tipo_cambio FROM configuracion LIMIT 1")
    r = cursor.fetchone()
    return r[0] if r else 24.0

def set_tipo_cambio(nuevo):
    cursor.execute("UPDATE configuracion SET tipo_cambio = ?", (nuevo,))
    conn.commit()

# --- VENTANA PRINCIPAL ---
app = tk.Tk()
app.title("Sistema Completo de Inventario Cuba")
app.geometry("950x700")
app.configure(bg="#f0f0f0")

# --- FRAMES ---
frames = {}
for name in ["login", "menu", "productos", "agregar_producto", "editar_producto", "vender", "historial", "reportes", "config"]:
    f = tk.Frame(app)
    frames[name] = f
    f.place(relwidth=1, relheight=1)

def ocultar_frames():
    for f in frames.values():
        f.place_forget()

# --- LOGIN ---
def login():
    global usuario_actual
    user = entry_usuario.get().strip()
    pwd = entry_password.get().strip()
    if not user or not pwd:
        messagebox.showerror("Error", "Ingrese usuario y contraseña")
        return
    cursor.execute("SELECT id, usuario, rol FROM usuarios WHERE usuario=? AND password=?", (user, pwd))
    r = cursor.fetchone()
    if r:
        usuario_actual = {"id": r[0], "usuario": r[1], "rol": r[2]}
        messagebox.showinfo("Bienvenido", f"Bienvenido {usuario_actual['usuario']} ({usuario_actual['rol']})")
        mostrar_menu()
    else:
        messagebox.showerror("Error", "Usuario o contraseña incorrectos")

login_frame = frames["login"]
tk.Label(login_frame, text="Login", font=("Arial", 24)).pack(pady=40)
tk.Label(login_frame, text="Usuario").pack()
entry_usuario = tk.Entry(login_frame)
entry_usuario.pack(pady=5)
tk.Label(login_frame, text="Contraseña").pack()
entry_password = tk.Entry(login_frame, show="*")
entry_password.pack(pady=5)
tk.Button(login_frame, text="Entrar", command=login, bg="#4CAF50", fg="white").pack(pady=15)

def mostrar_login():
    ocultar_frames()
    frames["login"].place(relwidth=1, relheight=1)

# --- MENÚ PRINCIPAL ---
menu_frame = frames["menu"]

label_usuario = tk.Label(menu_frame, text="", font=("Arial", 12))
label_usuario.pack(anchor="ne", padx=10, pady=5)

tk.Label(menu_frame, text="Menú Principal", font=("Arial", 24)).pack(pady=40)

btn_productos = tk.Button(menu_frame, text="Gestionar Productos", width=30, height=2)
btn_vender = tk.Button(menu_frame, text="Vender Producto", width=30, height=2)
btn_historial = tk.Button(menu_frame, text="Historial de Ventas", width=30, height=2)
btn_reportes = tk.Button(menu_frame, text="Reportes", width=30, height=2)
btn_config = tk.Button(menu_frame, text="Configuración", width=30, height=2)
btn_salir = tk.Button(menu_frame, text="Cerrar Sesión", width=30, height=2, bg="#f44336", fg="white")

btn_productos.pack(pady=10)
btn_vender.pack(pady=10)
btn_historial.pack(pady=10)
btn_reportes.pack(pady=10)
btn_salir.pack(pady=30)

alerta_label = tk.Label(menu_frame, text="", fg="red", font=("Arial", 12, "bold"))
alerta_label.pack(pady=5)

def mostrar_alertas_stock():
    cursor.execute("SELECT nombre, cantidad, stock_minimo FROM productos WHERE cantidad <= stock_minimo")
    bajos = cursor.fetchall()
    if bajos:
        texto = "¡Atención! Productos con stock bajo:\n"
        texto += "\n".join([f"{p[0]} (Stock: {p[1]})" for p in bajos])
        alerta_label.config(text=texto)
    else:
        alerta_label.config(text="")

def mostrar_menu():
    ocultar_frames()
    frames["menu"].place(relwidth=1, relheight=1)
    label_usuario.config(text=f"Usuario: {usuario_actual['usuario']} ({usuario_actual['rol']})")
    mostrar_alertas_stock()
    # Mostrar u ocultar botón config según rol
    if usuario_actual["rol"] == "admin":
        btn_config.pack(pady=10)
    else:
        btn_config.pack_forget()

def cerrar_sesion():
    global usuario_actual
    usuario_actual = None
    mostrar_login()

btn_salir.config(command=cerrar_sesion)

# --- GESTIÓN DE PRODUCTOS ---
productos_frame = frames["productos"]

tree_productos = None

def mostrar_productos():
    ocultar_frames()
    f = frames["productos"]
    f.place(relwidth=1, relheight=1)
    for widget in f.winfo_children():
        widget.destroy()

    tk.Label(f, text="Productos", font=("Arial", 20)).pack(pady=10)

    busq_frame = tk.Frame(f)
    busq_frame.pack()
    tk.Label(busq_frame, text="Buscar:").pack(side="left")
    entry_buscar = tk.Entry(busq_frame)
    entry_buscar.pack(side="left", padx=5)

    columnas = ("ID", "Nombre", "Cantidad", "Precio", "Moneda", "Stock mínimo", "Imagen")
    global tree_productos
    tree_productos = ttk.Treeview(f, columns=columnas, show="headings", height=15)
    for col in columnas:
        tree_productos.heading(col, text=col)
        if col == "Imagen":
            tree_productos.column(col, width=150)
        else:
            tree_productos.column(col, width=100)
    tree_productos.pack(pady=10)

    btn_frame = tk.Frame(f)
    btn_frame.pack()
    tk.Button(btn_frame, text="Agregar Producto", command=mostrar_agregar_producto, bg="#4CAF50", fg="white").pack(side="left", padx=5)
    tk.Button(btn_frame, text="Editar Producto", command=editar_producto_seleccionado).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Eliminar Producto", command=eliminar_producto_seleccionado).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Volver al Menú", command=mostrar_menu).pack(side="left", padx=5)

    def filtrar(event=None):
        cargar_productos(entry_buscar.get())

    entry_buscar.bind("<KeyRelease>", filtrar)

    cargar_productos()

def cargar_productos(filtro=""):
    for i in tree_productos.get_children():
        tree_productos.delete(i)
    filtro_like = f"%{filtro}%"
    cursor.execute("SELECT id, nombre, cantidad, precio, moneda, stock_minimo, imagen FROM productos WHERE nombre LIKE ?", (filtro_like,))
    productos = cursor.fetchall()
    for p in productos:
        tree_productos.insert("", "end", values=p)

def mostrar_agregar_producto():
    ocultar_frames()
    f = frames["agregar_producto"]
    f.place(relwidth=1, relheight=1)
    for widget in f.winfo_children():
        widget.destroy()

    tk.Label(f, text="Agregar Producto", font=("Arial", 20)).pack(pady=20)
    form_frame = tk.Frame(f)
    form_frame.pack()

    tk.Label(form_frame, text="Nombre:").grid(row=0, column=0, sticky="e")
    entry_nombre = tk.Entry(form_frame, width=50)
    entry_nombre.grid(row=0, column=1, pady=5)

    tk.Label(form_frame, text="Cantidad:").grid(row=1, column=0, sticky="e")
    entry_cantidad = tk.Entry(form_frame, width=50)
    entry_cantidad.grid(row=1, column=1, pady=5)

    tk.Label(form_frame, text="Precio:").grid(row=2, column=0, sticky="e")
    entry_precio = tk.Entry(form_frame, width=50)
    entry_precio.grid(row=2, column=1, pady=5)

    tk.Label(form_frame, text="Moneda:").grid(row=3, column=0, sticky="e")
    combo_moneda = ttk.Combobox(form_frame, values=["USD","CUP"], state="readonly", width=47)
    combo_moneda.current(0)
    combo_moneda.grid(row=3, column=1, pady=5)

    tk.Label(form_frame, text="Stock mínimo:").grid(row=4, column=0, sticky="e")
    entry_stock_min = tk.Entry(form_frame, width=50)
    entry_stock_min.insert(0, "5")
    entry_stock_min.grid(row=4, column=1, pady=5)

    tk.Label(form_frame, text="Imagen (ruta):").grid(row=5, column=0, sticky="e")
    entry_imagen = tk.Entry(form_frame, width=50)
    entry_imagen.grid(row=5, column=1, pady=5)

    def seleccionar_imagen():
        archivo = filedialog.askopenfilename(filetypes=[("Imagenes", "*.jpg *.jpeg *.png *.gif")])
        if archivo:
            entry_imagen.delete(0, tk.END)
            entry_imagen.insert(0, archivo)
    tk.Button(form_frame, text="Seleccionar Imagen", command=seleccionar_imagen).grid(row=5, column=2, padx=5)

    def guardar():
        nombre = entry_nombre.get().strip()
        try:
            cantidad = int(entry_cantidad.get().strip())
            precio = float(entry_precio.get().strip())
            stock_min = int(entry_stock_min.get().strip())
        except:
            messagebox.showerror("Error", "Cantidad, Precio y Stock mínimo deben ser numéricos")
            return
        moneda = combo_moneda.get()
        imagen = entry_imagen.get().strip()
        if not nombre:
            messagebox.showerror("Error", "El nombre es obligatorio")
            return
        cursor.execute("INSERT INTO productos (nombre, cantidad, precio, moneda, imagen, stock_minimo) VALUES (?, ?, ?, ?, ?, ?)",
                       (nombre, cantidad, precio, moneda, imagen, stock_min))
        conn.commit()
        messagebox.showinfo("Éxito", "Producto agregado correctamente")
        mostrar_productos()

    tk.Button(f, text="Guardar", command=guardar, bg="#4CAF50", fg="white").pack(pady=15)
    tk.Button(f, text="Volver", command=mostrar_productos).pack()

# --- Editar producto ---
editar_producto_data = {}

def editar_producto_seleccionado():
    sel = tree_productos.selection()
    if not sel:
        messagebox.showerror("Error", "Seleccione un producto para editar")
        return
    item = tree_productos.item(sel[0])
    datos = item["values"]
    if not datos:
        return
    producto_id = datos[0]
    cursor.execute("SELECT nombre, cantidad, precio, moneda, imagen, stock_minimo FROM productos WHERE id=?", (producto_id,))
    p = cursor.fetchone()
    if not p:
        messagebox.showerror("Error", "Producto no encontrado")
        return
    editar_producto_data["id"] = producto_id
    mostrar_editar_producto(p)

def mostrar_editar_producto(p):
    ocultar_frames()
    f = frames["editar_producto"]
    f.place(relwidth=1, relheight=1)
    for widget in f.winfo_children():
        widget.destroy()

    tk.Label(f, text="Editar Producto", font=("Arial", 20)).pack(pady=20)
    form_frame = tk.Frame(f)
    form_frame.pack()

    tk.Label(form_frame, text="Nombre:").grid(row=0, column=0, sticky="e")
    entry_nombre = tk.Entry(form_frame, width=50)
    entry_nombre.insert(0, p[0])
    entry_nombre.grid(row=0, column=1, pady=5)

    tk.Label(form_frame, text="Cantidad:").grid(row=1, column=0, sticky="e")
    entry_cantidad = tk.Entry(form_frame, width=50)
    entry_cantidad.insert(0, p[1])
    entry_cantidad.grid(row=1, column=1, pady=5)

    tk.Label(form_frame, text="Precio:").grid(row=2, column=0, sticky="e")
    entry_precio = tk.Entry(form_frame, width=50)
    entry_precio.insert(0, p[2])
    entry_precio.grid(row=2, column=1, pady=5)

    tk.Label(form_frame, text="Moneda:").grid(row=3, column=0, sticky="e")
    combo_moneda = ttk.Combobox(form_frame, values=["USD","CUP"], state="readonly", width=47)
    combo_moneda.set(p[3])
    combo_moneda.grid(row=3, column=1, pady=5)

    tk.Label(form_frame, text="Stock mínimo:").grid(row=4, column=0, sticky="e")
    entry_stock_min = tk.Entry(form_frame, width=50)
    entry_stock_min.insert(0, p[5])
    entry_stock_min.grid(row=4, column=1, pady=5)

    tk.Label(form_frame, text="Imagen (ruta):").grid(row=5, column=0, sticky="e")
    entry_imagen = tk.Entry(form_frame, width=50)
    entry_imagen.insert(0, p[4])
    entry_imagen.grid(row=5, column=1, pady=5)

    def seleccionar_imagen():
        archivo = filedialog.askopenfilename(filetypes=[("Imagenes", "*.jpg *.jpeg *.png *.gif")])
        if archivo:
            entry_imagen.delete(0, tk.END)
            entry_imagen.insert(0, archivo)
    tk.Button(form_frame, text="Seleccionar Imagen", command=seleccionar_imagen).grid(row=5, column=2, padx=5)

    def guardar():
        nombre = entry_nombre.get().strip()
        try:
            cantidad = int(entry_cantidad.get().strip())
            precio = float(entry_precio.get().strip())
            stock_min = int(entry_stock_min.get().strip())
        except:
            messagebox.showerror("Error", "Cantidad, Precio y Stock mínimo deben ser numéricos")
            return
        moneda = combo_moneda.get()
        imagen = entry_imagen.get().strip()
        if not nombre:
            messagebox.showerror("Error", "El nombre es obligatorio")
            return
        cursor.execute("""
            UPDATE productos SET nombre=?, cantidad=?, precio=?, moneda=?, imagen=?, stock_minimo=? WHERE id=?
        """, (nombre, cantidad, precio, moneda, imagen, stock_min, editar_producto_data["id"]))
        conn.commit()
        messagebox.showinfo("Éxito", "Producto actualizado correctamente")
        mostrar_productos()

    tk.Button(f, text="Guardar Cambios", command=guardar, bg="#2196F3", fg="white").pack(pady=15)
    tk.Button(f, text="Volver", command=mostrar_productos).pack()

# --- Eliminar producto ---
def eliminar_producto_seleccionado():
    sel = tree_productos.selection()
    if not sel:
        messagebox.showerror("Error", "Seleccione un producto para eliminar")
        return
    item = tree_productos.item(sel[0])
    datos = item["values"]
    if not datos:
        return
    producto_id = datos[0]
    confirmar = messagebox.askyesno("Confirmar", f"¿Seguro que desea eliminar el producto {datos[1]}?")
    if confirmar:
        cursor.execute("DELETE FROM productos WHERE id=?", (producto_id,))
        conn.commit()
        messagebox.showinfo("Éxito", "Producto eliminado")
        mostrar_productos()

# --- VENDER PRODUCTO ---
vender_frame = frames["vender"]

def mostrar_vender():
    ocultar_frames()
    f = frames["vender"]
    f.place(relwidth=1, relheight=1)
    for widget in f.winfo_children():
        widget.destroy()

    tk.Label(f, text="Realizar Venta", font=("Arial", 24)).pack(pady=10)

    form_frame = tk.Frame(f)
    form_frame.pack(pady=5)

    tk.Label(form_frame, text="Producto:").grid(row=0, column=0, sticky="e")
    combo_productos = ttk.Combobox(form_frame, state="readonly", width=50)
    combo_productos.grid(row=0, column=1, pady=5)

    tk.Label(form_frame, text="Cantidad:").grid(row=1, column=0, sticky="e")
    entry_cantidad = tk.Entry(form_frame)
    entry_cantidad.grid(row=1, column=1, pady=5)

    tk.Label(form_frame, text="Cliente Nombre:").grid(row=2, column=0, sticky="e")
    entry_cliente_nombre = tk.Entry(form_frame)
    entry_cliente_nombre.grid(row=2, column=1, pady=5)

    tk.Label(form_frame, text="Cliente CI:").grid(row=3, column=0, sticky="e")
    entry_cliente_ci = tk.Entry(form_frame)
    entry_cliente_ci.grid(row=3, column=1, pady=5)

    tk.Label(form_frame, text="Cliente Dirección:").grid(row=4, column=0, sticky="e")
    entry_cliente_dir = tk.Entry(form_frame)
    entry_cliente_dir.grid(row=4, column=1, pady=5)

    # Mostrar total
    label_total = tk.Label(f, text="Total: 0.00", font=("Arial", 14))
    label_total.pack(pady=5)

    # Cargar productos al combobox
    cursor.execute("SELECT id, nombre, precio, moneda FROM productos")
    lista_productos = cursor.fetchall()
    productos_map = {f"{p[1]} (Precio: {p[2]} {p[3]})": p for p in lista_productos}
    combo_productos["values"] = list(productos_map.keys())

    def actualizar_total(event=None):
        sel = combo_productos.get()
        if sel and sel in productos_map:
            try:
                cant = int(entry_cantidad.get())
                if cant < 1:
                    label_total.config(text="Cantidad debe ser >= 1")
                    return
            except:
                label_total.config(text="Cantidad inválida")
                return
            p = productos_map[sel]
            total = cant * p[2]
            label_total.config(text=f"Total: {total:.2f} {p[3]}")
        else:
            label_total.config(text="Total: 0.00")

    combo_productos.bind("<<ComboboxSelected>>", actualizar_total)
    entry_cantidad.bind("<KeyRelease>", actualizar_total)

    def realizar_venta():
        sel = combo_productos.get()
        if not sel or sel not in productos_map:
            messagebox.showerror("Error", "Seleccione un producto")
            return
        try:
            cant = int(entry_cantidad.get())
            if cant < 1:
                raise ValueError()
        except:
            messagebox.showerror("Error", "Cantidad inválida")
            return

        p = productos_map[sel]
        cursor.execute("SELECT cantidad FROM productos WHERE id=?", (p[0],))
        stock_actual = cursor.fetchone()[0]
        if cant > stock_actual:
            messagebox.showerror("Error", f"No hay suficiente stock. Disponible: {stock_actual}")
            return

        total = cant * p[2]

        cliente_nombre = entry_cliente_nombre.get().strip()
        cliente_ci = entry_cliente_ci.get().strip()
        cliente_dir = entry_cliente_dir.get().strip()

        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Actualizar stock
        nuevo_stock = stock_actual - cant
        cursor.execute("UPDATE productos SET cantidad=? WHERE id=?", (nuevo_stock, p[0]))
        # Guardar venta
        cursor.execute("""
            INSERT INTO ventas (producto_id, cantidad, total, fecha, cliente_nombre, cliente_ci, cliente_dir, usuario_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (p[0], cant, total, fecha, cliente_nombre, cliente_ci, cliente_dir, usuario_actual["id"]))
        conn.commit()

        messagebox.showinfo("Venta", f"Venta realizada con éxito. Total: {total:.2f} {p[3]}")
        mostrar_menu()

    tk.Button(f, text="Realizar Venta", command=realizar_venta, bg="#4CAF50", fg="white").pack(pady=10)
    tk.Button(f, text="Volver al Menú", command=mostrar_menu).pack()

# --- HISTORIAL DE VENTAS ---
historial_frame = frames["historial"]

tree_ventas = None

def mostrar_historial():
    ocultar_frames()
    f = frames["historial"]
    f.place(relwidth=1, relheight=1)
    for widget in f.winfo_children():
        widget.destroy()

    tk.Label(f, text="Historial de Ventas", font=("Arial", 20)).pack(pady=10)

    filtro_frame = tk.Frame(f)
    filtro_frame.pack(pady=5)

    tk.Label(filtro_frame, text="Buscar producto:").pack(side="left")
    entry_buscar = tk.Entry(filtro_frame)
    entry_buscar.pack(side="left", padx=5)

    tk.Label(filtro_frame, text="Fecha Desde (YYYY-MM-DD):").pack(side="left")
    entry_fecha_desde = tk.Entry(filtro_frame, width=12)
    entry_fecha_desde.pack(side="left", padx=5)

    tk.Label(filtro_frame, text="Fecha Hasta (YYYY-MM-DD):").pack(side="left")
    entry_fecha_hasta = tk.Entry(filtro_frame, width=12)
    entry_fecha_hasta.pack(side="left", padx=5)

    columnas = ("ID Venta", "Producto", "Cantidad", "Total", "Fecha", "Cliente", "CI", "Dirección", "Vendedor")
    global tree_ventas
    tree_ventas = ttk.Treeview(f, columns=columnas, show="headings", height=15)
    for col in columnas:
        tree_ventas.heading(col, text=col)
        tree_ventas.column(col, width=110)
    tree_ventas.pack(pady=10)

    btn_frame = tk.Frame(f)
    btn_frame.pack()

    def cargar_ventas():
        producto_filtro = entry_buscar.get().strip()
        fecha_desde = entry_fecha_desde.get().strip()
        fecha_hasta = entry_fecha_hasta.get().strip()

        query = """
        SELECT v.id, p.nombre, v.cantidad, v.total, v.fecha, v.cliente_nombre, v.cliente_ci, v.cliente_dir, u.usuario
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        JOIN usuarios u ON v.usuario_id = u.id
        WHERE 1=1
        """
        params = []

        if producto_filtro:
            query += " AND p.nombre LIKE ?"
            params.append(f"%{producto_filtro}%")
        if fecha_desde:
            query += " AND v.fecha >= ?"
            params.append(fecha_desde + " 00:00:00")
        if fecha_hasta:
            query += " AND v.fecha <= ?"
            params.append(fecha_hasta + " 23:59:59")

        query += " ORDER BY v.fecha DESC"

        for i in tree_ventas.get_children():
            tree_ventas.delete(i)
        cursor.execute(query, params)
        filas = cursor.fetchall()
        for row in filas:
            tree_ventas.insert("", "end", values=row)

    tk.Button(btn_frame, text="Buscar", command=cargar_ventas).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Exportar PDF", command=lambda: exportar_pdf_ventas()).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Volver al Menú", command=mostrar_menu).pack(side="left", padx=5)

    cargar_ventas()

def exportar_pdf_ventas():
    if not tree_ventas.get_children():
        messagebox.showwarning("Advertencia", "No hay ventas para exportar")
        return
    file = filedialog.asksaveasfilename(defaultextension=".pdf",
                                        filetypes=[("PDF files", "*.pdf")],
                                        title="Guardar reporte de ventas")
    if not file:
        return

    c = pdf_canvas.Canvas(file, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 40, "Reporte de Ventas")
    c.setFont("Helvetica", 10)
    y = height - 70

    columnas = ("ID Venta", "Producto", "Cantidad", "Total", "Fecha", "Cliente", "CI", "Dirección", "Vendedor")
    ancho_col = (width - 80) / len(columnas)
    for idx, col in enumerate(columnas):
        c.drawString(40 + idx * ancho_col, y, col)
    y -= 20

    for item in tree_ventas.get_children():
        if y < 40:
            c.showPage()
            y = height - 40
        vals = tree_ventas.item(item)["values"]
        for idx, val in enumerate(vals):
            txt = str(val)
            if len(txt) > 15:
                txt = txt[:12] + "..."
            c.drawString(40 + idx * ancho_col, y, txt)
        y -= 15

    c.save()
    messagebox.showinfo("Exportación", "Reporte PDF generado con éxito")

# --- REPORTES SIMPLES ---
reportes_frame = frames["reportes"]

def mostrar_reportes():
    ocultar_frames()
    f = frames["reportes"]
    f.place(relwidth=1, relheight=1)
    for widget in f.winfo_children():
        widget.destroy()

    tk.Label(f, text="Reportes", font=("Arial", 20)).pack(pady=20)

    # Total ventas hoy
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT SUM(total) FROM ventas WHERE fecha LIKE ?", (fecha_hoy + "%",))
    total_hoy = cursor.fetchone()[0] or 0

    # Total ventas en mes actual
    fecha_mes = datetime.now().strftime("%Y-%m")
    cursor.execute("SELECT SUM(total) FROM ventas WHERE fecha LIKE ?", (fecha_mes + "%",))
    total_mes = cursor.fetchone()[0] or 0

    # Mostrar totales
    tk.Label(f, text=f"Total ventas hoy ({fecha_hoy}): {total_hoy:.2f}").pack(pady=5)
    tk.Label(f, text=f"Total ventas mes ({fecha_mes}): {total_mes:.2f}").pack(pady=5)

    tk.Button(f, text="Volver al Menú", command=mostrar_menu).pack(pady=30)

# --- CONFIGURACIÓN ---
config_frame = frames["config"]

def mostrar_config():
    ocultar_frames()
    f = frames["config"]
    f.place(relwidth=1, relheight=1)
    for widget in f.winfo_children():
        widget.destroy()

    tk.Label(f, text="Configuración", font=("Arial", 24)).pack(pady=20)

    tk.Label(f, text="Tipo de Cambio CUP/USD:").pack()
    entry_tipo_cambio = tk.Entry(f)
    entry_tipo_cambio.pack()
    entry_tipo_cambio.insert(0, str(get_tipo_cambio()))

    def guardar_cambios():
        try:
            valor = float(entry_tipo_cambio.get())
            if valor <= 0:
                raise ValueError()
            set_tipo_cambio(valor)
            messagebox.showinfo("Éxito", "Tipo de cambio actualizado")
            mostrar_menu()
        except:
            messagebox.showerror("Error", "Ingrese un número válido y positivo")

    tk.Button(f, text="Guardar", command=guardar_cambios, bg="#4CAF50", fg="white").pack(pady=10)
    tk.Button(f, text="Volver al Menú", command=mostrar_menu).pack()

# --- Conectar botones ---
btn_productos.config(command=mostrar_productos)
btn_vender.config(command=mostrar_vender)
btn_historial.config(command=mostrar_historial)
btn_reportes.config(command=mostrar_reportes)
btn_config.config(command=mostrar_config)

# --- Iniciar con login ---
mostrar_login()

app.mainloop()
