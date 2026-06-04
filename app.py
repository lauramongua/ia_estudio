from flask import Flask, render_template, request, jsonify

from document_service import extraer_texto_pdf
from ia_service import generar_examen_ia
import json

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/crear-examen', methods=['POST'])
def crear_examen():
    try: 
        materia = request.form.get('titulo_examen', 'Materia General')
        dificultad = request.form.get('dificultad', 'Media')
        modelo = request.form.get('modelo_ollama', 'gemma4:latest')

        texto_extraido = "Texto de prueba temporal simulado en PDF de la materia."

        print(f"[Web] Enviando texto a Ollama con el modelo {modelo}...")
        respuesta_ia_json = generar_examen_ia(texto_extraido, materia, dificultad, modelo)

        # Convertimos la respuesta en un diccionario
        datos_examen = json.loads(respuesta_ia_json)
        
        print("[Web] ¡Examen generado con éxito!")
        # (Próximamente aquí llamaremos a database.py para guardar el examen)
        
        return jsonify({"status": "success", "examen": datos_examen})

    except Exception as e:
        print(f"[Error Web] Ha ocurrido un problema: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Arrancamos el servidor en el puerto 5000
    app.run(debug=True, port=5000)