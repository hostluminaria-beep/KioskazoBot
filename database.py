import os
import json
import hashlib
import requests

TURSO_URL = os.environ.get("TURSO_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "")

def execute(sql, params=None):
    headers = {"Authorization": f"Bearer {TURSO_TOKEN}", "Content-Type": "application/json"}
    if params:
        for i, p in enumerate(params):
            sql = sql.replace("?", f"${i+1}", 1)
    data = {"statements": [{"sql": sql, "args": params or []}]}
    r = requests.post(f"{TURSO_URL}/v2/pipeline", headers=headers, json=data, timeout=10)
    result = r.json()
    return result.get("results", [{}])[0]

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def init_db():
    execute("""
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
    execute("""
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
    execute("""
        CREATE TABLE IF NOT EXISTS contactos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oferta_id INTEGER,
            comprador_id INTEGER,
            vendedor_id INTEGER,
            estado TEXT DEFAULT 'pendiente',
            creado TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    execute("""
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
    execute("""
        CREATE TABLE IF NOT EXISTS admins (
            telegram_id INTEGER PRIMARY KEY
        )
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            nombre TEXT PRIMARY KEY
        )
    """)
    try:
        execute("INSERT INTO categorias (nombre) VALUES ('Divisa')")
        execute("INSERT INTO categorias (nombre) VALUES ('Aceite')")
    except:
        pass

def get_usuario(telegram_id):
    r = execute("SELECT * FROM usuarios WHERE telegram_id = ?", [telegram_id])
    rows = r.get("rows", [])
    if rows:
        cols = [c["name"] for c in r.get("columns", [])]
        return dict(zip(cols, rows[0]))
    return None

def get_usuario_by_nombre(nombre):
    r = execute("SELECT * FROM usuarios WHERE nombre = ?", [nombre])
    rows = r.get("rows", [])
    if rows:
        cols = [c["name"] for c in r.get("columns", [])]
        return dict(zip(cols, rows[0]))
    return None

def registrar_usuario(telegram_id, nombre, contrasena):
    execute("INSERT INTO usuarios (telegram_id, nombre, contrasena) VALUES (?, ?, ?)",
            [telegram_id, nombre, hash_password(contrasena)])
    r = execute("SELECT id FROM usuarios WHERE telegram_id = ?", [telegram_id])
    rows = r.get("rows", [])
    if rows:
        return rows[0][0]
    return None

def verificar_login(nombre, contrasena, telegram_id):
    u = get_usuario_by_nombre(nombre)
    if u and u["contrasena"] == hash_password(contrasena) and u["telegram_id"] == telegram_id:
        return u
    return None

def es_admin(telegram_id):
    r = execute("SELECT * FROM admins WHERE telegram_id = ?", [telegram_id])
    return len(r.get("rows", [])) > 0

def add_admin(telegram_id):
    execute("INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", [telegram_id])

def crear_oferta(usuario_id, categoria, producto, cantidad, precio, moneda, descripcion):
    execute("INSERT INTO ofertas (usuario_id, categoria, producto, cantidad, precio, moneda, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [usuario_id, categoria, producto, cantidad, precio, moneda, descripcion])

def mis_ofertas(usuario_id):
    r = execute("SELECT * FROM ofertas WHERE usuario_id = ? ORDER BY creado DESC", [usuario_id])
    rows = r.get("rows", [])
    cols = [c["name"] for c in r.get("columns", [])]
    return [dict(zip(cols, row)) for row in rows]

def buscar_ofertas(texto):
    r = execute(
        "SELECT o.*, u.puntuacion FROM ofertas o JOIN usuarios u ON o.usuario_id = u.id WHERE o.estado = 'activa' AND (o.producto LIKE ? OR o.descripcion LIKE ?) ORDER BY u.puntuacion DESC, o.creado DESC",
        [f"%{texto}%", f"%{texto}%"]
    )
    rows = r.get("rows", [])
    cols = [c["name"] for c in r.get("columns", [])]
    return [dict(zip(cols, row)) for row in rows]

def get_oferta(oferta_id):
    r = execute("SELECT * FROM ofertas WHERE id = ?", [oferta_id])
    rows = r.get("rows", [])
    if rows:
        cols = [c["name"] for c in r.get("columns", [])]
        return dict(zip(cols, rows[0]))
    return None

def update_oferta(oferta_id, **campos):
    for k, v in campos.items():
        execute(f"UPDATE ofertas SET {k} = ? WHERE id = ?", [v, oferta_id])

def borrar_oferta(oferta_id):
    execute("DELETE FROM ofertas WHERE id = ?", [oferta_id])

def crear_contacto(oferta_id, comprador_id, vendedor_id):
    execute("INSERT INTO contactos (oferta_id, comprador_id, vendedor_id) VALUES (?, ?, ?)",
            [oferta_id, comprador_id, vendedor_id])

def contactos_pendientes(vendedor_id):
    r = execute(
        "SELECT c.*, o.producto, u.nombre FROM contactos c JOIN ofertas o ON c.oferta_id = o.id JOIN usuarios u ON c.comprador_id = u.id WHERE c.vendedor_id = ? AND c.estado = 'pendiente'",
        [vendedor_id]
    )
    rows = r.get("rows", [])
    cols = [c["name"] for c in r.get("columns", [])]
    return [dict(zip(cols, row)) for row in rows]

def update_contacto(contacto_id, estado):
    execute("UPDATE contactos SET estado = ? WHERE id = ?", [estado, contacto_id])

def valorar(comprador_id, vendedor_id, oferta_id, puntos, comentario):
    execute("INSERT INTO valoraciones (comprador_id, vendedor_id, oferta_id, puntos, comentario) VALUES (?, ?, ?, ?, ?)",
            [comprador_id, vendedor_id, oferta_id, puntos, comentario])
    r = execute("SELECT AVG(puntos), COUNT(*) FROM valoraciones WHERE vendedor_id = ?", [vendedor_id])
    rows = r.get("rows", [])
    if rows and rows[0][0] is not None:
        execute("UPDATE usuarios SET puntuacion = ?, num_valoraciones = ? WHERE id = ?",
                [rows[0][0], rows[0][1], vendedor_id])

def get_usuario_by_id(uid):
    r = execute("SELECT * FROM usuarios WHERE id = ?", [uid])
    rows = r.get("rows", [])
    if rows:
        cols = [c["name"] for c in r.get("columns", [])]
        return dict(zip(cols, rows[0]))
    return None
