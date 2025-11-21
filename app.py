# ...existing code...
from flask import Flask, url_for, render_template, request, redirect, flash, session
import mysql.connector
import bcrypt
from datetime import datetime, date, time, timedelta
import re


def normalize_phone(value):
    if not value:
        return ''
    return re.sub(r'\D', '', value)


def is_valid_phone(value):
    v = normalize_phone(value)
    return len(v) == 10

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'  # Necesaria para flash messages

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'formulario_db'
}

def obtener_conexion():
    return mysql.connector.connect(**DB_CONFIG)

# Mostrar primero la página principal
@app.route('/')
def index():
    return redirect(url_for('principal'))

@app.route('/principal')
def principal():
    return render_template('principal.html')

@app.route('/menu')
def menu():
    return render_template('menu.html')

@app.route('/contactos')
def contactos():
    return render_template('contactos.html')

@app.route('/gracias')
def gracias():
    return render_template('gracias.html')

# Página de reservaciones: acepta ?telefono=... para mostrar las reservaciones del usuario
@app.route('/reservaciones')
def reservaciones():
    # Requerir que el usuario esté autenticado para ver/crear reservaciones
    if not session.get('user_email'):
        flash('Debes iniciar sesión o registrarte para hacer una reservación.')
        # redirigir al formulario de login indicando que queremos volver a /reservaciones
        return redirect(url_for('loginform', next=url_for('reservaciones')))

    mis_reservaciones = []
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    # Buscar nombre, email y teléfono del usuario por su email
    cursor.execute('SELECT nombre, email, telefono FROM personas WHERE email = %s', (session.get('user_email'),))
    persona = cursor.fetchone()
    # Normalizar teléfono (solo dígitos) para evitar problemas con espacios, guiones o prefijos
    if persona and persona.get('telefono'):
        persona['telefono'] = re.sub(r'\D', '', persona['telefono'])
    if persona:
        telefono = persona['telefono']
        cursor.execute('SELECT * FROM reservaciones WHERE telefono = %s ORDER BY fecha, hora', (telefono,))
        mis_reservaciones = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('reservaciones.html', mis_reservaciones=mis_reservaciones, persona=persona)

# Mostrar formulario de login/registro
@app.route('/loginform')
def loginform():
    return render_template('index.html')

# Registro con validación de email duplicado
@app.route('/guardar', methods=['POST'])
def guardar():
    nombre = request.form['nombre']
    email = request.form['email']
    telefono = request.form['telefono']
    contrasena = request.form['contrasena']

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute('SELECT * FROM personas WHERE email = %s', (email,))
    existente = cursor.fetchone()

    if existente:
        flash("Este correo ya está registrado. Por favor usa otro o inicia sesión.")
        cursor.close()
        conexion.close()
        return redirect(url_for('loginform'))

    # Validar teléfono
    telefono = normalize_phone(telefono)
    if not is_valid_phone(telefono):
        flash('El teléfono debe contener exactamente 10 dígitos numéricos.')
        cursor.close()
        conexion.close()
        return redirect(url_for('loginform'))

    contrasena_cifrada = bcrypt.hashpw(contrasena.encode('utf-8'), bcrypt.gensalt())
    # Guardar como texto (utf-8) para evitar problemas al recuperar
    cursor.execute(
        'INSERT INTO personas (nombre, email, telefono, contrasena) VALUES (%s, %s, %s, %s)',
        (nombre, email, telefono, contrasena_cifrada.decode('utf-8'))
    )
    conexion.commit()
    cursor.close()
    conexion.close()

    # Guardar sesión del usuario recién registrado
    session['user_email'] = email

    # Si venimos con 'next' redirigir allí (por ejemplo a /reservaciones)
    next_page = request.args.get('next') or request.form.get('next')
    if next_page:
        return redirect(next_page)
    return redirect(url_for('principal'))

