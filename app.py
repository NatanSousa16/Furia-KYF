import os
import base64
import re
import unicodedata
from flask import Flask, render_template, request, url_for, session, jsonify, redirect
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image
from pdf2image import convert_from_path
import tempfile
from authlib.integrations.flask_client import OAuth
from flask_openid import OpenID
import mysql.connector


# Carregar variáveis do .env
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.debug = True
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="FuriaDB"
)
cursor = db.cursor()

def coletar_dados():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        endereco = request.form['endereco']
        cpf = request.form['cpf']
        atividades = request.form['atividades']
        eventos = request.form['eventos']
        compras = request.form['compras']
        link_perfil = request.form['link_perfil']
        interesses = request.form.getlist('interesse')

        # Salvando os dados no banco
        sql = '''
        INSERT INTO DadoFans (nome, email, endereco, cpf, atividades, eventos, compras, links)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        '''
        valores = (nome, email, endereco, cpf, atividades, eventos, compras, link_perfil)
        cursor.execute(sql, valores)
        db.commit()

        # Passando os dados para o template 'result.html'
        data = {
            'nome': nome,
            'email': email,
            'endereco': endereco,
            'cpf': cpf,
            'atividades': atividades,
            'eventos': eventos,
            'compras': compras,
            'link_perfil': link_perfil,
            'interesses': interesses, # Exemplo de retorno da análise de link
        }

        return render_template('result.html', data=data)

    return render_template('index.html')

oid = OpenID(app)
oauth = OAuth(app)

steam = oauth.register(
    'steam',
    client_id='STEAM_API_KEY',
    authorize_url='https://steamcommunity.com/openid/login',
    access_token_url=None,
    client_kwargs={'scope': 'openid'},
)

# Configuração do Discord OAuth
discord = oauth.register(
    'discord',
    client_id=os.getenv('DISCORD_CLIENT_ID'),
    client_secret=os.getenv('DISCORD_CLIENT_SECRET'),
    authorize_url='https://discord.com/oauth2/authorize',
    access_token_url='https://discord.com/api/oauth2/token',
    refresh_token_url=None,
    client_kwargs={'scope': 'identify email'},
)

# Configuração do Twitch OAuth
twitch = oauth.register(
    'twitch',
    client_id=os.getenv('TWITCH_CLIENT_ID'),
    client_secret=os.getenv('TWITCH_CLIENT_SECRET'),
    authorize_url='https://id.twitch.tv/oauth2/authorize',
    access_token_url='https://id.twitch.tv/oauth2/token',
    refresh_token_url=None,
    client_kwargs={'scope': 'user:read:email'},
)

# Rota para Steam OAuth
@app.route('/login/steam')
def login_steam():
    # Indica que a resposta de autenticação deve ser enviada para 'auth_steam'
    redirect_uri = url_for('auth_steam', _external=True)
    return steam.authorize_redirect(redirect_uri)

@app.route('/login/steam/authorized')
def auth_steam():
    token = steam.authorize_access_token()
    
    # Processa os dados retornados após a autenticação
    user_info = steam.get('https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/', token=token)
    
    # Salva o nome do usuário na sessão
    session['user'] = {'name': user_info.json()['response']['players'][0]['personaname']}
    
    return redirect(url_for('index'))

# Rota para Discord OAuth
@app.route('/login/discord')
def login_discord():
    redirect_uri = 'https://127.0.0.1:5000/login/discord/authorized'
    return discord.authorize_redirect(redirect_uri)

# Rota para Twitch OAuth
@app.route('/login/twitch')
def login_twitch():
    redirect_uri = url_for('auth_twitch', _external=True)
    return twitch.authorize_redirect(redirect_uri)

# Callback de autenticação para Steam
def auth_steam():
    # Verifica se a autenticação foi bem-sucedida
    if oid.verify():
        user_info = oid.fetch()
        # Armazenar as informações do usuário na sessão
        session['user'] = {'name': user_info}
        return redirect(url_for('index'))

# Callback de autenticação para Discord
@app.route('/login/discord/authorized')
def auth_discord():
    token = discord.authorize_access_token()
    user_info = discord.get('https://discord.com/api/v10/users/@me', token=token)
    session['user'] = {'name': user_info.json()['username']}
    return redirect(url_for('index'))

# Callback de autenticação para Twitch
@app.route('/login/twitch/authorized')
def auth_twitch():
    token = twitch.authorize_access_token()
    user_info = twitch.get('https://api.twitch.tv/helix/users', token=token)
    session['user'] = {'name': user_info.json()['data'][0]['display_name']}
    return redirect(url_for('index'))

