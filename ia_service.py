import ollama

def generar_examen_ia(texto_documento, materia, dificultad, modelo_elegido):
    instrucciones = f"""
    Actúa como un profesor experto en la materia de {materia}.
    Tu tarea es analizar el siguiente texto de estudio y generar un examen tipo test riguroso de nivel de dificultad {dificultad}.
    
    TEXTO DE ESTUDIO:
    {texto_documento}
    
    REGLAS ESTRICTAS DE RESPUESTA:
    1. Debes generar exactamente 5 preguntas de opción múltiple basadas exclusivamente en el texto proporcionado.
    2. Cada pregunta debe tener exactamente 3 opciones de respuesta (A, B, C).
    3. Tu respuesta debe ser OBLIGATORIAMENTE un objeto JSON válido. No incluyas introducciones, ni saludos, ni bloques de código markdown como ```json. Solo el JSON puro.
    
    ESTRUCTURA EXACTA DEL JSON QUE DEBES DEVOLVER:
    {{
        "materia": "{materia}",
        "dificultad": "{dificultad}",
        "preguntas": [
            {{
                "enunciado": "Escribe aquí la pregunta clara y directa",
                "opciones": {{
                    "A": "Primera opción",
                    "B": "Segunda opción",
                    "C": "Tercera opción"
                }},
                "opcion_correcta": "A",
                "explicacion": "Explicación detallada de por qué esa opción es la correcta basada en el texto."
            }}
        ]
    }}
    """
    respuesta = ollama.chat(
        model=modelo_elegido,
        format='json',
        messages=[
            {
                'role': 'user',
                'content' : instrucciones,
            },
        ],
    )

    return respuesta['message']['content']

if __name__ == "__main__":
    # Vamos a inventar unos datos de prueba falsos para ver si funciona
    texto_prueba = "La fotosíntesis es el proceso mediante el cual las plantas transforman el agua y el dióxido de carbono en glucosa y oxígeno utilizando la luz del sol. Ocurre en los cloroplastos."
    materia_prueba = "Biología"
    dificultad_prueba = "Fácil"
    
    # Ponemos el nombre EXACTO de lo que tienes en tu 'ollama list'
    modelo_prueba = "gemma4:latest" 
    
    print(f"[IA] Conectando con Ollama usando el modelo {modelo_prueba}... Espera un momento.")
    
    try:
        resultado = generar_examen_ia(texto_prueba, materia_prueba, dificultad_prueba, modelo_prueba)
        print("\n[IA] ¡Examen generado con éxito! Aquí tienes el JSON recibido:")
        print(resultado)
    except Exception as e:
        print(f"\n[Error] Algo ha fallado al conectar con Ollama: {e}")