# Login
ADMIN_EMAIL = 'admin@ejemplo.com'
ADMIN_PASSWORD = 'admin123'

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    contrasena = request.form['contrasena']

    if email == ADMIN_EMAIL and contrasena == ADMIN_PASSWORD:
        # Guardar sesión del admin también para permitir acciones administrativas
        session['user_email'] = email
        return redirect(url_for('admin'))

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('SELECT * FROM personas WHERE email = %s', (email,))
    usuario = cursor.fetchone()
    cursor.close()
    conexion.close()

    if usuario and bcrypt.checkpw(contrasena.encode('utf-8'), usuario['contrasena'].encode('utf-8')):
        # Guardar sesión
        session['user_email'] = email
       
        # Si el formulario incluyó 'next', redirigir allí
        next_page = request.form.get('next') or request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('principal'))
    else:
        flash("Usuario o contraseña incorrectos.")
        return redirect(url_for('loginform'))


@app.route('/logout')
def logout():
    session.pop('user_email', None)
    flash('Has cerrado sesión.')
    return redirect(url_for('principal'))

# Panel administrador
@app.route('/admin')
def admin():
    return render_template('admin.html')

# CRUD usuarios (todo en una sola vista)
@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        telefono = request.form['telefono']
        telefono = normalize_phone(telefono)
        if not is_valid_phone(telefono):
            flash('El teléfono debe contener exactamente 10 dígitos numéricos.')
            cursor.close()
            conexion.close()
            return redirect(url_for('usuarios'))
        contrasena = request.form['contrasena']
        contrasena_cifrada = bcrypt.hashpw(contrasena.encode('utf-8'), bcrypt.gensalt())

        cursor.execute(
            'INSERT INTO personas (nombre, email, telefono, contrasena) VALUES (%s, %s, %s, %s)',
            (nombre, email, telefono, contrasena_cifrada.decode('utf-8'))
        )
        conexion.commit()

    cursor.execute('SELECT * FROM personas')
    usuarios = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('usuarios.html', usuarios=usuarios)

@app.route('/usuarios/actualizar/<int:id>', methods=['POST'])
def actualizar_usuario(id):
    nombre = request.form['nombre']
    email = request.form['email']
    telefono = request.form['telefono']
    telefono = normalize_phone(telefono)
    if not is_valid_phone(telefono):
        flash('El teléfono debe contener exactamente 10 dígitos numéricos.')
        return redirect(url_for('usuarios'))

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        'UPDATE personas SET nombre = %s, email = %s, telefono = %s WHERE id = %s',
        (nombre, email, telefono, id)
    )
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect(url_for('usuarios'))

@app.route('/usuarios/eliminar/<int:id>')
def eliminar_usuario(id):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('DELETE FROM personas WHERE id = %s', (id,))
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect(url_for('usuarios'))

@app.route('/buscar_usuario')
def buscar_usuario():
    id = request.args.get('id')
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('SELECT * FROM personas WHERE id = %s', (id,))
    usuario = cursor.fetchone()
    cursor.close()
    conexion.close()
    return render_template('usuarios.html', usuarios=[usuario] if usuario else [])

@app.route('/buscar_proveedor')
def buscar_proveedor():
    id = request.args.get('id')
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('SELECT * FROM proveedores WHERE id = %s', (id,))
    proveedor = cursor.fetchone()
    cursor.close()
    conexion.close()
    return render_template('proveedores.html', proveedores=[proveedor] if proveedor else [])

@app.route('/buscar_clientes')
def buscar_clientes():
    id = request.args.get('id')
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('SELECT * FROM clientes WHERE id = %s', (id,))
    cliente = cursor.fetchone()
    cursor.close()
    conexion.close()
    return render_template('clientes.html', clientes=[cliente] if cliente else [])

@app.route('/buscar_empleados')
def buscar_empleados():
    id = request.args.get('id')
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('SELECT * FROM empleados WHERE id = %s', (id,))
    empleado = cursor.fetchone()
    cursor.close()
    conexion.close()
    return render_template('empleados.html', empleados=[empleado] if empleado else [])

@app.route('/buscar_productos')
def buscar_productos():
    id = request.args.get('id')
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('SELECT * FROM productos WHERE id = %s', (id,))
    producto = cursor.fetchone()
    cursor.close()
    conexion.close()
    return render_template('productos.html', productos=[producto] if producto else [])

