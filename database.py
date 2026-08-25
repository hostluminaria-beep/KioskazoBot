import os
from libsql_client import create_client

url = os.environ.get("TURSO_URL", "")
token = os.environ.get("TURSO_TOKEN", "")
client = create_client(url=url, auth_token=token)

def init_db():
    client.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            nombre TEXT UNIQUE,
            contrasena TEXT,
            anonimo INTEGER DEFAULT 1,
            puntuacion REAL DEFAULT 0,
            num_valoraciones INTEGER DEFAULT 0,
            max_ofertas INTEGER DEFAULT 5,
            creado TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    client.execute("""
        CREATE TABLE IF NOT EXISTS ofertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            categoria TEXT,
            producto TEXT,
            cantidad REAL,
            precio REAL,
            moneda TEXT,
            descripcion TEXT,
            estado TEXT DEFAULT 'activa',
            creado TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    client.execute("""
        CREATE TABLE IF NOT EXISTS contactos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oferta_id INTEGER,
            comprador_id INTEGER,
            vendedor_id INTEGER,
            estado TEXT DEFAULT 'pendiente',
            creado TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    client.execute("""
        CREATE TABLE IF NOT EXISTS valoraciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comprador_id INTEGER,
            vendedor_id INTEGER,
            oferta_id INTEGER,
            puntos REAL,
            comentario TEXT,
            creado TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    client.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            telegram_id INTEGER PRIMARY KEY
        )
    """)
    client.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            nombre TEXT PRIMARY KEY
        )
    """)
    try:
        client.execute("INSERT INTO categorias (nombre) VALUES ('Divisa')")
        client.execute("INSERT INTO categorias (nombre) VALUES ('Aceite')")
    except:
        pass

def get_usuario(telegram_id):
    r = client.execute("SELECT * FROM usuarios WHERE telegram_id = ?", [telegram_id])
    return r.rows[0] if r.rows else None

def get_usuario_by_nombre(nombre):
    r = client.execute("SELECT * FROM usuarios WHERE nombre = ?", [nombre])
    return r.rows[0] if r.rows else None

def registrar_usuario(telegram_id, nombre, contrasena):
    client.execute(
        "INSERT INTO usuarios (telegram_id, nombre, contrasena) VALUES (?, ?, ?)",
        [telegram_id, nombre, contrasena]
    )

def verificar_login(nombre, contrasena, telegram_id):
    u = get_usuario_by_nombre(nombre)
    if u and u["contrasena"] == contrasena and u["telegram_id"] == telegram_id:
        return u
    return None

def es_admin(telegram_id):
    r = client.execute("SELECT * FROM admins WHERE telegram_id = ?", [telegram_id])
    return len(r.rows) > 0

def add_admin(telegram_id):
    client.execute("INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", [telegram_id])

def crear_oferta(usuario_id, categoria, producto, cantidad, precio, moneda, descripcion):
    client.execute(
        "INSERT INTO ofertas (usuario_id, categoria, producto, cantidad, precio, moneda, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [usuario_id, categoria, producto, cantidad, precio, moneda, descripcion]
    )

def mis_ofertas(usuario_id):
    r = client.execute("SELECT * FROM ofertas WHERE usuario_id = ? ORDER BY creado DESC", [usuario_id])
    return r.rows

def buscar_ofertas(texto):
    r = client.execute(
        "SELECT o.*, u.puntuacion FROM ofertas o JOIN usuarios u ON o.usuario_id = u.id WHERE o.estado = 'activa' AND (o.producto LIKE ? OR o.descripcion LIKE ?) ORDER BY u.puntuacion DESC, o.creado DESC",
        [f"%{texto}%", f"%{texto}%"]
    )
    return r.rows

def get_oferta(oferta_id):
    r = client.execute("SELECT * FROM ofertas WHERE id = ?", [oferta_id])
    return r.rows[0] if r.rows else None

def update_oferta(oferta_id, **campos):
    for k, v in campos.items():
        client.execute(f"UPDATE ofertas SET {k} = ? WHERE id = ?", [v, oferta_id])

def borrar_oferta(oferta_id):
    client.execute("DELETE FROM ofertas WHERE id = ?", [oferta_id])

def crear_contacto(oferta_id, comprador_id, vendedor_id):
    client.execute(
        "INSERT INTO contactos (oferta_id, comprador_id, vendedor_id) VALUES (?, ?, ?)",
        [oferta_id, comprador_id, vendedor_id]
    )

def contactos_pendientes(vendedor_id):
    r = client.execute(
        "SELECT c.*, o.producto, u.nombre FROM contactos c JOIN ofertas o ON c.oferta_id = o.id JOIN usuarios u ON c.comprador_id = u.id WHERE c.vendedor_id = ? AND c.estado = 'pendiente'",
        [vendedor_id]
    )
    return r.rows

def update_contacto(contacto_id, estado):
    client.execute("UPDATE contactos SET estado = ? WHERE id = ?", [estado, contacto_id])

def valorar(comprador_id, vendedor_id, oferta_id, puntos, comentario):
    client.execute(
        "INSERT INTO valoraciones (comprador_id, vendedor_id, oferta_id, puntos, comentario) VALUES (?, ?, ?, ?, ?)",
        [comprador_id, vendedor_id, oferta_id, puntos, comentario]
    )
    r = client.execute("SELECT AVG(puntos), COUNT(*) FROM valoraciones WHERE vendedor_id = ?", [vendedor_id])
    if r.rows and r.rows[0][0] is not None:
        client.execute(
            "UPDATE usuarios SET puntuacion = ?, num_valoraciones = ? WHERE id = ?",
            [r.rows[0][0], r.rows[0][1], vendedor_id]
        )

def get_usuario_by_id(uid):
    r = client.execute("SELECT * FROM usuarios WHERE id = ?", [uid])
    return r.rows[0] if r.rows else None
