from app import create_app

app = create_app()

if __name__ == '__main__':
    print("Iniciando servidor Flask...")
    print("Acesse: http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)