@app.route('/buscar_reservacion')
def buscar_reservacion():
    id = request.args.get('id')
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('SELECT * FROM reservaciones WHERE id = %s', (id,))
    reservas = cursor.fetchone()
    cursor.close()
    conexion.close()
    return render_template('reservacionesadmin.html', reservaciones=[reservas] if reservas else [])

@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        telefono = normalize_phone(request.form['telefono'])
        direccion = request.form['direccion']
        if not is_valid_phone(telefono):
            flash('El teléfono debe contener exactamente 10 dígitos numéricos.')
            cursor.close()
            conexion.close()
            return redirect(url_for('clientes'))

        cursor.execute(
            'INSERT INTO clientes (nombre, email, telefono, direccion) VALUES (%s, %s, %s, %s)',
            (nombre, email, telefono, direccion)
        )
        conexion.commit()

    cursor.execute('SELECT * FROM clientes')
    clientes = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('clientes.html', clientes=clientes)

@app.route('/clientes/actualizar/<int:id>', methods=['POST'])
def actualizar_cliente(id):
    nombre = request.form['nombre']
    email = request.form['email']
    telefono = normalize_phone(request.form['telefono'])
    if not is_valid_phone(telefono):
        flash('El teléfono debe contener exactamente 10 dígitos numéricos.')
        return redirect(url_for('clientes'))
    direccion = request.form['direccion']

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        'UPDATE clientes SET nombre = %s, email = %s, telefono = %s, direccion = %s WHERE id = %s',
        (nombre, email, telefono, direccion, id)
    )
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect(url_for('clientes'))

@app.route('/clientes/eliminar/<int:id>')
def eliminar_cliente(id):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('DELETE FROM clientes WHERE id = %s', (id,))
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect(url_for('clientes'))

@app.route('/productos', methods=['GET', 'POST'])
def productos():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        stock = request.form['stock']

        cursor.execute(
            'INSERT INTO productos (nombre, descripcion, precio, stock) VALUES (%s, %s, %s, %s)',
            (nombre, descripcion, precio, stock)
        )
        conexion.commit()

    cursor.execute('SELECT * FROM productos')
    productos = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('productos.html', productos=productos)

@app.route('/productos/actualizar/<int:id>', methods=['POST'])
def actualizar_producto(id):
    nombre = request.form['nombre']
    descripcion = request.form['descripcion']
    precio = request.form['precio']
    stock = request.form['stock']

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        'UPDATE productos SET nombre = %s, descripcion = %s, precio = %s, stock = %s WHERE id = %s',
        (nombre, descripcion, precio, stock, id)
    )
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect(url_for('productos'))

@app.route('/productos/eliminar/<int:id>')
def eliminar_producto(id):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('DELETE FROM productos WHERE id = %s', (id,))
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect(url_for('productos'))

@app.route('/proveedores', methods=['GET', 'POST'])
def proveedores():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    if request.method == 'POST':
        nombre = request.form['nombre']
        empresa = request.form['empresa']
        telefono = normalize_phone(request.form['telefono'])
        if not is_valid_phone(telefono):
            flash('El teléfono debe contener exactamente 10 dígitos numéricos.')
            cursor.close()
            conexion.close()
            return redirect(url_for('proveedores'))
        email = request.form['email']

        cursor.execute(
            'INSERT INTO proveedores (nombre, empresa, telefono, email) VALUES (%s, %s, %s, %s)',
            (nombre, empresa, telefono, email)
        )
        conexion.commit()

    cursor.execute('SELECT * FROM proveedores')
    proveedores = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('proveedores.html', proveedores=proveedores)

@app.route('/proveedores/actualizar/<int:id>', methods=['POST'])
def actualizar_proveedor(id):
    nombre = request.form['nombre']
    empresa = request.form['empresa']
    telefono = normalize_phone(request.form['telefono'])
    if not is_valid_phone(telefono):
        flash('El teléfono debe contener exactamente 10 dígitos numéricos.')
        return redirect(url_for('proveedores'))
    email = request.form['email']

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        'UPDATE proveedores SET nombre = %s, empresa = %s, telefono = %s, email = %s WHERE id = %s',
        (nombre, empresa, telefono, email, id)
    )
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect(url_for('proveedores'))

