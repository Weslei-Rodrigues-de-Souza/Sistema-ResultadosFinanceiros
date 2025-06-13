import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua-chave-secreta-aqui'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///resultados_financeiros.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    # Crie a pasta se não existir
    os.makedirs(Config.CLIENTES_DIR, exist_ok=True)

    # Função para alternar bancos
    def get_db_engine(empresa_id):
        empresa = Empresa.query.get(empresa_id)
        return create_engine(f'sqlite:///{empresa.caminho_banco}')

    # Sobrescreva a session do SQLAlchemy
    @app.before_request
    def before_request():
        if 'empresa_selecionada' in session:
            empresa_id = session['empresa_selecionada']
            engine = get_db_engine(empresa_id)
            db.session.bind = engine
