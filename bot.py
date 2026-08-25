from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import database as db
import os

TOKEN = os.environ.get("TOKEN", "")
app = Application.builder().token(TOKEN).build()
sesiones = {}
estados = {}

async def start(update, context):
    teclado = [
        [InlineKeyboardButton("Entrar", callback_data="login")],
        [InlineKeyboardButton("Registrarme", callback_data="registro")],
        [InlineKeyboardButton("Ayuda", callback_data="ayuda")],
    ]
    await update.message.reply_text(
        "KIOSKAZO\n\nPublica, busca y contacta ofertas de venta.",
        reply_markup=InlineKeyboardMarkup(teclado)
    )

async def ayuda(update, context):
    texto = (
        "COMANDOS\n\n"
        "/start - Inicio\n"
        "/publicar - Crear oferta\n"
        "/mis_ofertas - Ver mis ofertas\n"
        "/buscar - Buscar ofertas\n"
        "/valoraciones - Ver mi puntuacion\n"
        "/config - Ajustes\n"
        "/admin - Panel admin\n\n"
        "Condiciones:\n"
        "Respete a otros usuarios. Las ofertas fraudulentas seran eliminadas."
    )
    await update.message.reply_text(texto)

async def login(update, context):
    await update.callback_query.answer()
    estados[update.effective_user.id] = {"estado": "login_nombre"}
    await update.callback_query.edit_message_text("Escribe tu nombre:")

async def registro(update, context):
    await update.callback_query.answer()
    estados[update.effective_user.id] = {"estado": "registro_nombre"}
    await update.callback_query.edit_message_text("Elige un nombre de usuario:")

async def handle_mensaje(update, context):
    uid = update.effective_user.id
    texto = update.message.text.strip()
    est = estados.get(uid, {}).get("estado")

    if est == "login_nombre":
        estados[uid]["nombre"] = texto
        estados[uid]["estado"] = "login_pass"
        await update.message.reply_text("Escribe tu contrasena:")
    elif est == "login_pass":
        nombre = estados[uid]["nombre"]
        u = db.verificar_login(nombre, texto, uid)
        if u:
            sesiones[uid] = u["id"]
            estados.pop(uid, None)
            await update.message.reply_text(f"Bienvenido {nombre}")
        else:
            await update.message.reply_text("No se pudo iniciar sesion.")
    elif est == "registro_nombre":
        if db.get_usuario_by_nombre(texto):
            await update.message.reply_text("Ese nombre ya existe.")
        else:
            estados[uid]["nombre"] = texto
            estados[uid]["estado"] = "registro_pass"
            await update.message.reply_text("Elige una contrasena:")
    elif est == "registro_pass":
        nombre = estados[uid]["nombre"]
        db.registrar_usuario(uid, nombre, texto)
        u = db.get_usuario(uid)
        if u:
            sesiones[uid] = u["id"]
            estados.pop(uid, None)
            await update.message.reply_text(f"Registrado como {nombre}")
        else:
            await update.message.reply_text("Error al registrar. Intenta de nuevo.")
    elif est == "publicar_categoria":
        estados[uid]["categoria"] = texto
        estados[uid]["estado"] = "publicar_producto"
        await update.message.reply_text("Producto:")
    elif est == "publicar_producto":
        estados[uid]["producto"] = texto
        estados[uid]["estado"] = "publicar_cantidad"
        await update.message.reply_text("Cantidad:")
    elif est == "publicar_cantidad":
        estados[uid]["cantidad"] = texto
        estados[uid]["estado"] = "publicar_precio"
        await update.message.reply_text("Precio:")
    elif est == "publicar_precio":
        estados[uid]["precio"] = texto
        estados[uid]["estado"] = "publicar_moneda"
        await update.message.reply_text("Moneda (CUP o USD):")
    elif est == "publicar_moneda":
        estados[uid]["moneda"] = texto.upper()
        estados[uid]["estado"] = "publicar_desc"
        await update.message.reply_text("Descripcion:")
    elif est == "publicar_desc":
        e = estados.pop(uid)
        db.crear_oferta(
            sesiones[uid],
            e["categoria"], e["producto"], e["cantidad"],
            e["precio"], e["moneda"], texto
        )
        await update.message.reply_text("Oferta publicada.")
    elif est == "buscar":
        ofertas = db.buscar_ofertas(texto)
        if not ofertas:
            await update.message.reply_text("Sin resultados.")
            return
        teclado = []
        for o in ofertas[:20]:
            teclado.append([InlineKeyboardButton(
                f"{o['producto']} - {o['precio']} {o['moneda']}",
                callback_data=f"ver_{o['id']}"
            )])
        await update.message.reply_text("Resultados:", reply_markup=InlineKeyboardMarkup(teclado))

async def publicar(update, context):
    uid = update.effective_user.id
    if uid not in sesiones:
        await update.message.reply_text("Inicia sesion primero.")
        return
    categorias = db.execute("SELECT nombre FROM categorias").get("rows", [])
    teclado = [[InlineKeyboardButton(c[0], callback_data=f"cat_{c[0]}")] for c in categorias]
    await update.message.reply_text("Elige categoria:", reply_markup=InlineKeyboardMarkup(teclado))

async def boton(update, context):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = update.effective_user.id

    if data == "login":
        await login(update, context)
    elif data == "registro":
        await registro(update, context)
    elif data == "ayuda":
        await ayuda(update, context)
    elif data.startswith("cat_"):
        estados[uid] = {"estado": "publicar_categoria", "categoria": data[4:]}
        await q.edit_message_text("Producto:")
    elif data.startswith("ver_"):
        oferta_id = int(data[4:])
        oferta = db.get_oferta(oferta_id)
        if not oferta:
            await q.edit_message_text("Oferta no encontrada.")
            return
        vendedor = db.get_usuario_by_id(oferta["usuario_id"])
        texto = (
            f"{oferta['producto']}\n"
            f"Cantidad: {oferta['cantidad']}\n"
            f"Precio: {oferta['precio']} {oferta['moneda']}\n"
            f"Descripcion: {oferta['descripcion']}\n"
            f"Vendedor: {'Anonimo' if vendedor['anonimo'] else vendedor['nombre']}"
        )
        teclado = [[InlineKeyboardButton("Contactar vendedor", callback_data=f"cont_{oferta_id}")]]
        await q.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(teclado))
    elif data.startswith("cont_"):
        oferta_id = int(data[5:])
        oferta = db.get_oferta(oferta_id)
        db.crear_contacto(oferta_id, sesiones[uid], oferta["usuario_id"])
        await q.edit_message_text("Solicitud enviada al vendedor.")

async def mis_ofertas(update, context):
    uid = update.effective_user.id
    if uid not in sesiones:
        await update.message.reply_text("Inicia sesion.")
        return
    ofertas = db.mis_ofertas(sesiones[uid])
    if not ofertas:
        await update.message.reply_text("No tienes ofertas.")
        return
    texto = ""
    for o in ofertas:
        texto += f"[{o['estado']}] {o['producto']} - {o['precio']} {o['moneda']}\n"
    await update.message.reply_text(texto)

async def buscar(update, context):
    uid = update.effective_user.id
    if uid not in sesiones:
        await update.message.reply_text("Inicia sesion.")
        return
    estados[uid] = {"estado": "buscar"}
    await update.message.reply_text("Escribe que buscas:")

def main():
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("publicar", publicar))
    app.add_handler(CommandHandler("mis_ofertas", mis_ofertas))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CallbackQueryHandler(boton))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mensaje))
    app.run_polling()

if __name__ == "__main__":
    db.init_db()
    main()