@app.route('/proveedores/eliminar/<int:id>')
def eliminar_proveedor(id):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('DELETE FROM proveedores WHERE id = %s', (id,))
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect(url_for('proveedores'))

@app.route('/empleados', methods=['GET', 'POST'])
def empleados():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    if request.method == 'POST':
        nombre = request.form['nombre']
        puesto = request.form['puesto']
        telefono = normalize_phone(request.form['telefono'])
        if not is_valid_phone(telefono):
            flash('El teléfono debe contener exactamente 10 dígitos numéricos.')
            cursor.close()
            conexion.close()
            return redirect(url_for('empleados'))
        email = request.form['email']
        fecha_ingreso = request.form['fecha_ingreso']
        pago = request.form['pago']
        turno = request.form['turno']

        cursor.execute(
            'INSERT INTO empleados (nombre, puesto, telefono, email, fecha_ingreso, pago, turno) VALUES (%s, %s, %s, %s, %s, %s, %s)',
            (nombre, puesto, telefono, email, fecha_ingreso, pago, turno)
        )
        conexion.commit()

    cursor.execute('SELECT * FROM empleados')
    empleados = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('empleados.html', empleados=empleados)

@app.route('/empleados/actualizar/<int:id>', methods=['POST'])
def actualizar_empleado(id):
    nombre = request.form['nombre']
    puesto = request.form['puesto']
    telefono = normalize_phone(request.form['telefono'])
    if not is_valid_phone(telefono):
        flash('El teléfono debe contener exactamente 10 dígitos numéricos.')
        return redirect(url_for('empleados'))
    email = request.form['email']
    fecha_ingreso = request.form['fecha_ingreso']
    pago = request.form['pago']
    turno = request.form['turno']

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        'UPDATE empleados SET nombre = %s, puesto = %s, telefono = %s, email = %s, fecha_ingreso = %s, pago = %s, turno = %s WHERE id = %s',
        (nombre, puesto, telefono, email, fecha_ingreso, pago, turno, id)
    )

    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect(url_for('empleados'))

@app.route('/empleados/eliminar/<int:id>')
def eliminar_empleado(id):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('DELETE FROM empleados WHERE id = %s', (id,))
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect(url_for('empleados'))

