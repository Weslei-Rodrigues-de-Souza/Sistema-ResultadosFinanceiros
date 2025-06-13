from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum

db = SQLAlchemy()

class TipoConta(Enum):
    RECEITA = "receita"
    DESPESA = "despesa"
    INVESTIMENTO = "investimento"
    IMPOSTO = "imposto"
    CUSTO = "custo"
    RETIRADA = "retirada"

class Categoria(db.Model):
    __tablename__ = 'categorias'
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False, unique=False)
    descricao = db.Column(db.Text)
    eh_faturamento = db.Column(db.Boolean, default=False)
    ativa = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    contas = db.relationship('Conta', backref='categoria', lazy=True)

class Conta(db.Model):
    __tablename__ = 'contas'
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=False)
    data = db.Column(db.Date, nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    descricao = db.Column(db.String(255))
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

class ConfiguracaoCalculo(db.Model):
    __tablename__ = 'configuracao_calculo'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False, unique=True)
    categorias_positivas = db.Column(db.Text)
    categorias_negativas = db.Column(db.Text)
    formula_customizada = db.Column(db.Text)
    ativa = db.Column(db.Boolean, default=True)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    def __repr__(self):
        return f'<ConfiguracaoCalculo {self.nome}>'

class Empresa(db.Model):
    __tablename__ = 'empresas'
    id = db.Column(db.Integer, primary_key=True)
    cnpj = db.Column(db.String(18), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    caminho_banco = db.Column(db.String(255), nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    ativa = db.Column(db.Boolean, default=True)
    def __repr__(self):
        return f'<Empresa {self.nome}>'