# Página inicial
@app.route('/')
def index():
    if 'user' in session:
        return f'Olá, {session["user"]["name"]}'
    return render_template('index.html')

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
        link_perfil = request.form.get('link_perfil', '').strip()

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
            'link_perfil': link_perfil,
            'resultado_ia': "Nenhum documento enviado.",
            'resultado_link': "Nenhum link enviado."
        }
        
        
        # Verifica se o CPF é válido
        if not validate_cpf(cpf):
            form_data['resultado_link'] = "🚨 CPF inválido"
            return render_template('error.html', message="CPF inválido", data=form_data), 400

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
                                "JUSTIFICATIVA: [explicação clara e detalhada sobre oque é relevante para a pessoa baseado no link e ligue com a furia]"
                            )
                        },
                        {
                            "role": "user",
                            "content": f"Link do perfil: {link_perfil}\nInteresses: {', '.join(form_data['interesses'])}"
                        }
                    ],
                    temperature=0.2,
                    max_tokens=500
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
        "content": "Você é um validador de documentos. Analise a imagem fornecida comparando com os dados: Nome: {nome} CPF: {cpf} Sua resposta DEVE seguir EXATAMENTE este formato: STATUS: [VALIDADO/NÃO VALIDADO] JUSTIFICATIVA: [Explicação detalhada da decisão] ATENÇÃO PARA NUMEROS SEMELHANTES ESCRITOS COMO 5 e 6 E LETRAS SEMELHANTES COMO S E Z Critérios:1. VALIDADO se:- Nome e CPF na imagem coincidem com os dados fornecidos - Documento parece autêntico e legível 2. NÃO VALIDADO se: - Qualquer divergência nos dados - Documento ilegível, adulterado ou incompleto"  # Mantenha seu system prompt   
    },
    {
        "role": "user", 
        "content": [
            {
                "type": "text",
                "text": f"Verifique se o documento contém:\nNome: {form_data['nome']}\nCPF: {cpf}"
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

                

                # Padrões melhorados com flexibilidade
                status_pattern = r"(?i)(status|resultado|validação)\s*[:.-]?\s*(validado|não validado|nao validado|inválido|invalido|aprovado|reprovado|negado|incorreto)"
                justificativa_pattern = r"(?i)(justificativa|motivo|razão|explicação|análise)\s*[:.-]?\s*(.*?)(?=(status|resultado|validação|$))"
                
                
                status_mapping = {
                    'validado': 'VALIDADO',
                    'aprovado': 'VALIDADO',
                    'reprovado': 'NÃO VALIDADO',
                    'inválido': 'NÃO VALIDADO', 
                    'invalido': 'NÃO VALIDADO',
                    'nao validado': 'NÃO VALIDADO',
                    'não validado': 'NÃO VALIDADO',
                    'negado': 'NÃO VALIDADO',
                    'incorreto': 'NÃO VALIDADO'
                }

                # Processar resposta
                raw_response = response.choices[0].message.content.strip()
                status = "INDETERMINADO"
                justificativa = "Resposta não interpretada"
                
                status_match = re.search(status_pattern, raw_response, re.DOTALL | re.IGNORECASE)
                justificativa_match = re.search(justificativa_pattern, raw_response, re.DOTALL | re.IGNORECASE)
                
                # Normalizar status
                if status_match:
                    raw_status = status_match.group(2).strip().lower()
                    status = status_mapping.get(raw_status, 'INDETERMINADO')

                # Capturar justificativa
                if justificativa_match:
                    justificativa = justificativa_match.group(2).strip()
                    justificativa = re.sub(r'\s+', ' ', justificativa)  # Remover espaços múltiplos
                
                # Fallback 1 - Busca contextual
                if status == 'INDETERMINADO':
                    if any(palavra in raw_response.lower() for palavra in ["confere", "correto", "coincide", "match"]):
                        status = "VALIDADO"
                    elif any(palavra in raw_response.lower() for palavra in ["não confere", "incorreto", "divergente", "errado"]):
                        status = "NÃO VALIDADO"
                        
                # Fallback 2 - Análise de sentimento
                if status == 'INDETERMINADO':
                    positive_words = ['valid', 'correct', 'match', 'positiv']
                    negative_words = ['invalid', 'incorrect', 'mismatch', 'negativ']
                    
                    if any(word in raw_response.lower() for word in positive_words):
                        status = "VALIDADO"
                    elif any(word in raw_response.lower() for word in negative_words):
                        status = "NÃO VALIDADO"
                        
                # Atualizar com matches encontrados
                if status_match:
                    status = status_match.group(2).upper()
                    status = "NÃO VALIDADO" if status in ["NAO VALIDADO", "INVALIDO", "INVÁLIDO", "REPROVADO"] else status
                    
                if justificativa_match:
                    justificativa = justificativa_match.group(2).strip()
                    
                status = status if status in ["VALIDADO", "NÃO VALIDADO"] else "INDETERMINADO"

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
    context = ('cert.pem', 'key.pem')  # Certificado e chave privada
    app.run(host='127.0.0.1', port=5000, ssl_context=context)
    app.run(debug=True)