@app.route('/reservacionesadmin', methods=['GET', 'POST'])
def reservacionesadmin():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    mensaje = None

    if request.method == 'POST':
        nombre = request.form['nombre']
        telefono = normalize_phone(request.form.get('telefono'))  # ahora admin puede agregar teléfono
        fecha = request.form['fecha']
        hora = request.form['hora']

        # Validaciones similares a la vista pública
        if not telefono:
            mensaje = 'Debe indicar un número de teléfono para la reservación.'
            cursor.execute('SELECT * FROM reservaciones ORDER BY fecha, hora')
            reservaciones = cursor.fetchall()
            cursor.close()
            conexion.close()
            return render_template('reservacionesadmin.html', reservaciones=reservaciones, mensaje=mensaje)
        if not is_valid_phone(telefono):
            mensaje = 'El teléfono debe contener exactamente 10 dígitos numéricos.'
            cursor.execute('SELECT * FROM reservaciones ORDER BY fecha, hora')
            reservaciones = cursor.fetchall()
            cursor.close()
            conexion.close()
            return render_template('reservacionesadmin.html', reservaciones=reservaciones, mensaje=mensaje)

        if not fecha or not hora:
            mensaje = 'Fecha y hora son obligatorias.'
            cursor.execute('SELECT * FROM reservaciones ORDER BY fecha, hora')
            reservaciones = cursor.fetchall()
            cursor.close()
            conexion.close()
            return render_template('reservacionesadmin.html', reservaciones=reservaciones, mensaje=mensaje)

        # Parsear fecha y hora
        try:
            fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        except ValueError:
            mensaje = 'Formato de fecha inválido.'
            cursor.execute('SELECT * FROM reservaciones ORDER BY fecha, hora')
            reservaciones = cursor.fetchall()
            cursor.close()
            conexion.close()
            return render_template('reservacionesadmin.html', reservaciones=reservaciones, mensaje=mensaje)

        try:
            hora_obj = datetime.strptime(hora, '%H:%M').time()
        except ValueError:
            mensaje = 'Formato de hora inválido.'
            cursor.execute('SELECT * FROM reservaciones ORDER BY fecha, hora')
            reservaciones = cursor.fetchall()
            cursor.close()
            conexion.close()
            return render_template('reservacionesadmin.html', reservaciones=reservaciones, mensaje=mensaje)

        # Validar rango horario permitido (09:00 - 23:00)
        inicio_permitido = time(9, 0)
        fin_permitido = time(23, 0)
        if hora_obj < inicio_permitido or hora_obj > fin_permitido:
            mensaje = 'Las reservaciones sólo pueden hacerse entre las 09:00 y las 23:00.'
            cursor.execute('SELECT * FROM reservaciones ORDER BY fecha, hora')
            reservaciones = cursor.fetchall()
            cursor.close()
            conexion.close()
            return render_template('reservacionesadmin.html', reservaciones=reservaciones, mensaje=mensaje)

        ahora = datetime.now()
        hoy = ahora.date()
        hora_actual = ahora.time()

        if fecha_obj < hoy:
            mensaje = 'No se pueden hacer reservaciones en fechas pasadas.'
            cursor.execute('SELECT * FROM reservaciones ORDER BY fecha, hora')
            reservaciones = cursor.fetchall()
            cursor.close()
            conexion.close()
            return render_template('reservacionesadmin.html', reservaciones=reservaciones, mensaje=mensaje)

        if fecha_obj == hoy and hora_obj <= hora_actual:
            mensaje = 'La hora seleccionada ya pasó. Elige una hora futura.'
            cursor.execute('SELECT * FROM reservaciones ORDER BY fecha, hora')
            reservaciones = cursor.fetchall()
            cursor.close()
            conexion.close()
            return render_template('reservacionesadmin.html', reservaciones=reservaciones, mensaje=mensaje)

        # Contar cuántas reservaciones hay en la misma fecha y misma hora (por hora)
        cursor.execute(
            'SELECT COUNT(*) AS cnt, MAX(hora) AS max_hora FROM reservaciones WHERE fecha = %s AND HOUR(hora) = HOUR(%s)',
            (fecha, hora)
        )
        fila = cursor.fetchone()
        cantidad = fila['cnt'] if isinstance(fila, dict) else fila[0]
        max_hora = fila['max_hora'] if isinstance(fila, dict) else (fila[1] if fila[1] else None)

        if cantidad >= 3:
            # Si ya hay 3 en esa hora, exigir que la nueva hora sea al menos 1 hora después del max existente
            if max_hora:
                # max_hora puede ser time o str según conector
                if isinstance(max_hora, str):
                    max_hora_obj = datetime.strptime(max_hora, '%H:%M:%S').time() if len(max_hora.split(':')) == 3 else datetime.strptime(max_hora, '%H:%M').time()
                else:
                    max_hora_obj = max_hora
                max_dt = datetime.combine(fecha_obj, max_hora_obj) + timedelta(hours=1)
                req_dt = datetime.combine(fecha_obj, hora_obj)
                if req_dt < max_dt:
                    mensaje = f'Ya hay 3 reservaciones en esa hora. Debes escoger una hora >= {max_dt.time().strftime("%H:%M")}.'
                    cursor.execute('SELECT * FROM reservaciones ORDER BY fecha, hora')
                    reservaciones = cursor.fetchall()
                    cursor.close()
                    conexion.close()
                    return render_template('reservacionesadmin.html', reservaciones=reservaciones, mensaje=mensaje)
            else:
                mensaje = 'Ya hay 3 reservaciones en esa hora. Por favor escoge otra hora.'
                cursor.execute('SELECT * FROM reservaciones ORDER BY fecha, hora')
                reservaciones = cursor.fetchall()
                cursor.close()
                conexion.close()
                return render_template('reservacionesadmin.html', reservaciones=reservaciones, mensaje=mensaje)

        # Insertar nueva reservación (incluye teléfono)
        cursor.execute(
            'INSERT INTO reservaciones (nombre, fecha, hora, telefono) VALUES (%s, %s, %s, %s)',
            (nombre, fecha, hora, telefono)
        )
        conexion.commit()
        mensaje = 'Reservación registrada con éxito'

    cursor.execute('SELECT * FROM reservaciones ORDER BY fecha, hora')
    reservaciones = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('reservacionesadmin.html', reservaciones=reservaciones, mensaje=mensaje)

