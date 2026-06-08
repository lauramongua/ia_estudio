from flask import Flask, render_template, request, jsonify
import os
from werkzeug.utils import secure_filename
from document_service import extraer_texto_pdf
from ia_service import generar_examen_ia
import json
import datetime
import requests

app = Flask(__name__)

# ── Rutas de navegación ──────────────────────────────────────────────────────

@app.route('/')
def index():
    hist_path = os.path.join(os.getcwd(), 'historico.json')
    total_examenes = 0
    if os.path.isfile(hist_path):
        try:
            with open(hist_path, encoding='utf-8') as f:
                total_examenes = len(json.load(f))
        except Exception:
            pass
    return render_template('index.html', seccion='inicio', total_examenes=total_examenes)

@app.route('/documentos')
def documentos():
    return render_template('index.html', seccion='documentos')

@app.route('/crear-examen')
def crear_examen_view():
    return render_template('index.html', seccion='crear_examen', modelos=obtener_modelos_ollama())

@app.route('/historial')
def historial():
    hist_path = os.path.join(os.getcwd(), 'historico.json')
    historico = []
    if os.path.isfile(hist_path):
        try:
            with open(hist_path, encoding='utf-8') as f:
                historico = json.load(f)
        except Exception:
            pass
    return render_template('index.html', seccion='historial', historico=historico)


def obtener_modelos_ollama():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            return [m['name'] for m in r.json().get('models', [])]
    except Exception as e:
        print(f"Error conectando con Ollama: {e}")
    return []


# ── API: Historial ───────────────────────────────────────────────────────────

@app.route('/api/historial/<int:index>', methods=['GET'])
def get_historial_entry(index):
    try:
        hist_path = os.path.join(os.getcwd(), 'historico.json')
        if not os.path.isfile(hist_path):
            return jsonify({"status": "success", "entry": None})
        with open(hist_path, encoding='utf-8') as f:
            historial = json.load(f)
        if index < 0 or index >= len(historial):
            return jsonify({"status": "success", "entry": None})
        return jsonify({"status": "success", "entry": historial[index]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


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
        removed = historial.pop(index)
        with open(hist_path, 'w', encoding='utf-8') as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "success", "removed": removed})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/historial/<int:index>/seleccion', methods=['POST'])
def save_historial_seleccion(index):
    # NOTA: En el original este método estaba mal indentado DENTRO de generar_tips()
    # y Flask nunca lo registraba. Aquí está correctamente en el nivel raíz.
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
        preguntas = historial[index].get('examen', {}).get('preguntas', [])
        for sel in selections:
            idx = sel.get('pregunta_idx')
            resp = sel.get('respuesta')
            if isinstance(idx, int) and 0 <= idx < len(preguntas):
                preguntas[idx]['seleccion_usuario'] = resp
        with open(hist_path, 'w', encoding='utf-8') as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── API: Tips IA ─────────────────────────────────────────────────────────────

@app.route('/api/generar-tips', methods=['POST'])
def generar_tips():
    try:
        data = request.get_json()
        examen = data.get('examen') if isinstance(data, dict) else None
        if not examen or 'preguntas' not in examen:
            return jsonify({"status": "error", "message": "Examen inválido."}), 400
        # Devuelve tips sobre las preguntas falladas (o las 3 primeras si no hay selección)
        falladas = [p for p in examen['preguntas']
                    if not p.get('seleccion_usuario') or
                    p.get('seleccion_usuario', '').upper() != p.get('opcion_correcta', '').upper()]
        objetivos = falladas[:5] if falladas else examen['preguntas'][:3]
        tips = [f"Repasa el concepto de: {p.get('enunciado', '')}" for p in objetivos]
        return jsonify({"status": "success", "tips": tips})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── API: Documentos ──────────────────────────────────────────────────────────

@app.route('/api/listar-documentos')
def listar_documentos_api():
    upload_folder = os.path.join(os.getcwd(), 'uploads')
    if not os.path.isdir(upload_folder):
        return jsonify([])
    return jsonify([f for f in os.listdir(upload_folder) if f.lower().endswith('.pdf')])


# ── API: Generar examen ──────────────────────────────────────────────────────

@app.route('/api/generar-examen', methods=['POST'])
def procesar_examen():
    try:
        materia      = request.form.get('titulo_examen', 'Materia General')
        dificultad   = request.form.get('dificultad', 'Media')
        modelo       = request.form.get('modelo_ollama', 'gemma2:9b')
        num_preguntas = int(request.form.get('num_preguntas', 5))

        upload_folder = os.path.join(os.getcwd(), 'uploads')
        os.makedirs(upload_folder, exist_ok=True)

        textos = []

        # 1) PDFs subidos en el formulario
        for pdf_file in request.files.getlist('pdf'):
            if not pdf_file or pdf_file.filename == '':
                continue
            if not pdf_file.filename.lower().endswith('.pdf'):
                raise ValueError(f"Archivo inválido: {pdf_file.filename}")
            filename = secure_filename(pdf_file.filename)
            path = os.path.join(upload_folder, filename)
            pdf_file.save(path)
            textos.append(extraer_texto_pdf(path))

        # 2) PDFs ya guardados seleccionados con checkbox
        for name in request.form.getlist('pdf_existing'):
            path = os.path.join(upload_folder, secure_filename(name))
            if not os.path.isfile(path):
                raise ValueError(f"Archivo no encontrado: {name}")
            textos.append(extraer_texto_pdf(path))

        if not textos:
            raise ValueError("No se proporcionó ningún PDF para generar el examen.")

        texto_extraido = "\n".join(textos)
        print(f"[Web] Generando examen · modelo={modelo} · preguntas={num_preguntas}")

        respuesta_json = generar_examen_ia(texto_extraido, materia, dificultad, modelo, num_preguntas)
        datos_examen   = json.loads(respuesta_json)

        # Guardar en historico.json
        hist_path = os.path.join(os.getcwd(), 'historico.json')
        historial = []
        if os.path.isfile(hist_path):
            try:
                with open(hist_path, encoding='utf-8') as f:
                    historial = json.load(f)
            except Exception:
                historial = []

        entry = {
            "timestamp":    datetime.datetime.now().isoformat(),
            "nombre_examen": materia,
            "materia":      materia,
            "dificultad":   dificultad,
            "modelo":       modelo,
            "examen":       datos_examen
        }
        historial.append(entry)

        with open(hist_path, 'w', encoding='utf-8') as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)

        new_index = len(historial) - 1
        return jsonify({"status": "success", "examen": datos_examen, "hist_index": new_index})

    except Exception as e:
        print(f"[Error Web] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
