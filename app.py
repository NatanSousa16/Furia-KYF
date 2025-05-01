import os
import base64
import re
import unicodedata
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image
from pdf2image import convert_from_path
import tempfile

# Carregar variáveis do .env
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def normalize_text(text):
    """Normaliza texto removendo acentos e convertendo para minúsculas"""
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode()
    return text.lower().strip()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def encode_image(image_path):
    """Codifica a imagem em base64"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def process_file(filepath):
    """Processa diferentes tipos de arquivo"""
    if filepath.lower().endswith('.pdf'):
        with tempfile.TemporaryDirectory() as temp_dir:
            images = convert_from_path(filepath, dpi=300, output_folder=temp_dir, 
                                     first_page=1, last_page=1, fmt='jpeg')
            if not images:
                raise ValueError("Falha ao converter PDF")
            temp_img_path = os.path.join(temp_dir, 'temp_page.jpg')
            images[0].save(temp_img_path, 'JPEG')
            return temp_img_path
    return filepath

def mask_cpf(cpf):
    """Mascara o CPF para exibição"""
    return f"{cpf[:3]}.***.***-{cpf[-2:]}" if len(cpf) == 11 else cpf

def validate_cpf(cpf):
    """Valida o formato básico do CPF"""
    return re.match(r"^\d{11}$", cpf) is not None

@app.route('/', methods=['GET', 'POST'])
def form():
    status_emoji = {
        "VALIDADO": "✅ DOCUMENTO VALIDADO",
        "NÃO VALIDADO": "❌ DOCUMENTO NÃO VALIDADO",
        "INDETERMINADO": "⚠️ STATUS INDETERMINADO"
    }

    if request.method == 'POST':
        # Coletar dados do formulário
        cpf = request.form['cpf'].strip().replace('.', '').replace('-', '')
        
        # Inicializa a variável link_perfil
        link_perfil = request.form.get('link_perfil', '').strip()

        # Verifica se o CPF é válido
        if not validate_cpf(cpf):
            form_data = {
                'resultado_link': "🚨 CPF inválido"
            }
            return render_template('error.html', message="CPF inválido"), 400

        # Normalizar nome do usuário
        form_data = {
            'nome': request.form['nome'].strip(),
            'email': request.form['email'].strip(),
            'endereco': request.form['endereco'].strip(),
            'cpf': mask_cpf(cpf),
            'interesses': request.form.getlist('interesse'),
            'atividades': request.form['atividades'].strip(),
            'eventos': request.form['eventos'].strip(),
            'compras': request.form['compras'].strip(),
            'resultado_ia': "Nenhum documento enviado.",
            'link_perfil': link_perfil,  # Adicionando o link_perfil no form_data
            'resultado_link': "Nenhum link enviado."
        }

        if link_perfil:
            try:
                # Requisição para a IA analisar o link
                link_response = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[ 
                        {
                            "role": "system",
                            "content": (
                                "Você é uma IA que avalia perfis online. "
                                "Analise o conteúdo de um link de perfil de e-sports ou qualquer outro conteúdo online que "
                                "possa estar relacionado a organizações como a FURIA, times de e-sports ou interesses gerais em e-sports.\n"
                                "Responda da seguinte forma:\n"
                                "STATUS: Relevante/Irrelevante\n"
                                "JUSTIFICATIVA: [explicação clara sobre a relação com a FURIA ou e-sports]"
                            )
                        },
                        {
                            "role": "user",
                            "content": f"Link do perfil: {link_perfil}\nInteresses: {', '.join(form_data['interesses'])}"
                        }
                    ],
                    temperature=0.2,
                    max_tokens=200
                )

                raw_link_resp = link_response.choices[0].message.content.strip()
                status_link = "INDETERMINADO"
                justificativa_link = "Resposta não interpretada"

                # Verificar se a resposta contém a estrutura de status e justificativa
                if "STATUS:" in raw_link_resp and "JUSTIFICATIVA:" in raw_link_resp:
                    status_match = re.search(r"STATUS:\s*(Relevante|Irrelevante)", raw_link_resp, re.IGNORECASE)
                    justificativa_match = re.search(r"JUSTIFICATIVA:\s*(.+)", raw_link_resp, re.DOTALL)

                    if status_match and justificativa_match:
                        status_link = status_match.group(1).capitalize()
                        justificativa_link = justificativa_match.group(1).strip()

                form_data['resultado_link'] = (
                    f"{'✅ Perfil Relevante' if status_link == 'Relevante' else '❌ Perfil Irrelevante'}\n"
                    f"Justificativa: {justificativa_link}"
                )

            except Exception as e:
                form_data['resultado_link'] = f"🚨 ERRO: {str(e)}"
                app.logger.error(f"Erro na análise do link: {str(e)}")

        documento = request.files['documento']
        if documento and allowed_file(documento.filename):
            filename = secure_filename(documento.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            documento.save(filepath)

            try:
                # Processar arquivo (PDF ou imagem)
                processed_path = process_file(filepath)
                img = Image.open(processed_path)
                img.thumbnail((1024, 1024))
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(processed_path)
                base64_image = encode_image(processed_path)

                # Chamada à API para validar o documento
                response = client.chat.completions.create(
    model="gpt-4-turbo",
    messages=[
        {
            "role": "system",
            "content": (
                "Valide documentos seguindo estas regras:\n"
                "1. Ignore acentos e diferenças de caixa\n"
                "2. Invalide apenas por diferenças reais\n"
                "Formato resposta:\n"
                "STATUS: VALIDADO/NÃO VALIDADO\n"
                "JUSTIFICATIVA: [motivo técnico]"
            )
        },
        {
            "role": "user", 
            "content": [
                {
                    "type": "text",
                    "text": f"Verifique se o documento contém: {form_data['nome']}"  # Correção aqui
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        }
    ],
    temperature=0.0,
    max_tokens=150
)

                # Processar resposta
                raw_response = response.choices[0].message.content.strip()
                status = "INDETERMINADO"
                justificativa = "Resposta não interpretada"

                # Verificar a resposta da IA
                if "STATUS:" in raw_response and "JUSTIFICATIVA:" in raw_response:
                    status_match = re.search(r"STATUS:\s*(VALIDADO|NÃO VALIDADO|NAO VALIDADO)", raw_response, re.IGNORECASE)
                    justificativa_match = re.search(r"JUSTIFICATIVA:\s*(.+)", raw_response, re.DOTALL)

                    if status_match and justificativa_match:
                        status = status_match.group(1).upper()
                        status = "NÃO VALIDADO" if "NAO" in status else status
                        justificativa = justificativa_match.group(1).strip()

                form_data['resultado_ia'] = (
                    f"{status_emoji.get(status, status_emoji['INDETERMINADO'])}\n"
                    f"Justificativa: {justificativa}"
                )

            except Exception as e:
                form_data['resultado_ia'] = f"🚨 ERRO: {str(e)}"
                app.logger.error(f"Erro: {str(e)}")

        return render_template('result.html', data=form_data)
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