@app.route('/reservaciones/eliminar/<int:id>')
def eliminar_reservacion(id):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute('DELETE FROM reservaciones WHERE id = %s', (id,))
    conexion.commit()
    cursor.close()
    conexion.close()
    # volver a la página origen si existe
    ref = request.referrer
    if ref:
        return redirect(ref)
    return redirect(url_for('reservacionesadmin'))

@app.route('/reservaciones/actualizar/<int:id>', methods=['POST'])
def actualizar_reservacion(id):
    nombre = request.form['nombre']
    fecha = request.form['fecha']
    hora = request.form['hora']
    telefono = normalize_phone(request.form.get('telefono'))
    if not is_valid_phone(telefono):
        flash('El teléfono debe contener exactamente 10 dígitos numéricos.')
        return redirect(url_for('reservacionesadmin'))

    # Validar fecha y hora
    if not fecha or not hora:
        flash('Fecha y hora son obligatorias.')
        return redirect(url_for('reservacionesadmin'))

    try:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
    except ValueError:
        flash('Formato de fecha inválido.')
        return redirect(url_for('reservacionesadmin'))

    try:
        hora_obj = datetime.strptime(hora, '%H:%M').time()
    except ValueError:
        flash('Formato de hora inválido.')
        return redirect(url_for('reservacionesadmin'))

    # Rango horario
    inicio_permitido = time(9, 0)
    fin_permitido = time(23, 0)
    if hora_obj < inicio_permitido or hora_obj > fin_permitido:
        flash('Las reservaciones sólo pueden hacerse entre las 09:00 y las 23:00.')
        return redirect(url_for('reservacionesadmin'))

    ahora = datetime.now()
    hoy = ahora.date()
    hora_actual = ahora.time()
    if fecha_obj < hoy or (fecha_obj == hoy and hora_obj <= hora_actual):
        flash('No se permiten reservaciones en el pasado.')
        return redirect(url_for('reservacionesadmin'))

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        'UPDATE reservaciones SET nombre = %s, fecha = %s, hora = %s, telefono = %s WHERE id = %s',
        (nombre, fecha, hora, telefono, id)
    )
    conexion.commit()
    cursor.close()
    conexion.close()
    return redirect(url_for('reservacionesadmin'))

