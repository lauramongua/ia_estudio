from flask import Flask, render_template, request, jsonify
import os
from werkzeug.utils import secure_filename
from document_service import extraer_texto_pdf
from ia_service import generar_examen_ia
import json
import datetime
import requests

app = Flask(__name__)

# --- Rutas de Navegación (GET) ---
@app.route('/')
def index():
    # Determine how many exams have been saved in historial.json
    hist_path = os.path.join(os.getcwd(), 'historico.json')
    total_examenes = 0
    if os.path.isfile(hist_path):
        try:
            with open(hist_path, encoding='utf-8') as f:
                historial = json.load(f)
                total_examenes = len(historial)
        except Exception:
            total_examenes = 0
    return render_template('index.html', seccion='inicio', total_examenes=total_examenes)

@app.route('/documentos')
def documentos():
    return render_template('index.html', seccion='documentos')

@app.route('/crear-examen')
def crear_examen_view():
    lista_modelos = obtener_modelos_ollama()
    return render_template('index.html', seccion='crear_examen', modelos=lista_modelos)

import json, datetime, os

@app.route('/historial')
def historial():
    # Load saved exams from a JSON file (if exists)
    hist_path = os.path.join(os.getcwd(), 'historico.json')
    if os.path.isfile(hist_path):
        try:
            with open(hist_path, encoding='utf-8') as f:
                historico = json.load(f)
        except Exception:
            historico = []
    else:
        historico = []
    return render_template('index.html', seccion='historial', historico=historico)

def obtener_modelos_ollama():
    try:
        # Hacemos la petición a la API de Ollama
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            datos = response.json()
            # Devolvemos la lista de nombres
            return [modelo['name'] for modelo in datos['models']]
    except Exception as e:
        print(f"Error al conectar con Ollama: {e}")
        return [] # Retorna vacío si hay error

