# 🔥 Furia-KYF: Validador Inteligente de Fãs

Este projeto é um sistema Flask que valida documentos e perfis de redes sociais para identificar fãs reais da equipe FURIA de esports. A validação é feita com ajuda de inteligência artificial via GPT-4.

---

## 🚀 Funcionalidades

- Upload de documentos (.pdf, .jpg, .png)
- Extração de Nome e CPF
- Justificativa e status de validação via GPT-4
- Validação de links de perfil (Steam, Discord, Twitch)
- Avaliação da relevância dos perfis para o cenário de esports
- Login com redes sociais via OAuth

---

## 🧠 Tecnologias Utilizadas

- Python 3.8.10
- Flask
- HTML + CSS
- MySQL
- GPT-4 Turbo (via API)
- OpenSSL para HTTPS local
- OAuth (Para Twitch, Discord e Steam)

---

## 📁 Organização do Projeto

furia-kyf/
├── app.py # Aplicação principal Flask
├── templates/ # Arquivos HTML (páginas do sistema)
│ ├── index.html
│ ├── resultado.html
├── static/ # Estilos e imagens
│ └── style.css
| ├── image/
│ └── discord.png
│ └── furia-logo.png
│ └── steam.png
│ └── twitch.png



---

## 🔒 Segurança e Privacidade

- Documentos enviados não são armazenados após a análise.
- Dados sensíveis como CPF são tratados apenas em memória.
- Conexão HTTPS ativa para testes locais com SSL.

---

## ⚙️ Como Executar Localmente

1. Clone o repositório:
   ```bash
   git clone https://github.com/seuusuario/furia-kyf.git
   cd furia-kyf
2. Gere certificados SSL (para HTTPS local):
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

3. Execute o app:
python3 app.py

4. Acesse:
https://127.0.0.1:5000
