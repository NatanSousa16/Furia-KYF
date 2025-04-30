from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def form():
    if request.method == 'POST':
        data = {
            'nome': request.form['nome'],
            'email': request.form['email'],
            'endereco': request.form['endereco'],
            'cpf': request.form['cpf'],
            'interesses': request.form.getlist('interesses')
        }
        return render_template('result.html', data=data)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