# API to retrieve a specific exam entry from historial by its index
@app.route('/api/historial/<int:index>', methods=['GET'])
def get_historial_entry(index):
    try:
        hist_path = os.path.join(os.getcwd(), 'historico.json')
        # If the file does not exist, treat as empty historial
        if not os.path.isfile(hist_path):
            return jsonify({"status": "success", "entry": None})
        with open(hist_path, encoding='utf-8') as f:
            historial = json.load(f)
        # If the list is empty or index out of range, also return null entry
        if index < 0 or index >= len(historial):
            return jsonify({"status": "success", "entry": None})
        return jsonify({"status": "success", "entry": historial[index]})
    except Exception as e:
        print(f"[Error API historial] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Delete a specific exam entry from the historial file
@app.route('/api/historial/<int:index>', methods=['DELETE'])
def delete_historial_entry(index):
    try:
        hist_path = os.path.join(os.getcwd(), 'historico.json')
        if not os.path.isfile(hist_path):
            return jsonify({"status": "error", "message": "Historial no encontrado."}), 404
        with open(hist_path, encoding='utf-8') as f:
            historial = json.load(f)
        if index < 0 or index >= len(historial):
            return jsonify({"status": "error", "message": "Índice fuera de rango."}), 400
        removed_entry = historial.pop(index)
        with open(hist_path, 'w', encoding='utf-8') as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "success", "removed": removed_entry})
    except Exception as e:
        print(f"[Error API borrar historial] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Placeholder endpoint to generate tips for an exam using IA (currently returns static suggestions)
@app.route('/api/generar-tips', methods=['POST'])
def generar_tips():
    try:
        data = request.get_json()
        examen = data.get('examen') if isinstance(data, dict) else None
        # Simple placeholder: list first three question titles as tips
        if not examen or 'preguntas' not in examen:
            return jsonify({"status": "error", "message": "Examen inválido."}), 400
        preguntas = examen['preguntas'][:3]
        tips = [f"Revisa la pregunta: {p.get('enunciado', '')}" for p in preguntas]
        return jsonify({"status": "success", "tips": tips})
    except Exception as e:
        print(f"[Error generar tips] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    # Save user selections for a specific exam entry in the historial
    @app.route('/api/historial/<int:index>/seleccion', methods=['POST'])
    def save_historial_seleccion(index):
        try:
            hist_path = os.path.join(os.getcwd(), 'historico.json')
            if not os.path.isfile(hist_path):
                return jsonify({"status": "error", "message": "Historial no encontrado."}), 404
            with open(hist_path, encoding='utf-8') as f:
                historial = json.load(f)
            if index < 0 or index >= len(historial):
                return jsonify({"status": "error", "message": "Índice fuera de rango."}), 400
            data = request.get_json()
            selections = data.get('selections', []) if isinstance(data, dict) else []
            # Update each pregunta with the user's selected answer
            for sel in selections:
                idx = sel.get('pregunta_idx')
                resp = sel.get('respuesta')
                if isinstance(idx, int) and 0 <= idx < len(historial[index]['examen'].get('preguntas', [])):
                    historial[index]['examen']['preguntas'][idx]['seleccion_usuario'] = resp
            # Write back updated historial
            with open(hist_path, 'w', encoding='utf-8') as f:
                json.dump(historial, f, ensure_ascii=False, indent=2)
            return jsonify({"status": "success"})
        except Exception as e:
            print(f"[Error guardando selección historial] {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

# API que devuelve la lista de PDFs guardados en la carpeta uploads
@app.route('/api/listar-documentos')
def listar_documentos_api():
    upload_folder = os.path.join(os.getcwd(), 'uploads')
    if not os.path.isdir(upload_folder):
        return jsonify([])
    archivos = [f for f in os.listdir(upload_folder) if f.lower().endswith('.pdf')]
    return jsonify(archivos)

# --- Ruta única para procesar el formulario (POST) ---
@app.route('/api/generar-examen', methods=['POST'])
def procesar_examen():
    try:
        # Obtener datos del formulario y los archivos PDF
        materia = request.form.get('titulo_examen', 'Materia General')
        dificultad = request.form.get('dificultad', 'Media')
        modelo = request.form.get('modelo_ollama', 'gemma2:9b')
        num_preguntas = int(request.form.get('num_preguntas', 5))

        # Recolectar PDFs subidos y/o PDFs ya almacenados en la carpeta uploads
        upload_folder = os.path.join(os.getcwd(), 'uploads')
        os.makedirs(upload_folder, exist_ok=True)

        textos = []
        # 1) Archivos enviados en el request (puede ser vacío)
        pdf_files = request.files.getlist('pdf') if 'pdf' in request.files else []
        for pdf_file in pdf_files:
            # Si no se seleccionó ningún archivo, simplemente lo ignoramos
            if not pdf_file or pdf_file.filename == '':
                continue
            if not pdf_file.filename.lower().endswith('.pdf'):
                raise ValueError(f"Archivo inválido: {pdf_file.filename}. Se requiere un PDF.")
            filename = secure_filename(pdf_file.filename)
            file_path = os.path.join(upload_folder, filename)
            pdf_file.save(file_path)
            textos.append(extraer_texto_pdf(file_path))

        # 2) Nombres de PDFs previamente guardados enviados como campo oculto
        existing_names = request.form.getlist('pdf_existing')
        for name in existing_names:
            safe_name = secure_filename(name)
            file_path = os.path.join(upload_folder, safe_name)
            if not os.path.isfile(file_path):
                raise ValueError(f"Archivo existente no encontrado: {name}")
            textos.append(extraer_texto_pdf(file_path))

        if not textos:
            raise ValueError("No se proporcionó ningún PDF para generar el examen.")

        # Concatenar todo el texto extraído
        texto_extraido = "\n".join(textos)

        print(f"[Web] Generando examen con modelo {modelo} a partir de {len(pdf_files)} PDF(s), {num_preguntas} preguntas.")
        respuesta_ia_json = generar_examen_ia(texto_extraido, materia, dificultad, modelo, num_preguntas)

        datos_examen = json.loads(respuesta_ia_json)
        # Guardar examen en historial (historico.json en la raíz del proyecto)
        try:
            hist_path = os.path.join(os.getcwd(), 'historico.json')
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "materia": materia,
                "dificultad": dificultad,
                "modelo": modelo,
                "examen": datos_examen
            }
            if os.path.isfile(hist_path):
                with open(hist_path, 'r', encoding='utf-8') as f:
                    historial = json.load(f)
            else:
                historial = []
            historial.append(entry)
            with open(hist_path, 'w', encoding='utf-8') as f:
                json.dump(historial, f, ensure_ascii=False, indent=2)
        except Exception as e_save:
            print(f"[Error guardando historial] {e_save}")

        # Determine the index of this newly saved exam entry
        new_index = len(historial) - 1 if isinstance(historial, list) else 0
        return jsonify({"status": "success", "examen": datos_examen, "hist_index": new_index})

    except Exception as e:
        print(f"[Error Web] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)