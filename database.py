import sqlite3



def conectar_db():
    """"Abre la conexion con el archivo de la base de datos."""
    conexion = sqlite3.connect("estudio")
    conexion.execute("PRAGMA foreign_keys = ON;")
    return conexion

def inicializar_base_datos():
    """Crea las tablas necesarias si no existen en el sistema."""
    conexion = conectar_db()

    #El cursor es el objeto que permite ejecutar comandos SQL
    cursor = conexion.cursor()

    #TABLA DE USUARIOS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        correo TEXT UNIQUE NOT NULL
    );
    """)

    #TABLA DE DOCUMENTOS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documentos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        nombre_archivo TEXT NOT NULL,
        ruta_archivo TEXT NOT NULL,
        fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    #TABLA DE EXAMENES
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS examenes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        materia TEXT NOT NULL,
        dificultad TEXT NOT NULL,
        nota_final REAL,
        fecha_realizado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );
    """)

    #TABLA HISTORIAL DE PREGUNTAS(Detalle de cada pregunta del examen)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS preguntas_historial(
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        examen_id INTEGER,
        enunciado_pregunta TEXT NOT NULL,
        opcion_correcta TEXT NOT NULL,
        respuesta_usuario TEXT,
        es_correcta INTEGER, 
        explicacion TEXT,
        FOREIGN KEY (examen_id) REFERENCES examenes(id) ON DELETE CASCADE
    );
    """)

    conexion.commit()

    conexion.close()
    print("[Base de Datos] Tablas inicializadas correctamente.")

def guardar_examen(usuario_id, materia, dificultad, nota_final):
    conexion = conectar_db()

    cursor = conexion.cursor()

    cursor.execute("""
        INSERT INTO examenes(usuario_id, materia, dificultad, nota_final) VALUES (?, ?, ?, ?);
    """, (usuario_id, materia, dificultad, nota_final))

    conexion.commit()
    id_examen = cursor.lastrowid
    cursor.close()
    return id_examen

def guardar_pregunta(examen_id, enunciado, opcion_correcta, respuesta_usuario, es_correcta, explicacion):
    conexion = conectar_db()

    cursor = conexion.cursor()

    cursor.execute("""
        INSERT INTO preguntas_historial (examen_id, enunciado_pregunta, opcion_correcta, respuesta_usuario, es_correcta, explicacion) VALUES (?, ?, ?, ?, ?, ?);
                   """, (examen_id, enunciado, opcion_correcta, respuesta_usuario, es_correcta, explicacion))

    conexion.commit()
    conexion.close()


if __name__ == "__main__":
    inicializar_base_datos()