# Endpoint para que un usuario agregue una reservación (incluye teléfono)
@app.route('/reservar', methods=['GET', 'POST'])
def reservar():
    # Si es GET mostramos el formulario (protegido)
    if request.method == 'GET':
        if not session.get('user_email'):
            flash('Debes iniciar sesión o registrarte para hacer una reservación.')
            return redirect(url_for('loginform', next=url_for('reservaciones')))
            # usuario autenticado: delegar a la vista /reservaciones (aquí se cargan los datos de persona)
            return redirect(url_for('reservaciones'))

    # POST: creación de la reservación requiere sesión
    if not session.get('user_email'):
        flash('Debes iniciar sesión o registrarte para hacer una reservación.')
        return redirect(url_for('loginform', next=url_for('reservaciones')))

    # Cargar datos de la persona para poder re-renderizar el formulario con autocompletado si hay errores
    # Cargar persona (usar conexión temporal y cerrarla inmediatamente)
    _conn_p = obtener_conexion()
    _cur_p = _conn_p.cursor(dictionary=True)
    _cur_p.execute('SELECT nombre, email, telefono FROM personas WHERE email = %s', (session.get('user_email'),))
    persona = _cur_p.fetchone()
    if persona and persona.get('telefono'):
        persona['telefono'] = re.sub(r'\D', '', persona['telefono'])
    _cur_p.close()
    _conn_p.close()

    # continuar con el flujo existente para POST
    nombre = request.form.get('nombre')
    # Validar nombre: solo letras, espacios y acentos
    import unicodedata
    def is_valid_nombre(n):
        if not n:
            return False
        # Permitir letras, espacios y acentos
        for c in n:
            cat = unicodedata.category(c)
            if not (cat.startswith('L') or c in ' áéíóúÁÉÍÓÚñÑüÜ'):
                return False
        return True
    if not is_valid_nombre(nombre):
        mensaje = 'El nombre solo puede contener letras, espacios y acentos.'
        return render_template('reservaciones.html', mensaje=mensaje, mis_reservaciones=[], persona=persona)
    fecha = request.form.get('fecha')
    hora = request.form.get('hora')
    telefono = request.form.get('telefono')

    # Normalizar teléfono recibido (el usuario puede pegar formatos con espacios/guiones)
    telefono = normalize_phone(telefono)
    # Forzar que el teléfono usado pertenezca al usuario logueado (salvo admin)
    persona_phone = None
    if persona and persona.get('telefono'):
        persona_phone = normalize_phone(persona.get('telefono'))
    user_email = session.get('user_email')
    if user_email != ADMIN_EMAIL:
        # if user has a phone in personas table, override submitted telefono to prevent impersonation
        if persona_phone:
            telefono = persona_phone
        else:
            # no phone available for this user -> reject
            mensaje = 'No se encontró un número de teléfono asociado a tu cuenta. Añádelo en tu perfil antes de reservar.'
            return render_template('reservaciones.html', mensaje=mensaje, mensaje_tipo='error', mis_reservaciones=[], persona=persona)
    # Log para depuración en desarrollo
    app.logger.debug(f"/reservar POST - raw telefono: {request.form.get('telefono')!r}, normalized: {telefono!r}, len={len(telefono) if telefono else 'None'}")

    # Si por alguna razón no hay teléfono (debería estar forzado arriba), intentar fallback a persona
    if not telefono and persona and persona.get('telefono'):
        telefono = normalize_phone(persona.get('telefono'))

    # Exigir teléfono válido de 10 dígitos
    if not telefono or not is_valid_phone(telefono):
        mensaje = 'El teléfono debe contener exactamente 10 dígitos numéricos.'
        return render_template('reservaciones.html', mensaje=mensaje, mis_reservaciones=[], persona=persona)

    if not fecha or not hora:
        mensaje = 'Fecha y hora son obligatorias.'
        return render_template('reservaciones.html', mensaje=mensaje, mis_reservaciones=[])

    # Parsear fecha y hora
    try:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
    except ValueError:
        mensaje = 'Formato de fecha inválido.'
        return render_template('reservaciones.html', mensaje=mensaje, mis_reservaciones=[])

    try:
        hora_obj = datetime.strptime(hora, '%H:%M').time()
    except ValueError:
        mensaje = 'Formato de hora inválido.'
        return render_template('reservaciones.html', mensaje=mensaje, mis_reservaciones=[])

    # Validar rango horario permitido (09:00 - 23:00)
    inicio_permitido = time(9, 0)
    fin_permitido = time(23, 0)
    if hora_obj < inicio_permitido or hora_obj > fin_permitido:
        mensaje = 'Las reservaciones sólo pueden hacerse entre las 09:00 y las 23:00.'
        return render_template('reservaciones.html', mensaje=mensaje, mensaje_tipo='error', mis_reservaciones=[], persona=persona)

    ahora = datetime.now()
    hoy = ahora.date()
    hora_actual = ahora.time()

    # No permitir reservar en fechas pasadas
    if fecha_obj < hoy:
        mensaje = 'No se pueden hacer reservaciones en fechas pasadas.'
        return render_template('reservaciones.html', mensaje=mensaje, mis_reservaciones=[])

    # Si es el mismo día, no permitir horas pasadas o iguales al momento actual
    if fecha_obj == hoy and hora_obj <= hora_actual:
        mensaje = 'La hora seleccionada ya pasó. Elige una hora futura.'
        return render_template('reservaciones.html', mensaje=mensaje, mensaje_tipo='error', mis_reservaciones=[], persona=persona)

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    # Verificar cuántas reservaciones hay en esa fecha y en la misma HORA (por hora)
    cursor.execute(
        'SELECT COUNT(*) AS cnt, MAX(hora) AS max_hora FROM reservaciones WHERE fecha = %s AND HOUR(hora) = HOUR(%s)',
        (fecha, hora)
    )
    fila = cursor.fetchone()
    cantidad = fila['cnt'] if fila else 0
    max_hora = fila['max_hora'] if fila and 'max_hora' in fila else None

    if cantidad >= 3:
        if max_hora:
            if isinstance(max_hora, str):
                max_hora_obj = datetime.strptime(max_hora, '%H:%M:%S').time() if len(max_hora.split(':')) == 3 else datetime.strptime(max_hora, '%H:%M').time()
            else:
                max_hora_obj = max_hora
            max_dt = datetime.combine(fecha_obj, max_hora_obj) + timedelta(hours=1)
            req_dt = datetime.combine(fecha_obj, hora_obj)
            if req_dt < max_dt:
                mensaje = f'Ya hay 3 reservaciones en esa hora. Debes escoger una hora >= {max_dt.time().strftime("%H:%M")}.'
                cursor.close()
                conexion.close()
                return render_template('reservaciones.html', mensaje=mensaje, mis_reservaciones=[])
        else:
            mensaje = 'Ya hay 3 reservaciones en esa hora. Por favor escoge otra hora.'
            cursor.close()
            conexion.close()
            return render_template('reservaciones.html', mensaje=mensaje, mis_reservaciones=[])

    # Insertar nueva reservación (incluye teléfono)
    cursor.execute(
        'INSERT INTO reservaciones (nombre, fecha, hora, telefono) VALUES (%s, %s, %s, %s)',
        (nombre, fecha, hora, telefono)
    )
    conexion.commit()

    # Obtener las reservaciones del usuario por teléfono para mostrar a la derecha
    if telefono:
        cursor.execute('SELECT * FROM reservaciones WHERE telefono = %s ORDER BY fecha, hora', (telefono,))
        mis_reservaciones = cursor.fetchall()
    elif persona and persona.get('telefono'):
        cursor.execute('SELECT * FROM reservaciones WHERE telefono = %s ORDER BY fecha, hora', (persona['telefono'],))
        mis_reservaciones = cursor.fetchall()
    else:
        mis_reservaciones = []
    cursor.close()
    conexion.close()

    mensaje = 'Tu reservación está hecha'
    return render_template('reservaciones.html', mensaje=mensaje, mis_reservaciones=mis_reservaciones)

