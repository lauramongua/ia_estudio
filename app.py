from flask import Flask, render_template, request, jsonify
import os
from werkzeug.utils import secure_filename
from document_service import extraer_texto_pdf
from ia_service import generar_examen_ia
import json
import datetime
import requests
import re

app = Flask(__name__)

# ── Rutas de navegación ──────────────────────────────────────────────────────

@app.route('/')
def index():
    hist_path = os.path.join(os.getcwd(), 'historico.json')
    total_examenes = 0
    avg_score = None
    if os.path.isfile(hist_path):
        try:
            with open(hist_path, encoding='utf-8') as f:
                historial = json.load(f)
            total_examenes = len(historial)
            notas = []
            for entry in historial:
                preguntas = entry.get('examen', {}).get('preguntas', [])
                respondidas = [p for p in preguntas if p.get('seleccion_usuario')]
                if not preguntas or not respondidas:
                    continue
                correctas = sum(
                    1 for p in preguntas
                    if p.get('seleccion_usuario', '').strip().upper()
                    == p.get('opcion_correcta', '').strip().upper()
                )
                notas.append((correctas / len(preguntas)) * 10)
            if notas:
                avg_score = round(sum(notas) / len(notas), 1)
        except Exception:
            pass
    return render_template('index.html', seccion='inicio',
                           total_examenes=total_examenes, avg_score=avg_score)
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

@app.route('/api/repetir-examen/<int:index>', methods=['POST'])
def repetir_examen(index):
    try:
        hist_path = os.path.join(os.getcwd(), 'historico.json')
        if not os.path.isfile(hist_path):
            return jsonify({"status": "error", "message": "Historial no encontrado."}), 404
        with open(hist_path, encoding='utf-8') as f:
            historial = json.load(f)
        if index < 0 or index >= len(historial):
            return jsonify({"status": "error", "message": "Índice fuera de rango."}), 400

        entry = historial[index]
        texto_pdf = entry.get('texto_pdf', '')
        if not texto_pdf:
            return jsonify({"status": "error", "message": "Este examen no tiene texto guardado. Genera uno nuevo subiendo el PDF."}), 400

        data = request.get_json() or {}
        materia      = data.get('materia',      entry.get('materia', 'Materia General'))
        dificultad   = data.get('dificultad',   entry.get('dificultad', 'Media'))
        modelo       = data.get('modelo',       entry.get('modelo', 'gemma2:9b'))
        num_preguntas = int(data.get('num_preguntas', len(entry.get('examen', {}).get('preguntas', [])) or 5))

        respuesta_json = generar_examen_ia(texto_pdf, materia, dificultad, modelo, num_preguntas)

        texto = respuesta_json.strip()
        if texto.startswith("```"):
            texto = re.sub(r'^```(?:json)?\s*', '', texto)
            texto = re.sub(r'\s*```$', '', texto)
        start, end = texto.find('{'), texto.rfind('}')
        if start != -1 and end != -1:
            texto = texto[start:end+1]
        datos_examen = json.loads(texto)

        new_entry = {
            "timestamp":     datetime.datetime.now().isoformat(),
            "nombre_examen": materia,
            "materia":       materia,
            "dificultad":    dificultad,
            "modelo":        modelo,
            "texto_pdf":     texto_pdf,
            "examen":        datos_examen
        }
        historial.append(new_entry)
        with open(hist_path, 'w', encoding='utf-8') as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)

        return jsonify({"status": "success", "examen": datos_examen, "hist_index": len(historial) - 1})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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

@app.route('/api/eliminar-documento/<string:filename>', methods=['DELETE'])
def eliminar_documento(filename):
    try:
        upload_folder = os.path.join(os.getcwd(), 'uploads')
        safe_name = secure_filename(filename)
        if not safe_name or not safe_name.lower().endswith('.pdf'):
            return jsonify({"status": "error", "message": "Archivo inválido."}), 400
        path = os.path.join(upload_folder, safe_name)
        if not os.path.isfile(path):
            return jsonify({"status": "error", "message": "Archivo no encontrado."}), 404
        os.remove(path)
        return jsonify({"status": "success", "removed": safe_name})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
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
        # Limpiar respuesta: quitar bloques markdown y texto fuera del JSON
        texto = respuesta_json.strip()
        # Eliminar ```json ... ``` o ``` ... ```
        if texto.startswith("```"):
            texto = re.sub(r'^```(?:json)?\s*', '', texto)
            texto = re.sub(r'\s*```$', '', texto)
        # Extraer solo el objeto JSON principal (desde { hasta la última })
        start = texto.find('{')
        end = texto.rfind('}')
        if start != -1 and end != -1:
            texto = texto[start:end+1]
        datos_examen = json.loads(texto)

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
            "texto_pdf":     texto_extraido, 
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
