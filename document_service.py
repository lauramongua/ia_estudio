from pypdf import PdfReader

def extraer_texto_pdf(ruta_archivo):
    lector = PdfReader(ruta_archivo)
    texto_completo = ""

    for pagina in lector.pages:
        texto_pagina = pagina.extract_text()
        texto_completo+= texto_pagina

    return texto_completo