# Endpoint para cancelar una reservación por id (redirige a la página de origen si existe)
@app.route('/reservaciones/cancelar/<int:id>')
def cancelar_reservacion(id):
    # Requerir sesión
    if not session.get('user_email'):
        flash('Debes iniciar sesión para cancelar reservaciones.')
        return redirect(url_for('loginform', next=url_for('reservaciones')))

    # Solo permitir cancelar si el usuario es dueño de la reservación (por teléfono) o es admin
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute('SELECT * FROM reservaciones WHERE id = %s', (id,))
    reserva = cursor.fetchone()
    if not reserva:
        cursor.close()
        conexion.close()
        flash('Reservación no encontrada.')
        return redirect(url_for('reservaciones'))

    # Si es admin, permitir
    user_email = session.get('user_email')
    if user_email == ADMIN_EMAIL:
        allowed = True
    else:
        # verificar que la reserva pertenezca al usuario (comparar por teléfono)
        cursor.execute('SELECT telefono FROM personas WHERE email = %s', (user_email,))
        persona = cursor.fetchone()
        telefono_usuario = persona['telefono'] if persona and 'telefono' in persona else None
        allowed = (telefono_usuario and re.sub(r'\D','', telefono_usuario) == re.sub(r'\D','', str(reserva.get('telefono'))))

    if not allowed:
        cursor.close()
        conexion.close()
        flash('No tienes permiso para cancelar esta reservación.')
        return redirect(url_for('reservaciones'))

    # Eliminar la reservación
    cursor.execute('DELETE FROM reservaciones WHERE id = %s', (id,))
    conexion.commit()
    cursor.close()
    conexion.close()

    # Redirigir a la página de reservaciones del usuario (mostrando las reservaciones actualizadas)
    return redirect(url_for('reservaciones'))

# Ejecutar servidor
if __name__ == '__main__':
    app.run(debug=True)
# ...existing code...