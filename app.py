from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField, DateField, DecimalField, SelectField, SelectMultipleField
from wtforms.validators import DataRequired, NumberRange, Length, Optional, Email, EqualTo, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date
from sqlalchemy import extract, func, text
from enum import Enum
from functools import wraps  # ADICIONE ESTA LINHA
from functools import lru_cache
from datetime import datetime, timedelta
import pandas as pd
import tempfile
import os
import json

# Cache simples em memória
dashboard_cache = {}
CACHE_DURATION = 300  # 5 minutos

def get_dashboard_cache_key(empresa_id, ano):
    return f"dashboard_{empresa_id}_{ano}"

def get_cached_dashboard_data(empresa_id, ano):
    """Busca dados do cache se ainda válidos"""
    cache_key = get_dashboard_cache_key(empresa_id, ano)
    
    if cache_key in dashboard_cache:
        cached_data, timestamp = dashboard_cache[cache_key]
        if datetime.now() - timestamp < timedelta(seconds=CACHE_DURATION):
            return cached_data
    
    return None

def set_dashboard_cache(empresa_id, ano, data):
    """Salva dados no cache"""
    cache_key = get_dashboard_cache_key(empresa_id, ano)
    dashboard_cache[cache_key] = (data, datetime.now())

# Configuração para MySQL
MYSQL_CONFIG = {
    'host': '162.241.203.176',
    'port': 3306,
    'user': 'gerent67_weslei',
    'password': '1saZfK(rg',
    'database': 'gerent67_sistemas'
}

# Configuração do Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua-chave-secreta-super-segura'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///resultados_financeiros.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 3,           # Reduzir ainda mais
    'pool_timeout': 20,       # Timeout menor
    'pool_recycle': 3600,     # 1 hora
    'pool_pre_ping': False,   # Desabilitar para ganhar velocidade
    'max_overflow': 0,
    'connect_args': {
        'connect_timeout': 30,
        'read_timeout': 30,
        'write_timeout': 30,
        'charset': 'utf8mb4',
        'autocommit': True
    }
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['CLIENTES_DIR'] = os.path.join(os.path.dirname(__file__), 'clientes')


# Inicializar SQLAlchemy
db = SQLAlchemy(app)

# Configuração do Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'

# Modelos
class TipoConta(Enum):
    RECEITA = "receita"
    DESPESA = "despesa"
    INVESTIMENTO = "investimento"
    IMPOSTO = "imposto"
    CUSTO = "custo"
    RETIRADA = "retirada"

user_empresas = db.Table('user_empresas',
    db.Column('user_id', db.Integer, db.ForeignKey('usuarios.id'), primary_key=True),
    db.Column('empresa_id', db.Integer, db.ForeignKey('empresas.id'), primary_key=True),
    db.Column('data_associacao', db.DateTime, default=datetime.utcnow)
)

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nome_completo = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_login = db.Column(db.DateTime)
    
    # Relacionamento muitos-para-muitos com empresas
    empresas = db.relationship('Empresa', secondary=user_empresas, 
                              backref=db.backref('usuarios', lazy='dynamic'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def pode_acessar_empresa(self, empresa_id):
        """Verifica se o usuário pode acessar uma empresa específica"""
        if self.is_admin:
            return True
        return any(empresa.id == empresa_id for empresa in self.empresas)
    
    def get_empresas_acessiveis(self):
        """Retorna as empresas que o usuário pode acessar"""
        if self.is_admin:
            return Empresa.query.filter_by(ativa=True).all()
        return [empresa for empresa in self.empresas if empresa.ativa]

    def __repr__(self):
        return f'<Usuario {self.username}>'

class Categoria(db.Model):
    __tablename__ = 'categorias'
    
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    eh_faturamento = db.Column(db.Boolean, default=False)
    ativa = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_inativacao = db.Column(db.DateTime, nullable=True)
    usuario_inativacao = db.Column(db.String(100), nullable=True)
    
    contas = db.relationship('Conta', backref='categoria', lazy=True)

    def pode_ser_excluida(self):
        """Verifica se a categoria pode ser excluída (não tem contas vinculadas)"""
        # CORREÇÃO: Use len() ao invés de count()
        return len(self.contas) == 0

    def inativar(self, usuario):
        """Inativa a categoria"""
        self.ativa = False
        self.data_inativacao = datetime.utcnow()
        self.usuario_inativacao = usuario

    def __repr__(self):
        return f'<Categoria {self.nome}>'



class Conta(db.Model):
    __tablename__ = 'contas'
    
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)  # DEVE ESTAR AQUI
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=False)
    data = db.Column(db.Date, nullable=False)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    descricao = db.Column(db.String(255))
    ativa = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_inativacao = db.Column(db.DateTime, nullable=True)
    usuario_inativacao = db.Column(db.String(100), nullable=True)

    def inativar(self, usuario):
        """Inativa a conta"""
        self.ativa = False
        self.data_inativacao = datetime.utcnow()
        self.usuario_inativacao = usuario

    def __repr__(self):
        return f'<Conta {self.valor}>'

class Empresa(db.Model):
    __tablename__ = 'empresas'
    
    id = db.Column(db.Integer, primary_key=True)
    cnpj = db.Column(db.String(18), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    caminho_banco = db.Column(db.String(255), nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    ativa = db.Column(db.Boolean, default=True)
    data_inativacao = db.Column(db.DateTime, nullable=True)
    usuario_inativacao = db.Column(db.String(100), nullable=True)

    def pode_ser_excluida(self):
        """Verifica se a empresa pode ser excluída"""
        categorias_count = Categoria.query.filter_by(empresa_id=self.id).count()
        contas_count = Conta.query.filter_by(empresa_id=self.id).count()
        return categorias_count == 0 and contas_count == 0

    def inativar(self, usuario):
        """Inativa a empresa"""
        self.ativa = False
        self.data_inativacao = datetime.utcnow()
        self.usuario_inativacao = usuario

    def __repr__(self):
        return f'<Empresa {self.nome}>'

class ConfiguracaoCalculo(db.Model):
    __tablename__ = 'configuracao_calculo'
    
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    nome = db.Column(db.String(50), nullable=False)
    categorias_positivas = db.Column(db.Text)
    categorias_negativas = db.Column(db.Text)
    ativa = db.Column(db.Boolean, default=True)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    data_inativacao = db.Column(db.DateTime, nullable=True)
    usuario_inativacao = db.Column(db.String(100), nullable=True)

    # Constraint única por empresa
    __table_args__ = (db.UniqueConstraint('empresa_id', 'nome', name='_empresa_config_nome_uc'),)

    def pode_ser_excluida(self):
        """Verifica se a configuração pode ser excluída"""
        return True  # Configurações podem sempre ser excluídas

    def inativar(self, usuario):
        """Inativa a configuração"""
        self.ativa = False
        self.data_inativacao = datetime.utcnow()
        self.usuario_inativacao = usuario

    def __repr__(self):
        return f'<ConfiguracaoCalculo {self.nome}>'

def empresa_required(f):
    """Decorator para garantir que uma empresa esteja selecionada"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        empresa_id = session.get('empresa_selecionada')
        if not empresa_id:
            flash('Selecione uma empresa primeiro para acessar esta funcionalidade!', 'warning')
            return redirect(url_for('empresas'))
        
        # Verificar se a empresa ainda existe e está ativa
        empresa = Empresa.query.filter_by(id=empresa_id, ativa=True).first()
        if not empresa:
            session.pop('empresa_selecionada', None)
            flash('A empresa selecionada não está mais disponível. Selecione uma empresa válida.', 'warning')
            return redirect(url_for('empresas'))
        
        return f(*args, **kwargs)
    return decorated_function

# User loader
@login_manager.user_loader
def load_user(user_id):
    # ANTES: return db.session.get(Usuario, int(user_id))
    # DEPOIS:
    return db.session.get(Usuario, int(user_id))  # Esta já está correta

# Context processor para empresa selecionada
@app.context_processor
def inject_empresas():
    empresas = []
    if current_user.is_authenticated:
        try:
            empresas = current_user.get_empresas_acessiveis()
        except Exception as e:
            #print(f"Erro ao carregar empresas: {e}")
            empresas = []
    return dict(empresas=empresas)

@app.context_processor
def inject_empresa_selecionada():
    empresa = None
    if 'empresa_selecionada' in session:
        # ANTES: empresa = Empresa.query.get(session['empresa_selecionada'])
        # DEPOIS:
        empresa = db.session.get(Empresa, session['empresa_selecionada'])
    return dict(empresa_selecionada=empresa)

# Formulários
class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    remember_me = BooleanField('Lembrar de mim')
    submit = SubmitField('Entrar')

class RegistroForm(FlaskForm):
    username = StringField('Nome de Usuário', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    nome_completo = StringField('Nome Completo', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirmar Senha', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Cadastrar')

    def validate_username(self, username):
        user = Usuario.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Este nome de usuário já está em uso.')

    def validate_email(self, email):
        user = Usuario.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Este email já está cadastrado.')

class CategoriaForm(FlaskForm):
    nome = StringField('Nome da Categoria', validators=[DataRequired(), Length(min=2, max=100)])
    descricao = TextAreaField('Descrição', validators=[Optional(), Length(max=500)])
    eh_faturamento = BooleanField('Esta é a categoria de faturamento')

class ContaForm(FlaskForm):
    categoria_id = SelectField('Categoria', coerce=int, validators=[DataRequired()])
    data = DateField('Data', validators=[DataRequired()])
    valor = DecimalField('Valor', validators=[DataRequired(), NumberRange(min=0.01)], places=2)
    descricao = StringField('Descrição', validators=[Optional(), Length(max=255)])

class EmpresaForm(FlaskForm):
    cnpj = StringField('CNPJ', validators=[DataRequired(), Length(min=18, max=18)])
    nome = StringField('Nome da Empresa', validators=[DataRequired(), Length(min=3, max=100)])

# Adicione ao arquivo de forms (ou no app.py se estiver lá)
class UsuarioForm(FlaskForm):
    username = StringField('Nome de usuário', validators=[DataRequired(), Length(min=4, max=25)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    nome_completo = StringField('Nome completo', validators=[DataRequired(), Length(min=2, max=100)])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    is_admin = BooleanField('Administrador')
    empresas = SelectMultipleField('Empresas', coerce=int, 
                                  choices=[], 
                                  render_kw={"class": "form-control", "multiple": True})
    submit = SubmitField('Salvar')

class UsuarioEditForm(FlaskForm):
    username = StringField('Nome de usuário', validators=[DataRequired(), Length(min=4, max=25)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    nome_completo = StringField('Nome completo', validators=[DataRequired(), Length(min=2, max=100)])
    password = PasswordField('Nova senha (deixe em branco para manter a atual)', validators=[Optional(), Length(min=6)])
    is_admin = BooleanField('Administrador')
    ativo = BooleanField('Usuário ativo')
    empresas = SelectMultipleField('Empresas', coerce=int, 
                                  choices=[], 
                                  render_kw={"class": "form-control", "multiple": True})
    submit = SubmitField('Atualizar')

# Funções de planilha
def processar_importacao_planilha(arquivo, empresa_id):
    """
    Processa a importação de contas da planilha para a empresa selecionada
    
    Args:
        arquivo: Arquivo Excel (.xlsx ou .xls) com dados das contas
        
    Returns:
        dict: Resultado da importação com status, contadores e erros
    """
    try:
        # Verificar se há empresa selecionada
        empresa_id = session.get('empresa_selecionada')
        if not empresa_id:
            return {
                'sucesso': False,
                'erro': 'Nenhuma empresa selecionada para importação'
            }
        
        # Verificar se a empresa ainda existe e está ativa
        empresa = Empresa.query.filter_by(id=empresa_id, ativa=True).first()
        if not empresa:
            return {
                'sucesso': False,
                'erro': 'Empresa selecionada não está mais disponível'
            }
        
        #print(f"Iniciando importação para empresa: {empresa.nome} (ID: {empresa_id})")
        
        # Ler o arquivo Excel
        try:
            df = pd.read_excel(arquivo, sheet_name='Contas')
        except Exception as e:
            return {
                'sucesso': False,
                'erro': f'Erro ao ler arquivo Excel: {str(e)}. Verifique se o arquivo tem uma aba chamada "Contas"'
            }
        
        # Verificar se o DataFrame não está vazio
        if df.empty:
            return {
                'sucesso': False,
                'erro': 'Planilha está vazia ou não contém dados válidos'
            }
        
        # Verificar se as colunas obrigatórias existem
        colunas_obrigatorias = ['Categoria', 'Valor', 'Data']
        colunas_faltantes = [col for col in colunas_obrigatorias if col not in df.columns]
        if colunas_faltantes:
            return {
                'sucesso': False,
                'erro': f'Colunas obrigatórias não encontradas: {", ".join(colunas_faltantes)}'
            }
        
        # Carregar categorias da empresa
        categorias = Categoria.query.filter_by(empresa_id=empresa_id, ativa=True).all()
        if not categorias:
            return {
                'sucesso': False,
                'erro': 'Nenhuma categoria ativa encontrada para esta empresa. Crie categorias primeiro.'
            }
        
        # Criar dicionário de categorias para busca rápida
        categorias_dict = {cat.nome.strip().lower(): cat.id for cat in categorias}
        categorias_nomes = [cat.nome for cat in categorias]
        
        #print(f"Categorias disponíveis: {', '.join(categorias_nomes)}")
        
        # Contadores e controle
        contas_importadas = 0
        contas_ignoradas = 0
        erros = []
        linhas_processadas = 0
        
        # Processar cada linha do DataFrame
        for index, row in df.iterrows():
            linhas_processadas += 1
            linha_atual = index + 2  # +2 porque o Excel começa em 1 e tem cabeçalho
            
            try:
                # Verificar se a linha tem dados mínimos
                if pd.isna(row['Categoria']) and pd.isna(row['Valor']) and pd.isna(row['Data']):
                    continue  # Pular linhas completamente vazias
                
                # Validar categoria
                if pd.isna(row['Categoria']):
                    contas_ignoradas += 1
                    erros.append(f"Linha {linha_atual}: Categoria não informada - linha ignorada")
                    continue
                
                categoria_nome = str(row['Categoria']).strip()
                categoria_nome_lower = categoria_nome.lower()
                
                if categoria_nome_lower not in categorias_dict:
                    contas_ignoradas += 1
                    erros.append(f"Linha {linha_atual}: Categoria '{categoria_nome}' não encontrada - linha ignorada")
                    continue
                
                categoria_id = categorias_dict[categoria_nome_lower]
                
                # Validar e processar valor
                if pd.isna(row['Valor']):
                    contas_ignoradas += 1
                    erros.append(f"Linha {linha_atual}: Valor não informado - linha ignorada")
                    continue
                
                try:
                    valor_str = str(row['Valor']).strip()
                    
                    # Remover símbolos de moeda e espaços
                    valor_str = valor_str.replace('R$', '').replace(' ', '').replace('\xa0', '')
                    
                    # Tratar formatação brasileira (1.500,75) vs americana (1,500.75)
                    if ',' in valor_str and '.' in valor_str:
                        # Formato brasileiro: 1.500,75
                        if valor_str.rfind(',') > valor_str.rfind('.'):
                            valor_str = valor_str.replace('.', '').replace(',', '.')
                        # Formato americano: 1,500.75 (manter como está)
                    elif ',' in valor_str and '.' not in valor_str:
                        # Apenas vírgula: assumir decimal brasileiro
                        valor_str = valor_str.replace(',', '.')
                    
                    valor = float(valor_str)
                    
                    if valor <= 0:
                        contas_ignoradas += 1
                        erros.append(f"Linha {linha_atual}: Valor deve ser maior que zero (valor: {valor}) - linha ignorada")
                        continue
                        
                except (ValueError, TypeError) as e:
                    contas_ignoradas += 1
                    erros.append(f"Linha {linha_atual}: Valor inválido '{row['Valor']}' - linha ignorada")
                    continue
                
                # Validar e processar data
                if pd.isna(row['Data']):
                    contas_ignoradas += 1
                    erros.append(f"Linha {linha_atual}: Data não informada - linha ignorada")
                    continue
                
                try:
                    if isinstance(row['Data'], str):
                        data_str = row['Data'].strip()
                        
                        # Tentar diferentes formatos de data
                        formatos_data = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y', '%d-%m-%y']
                        data = None
                        
                        for formato in formatos_data:
                            try:
                                data = datetime.strptime(data_str, formato).date()
                                break
                            except ValueError:
                                continue
                        
                        if data is None:
                            raise ValueError(f"Formato de data não reconhecido: {data_str}")
                            
                    elif hasattr(row['Data'], 'date'):
                        # Objeto datetime do pandas
                        data = row['Data'].date()
                    elif isinstance(row['Data'], date):
                        # Já é um objeto date
                        data = row['Data']
                    else:
                        # Tentar converter diretamente
                        data = pd.to_datetime(row['Data']).date()
                    
                    # Validar se a data não é muito antiga ou futura
                    hoje = date.today()
                    if data.year < 1900 or data.year > hoje.year + 10:
                        contas_ignoradas += 1
                        erros.append(f"Linha {linha_atual}: Data fora do intervalo válido (1900 - {hoje.year + 10}) - linha ignorada")
                        continue
                        
                except (ValueError, TypeError) as e:
                    contas_ignoradas += 1
                    erros.append(f"Linha {linha_atual}: Data inválida '{row['Data']}' (use DD/MM/AAAA) - linha ignorada")
                    continue
                
                # Processar descrição (opcional)
                descricao = None
                if 'Descrição' in row and not pd.isna(row['Descrição']):
                    descricao = str(row['Descrição']).strip()
                    if len(descricao) > 255:
                        descricao = descricao[:255]
                        erros.append(f"Linha {linha_atual}: Descrição truncada para 255 caracteres")
                
                # Criar a conta
                conta = Conta(
                    categoria_id=categoria_id,
                    empresa_id=empresa_id,
                    valor=valor,
                    data=data,
                    descricao=descricao,
                    ativa=True
                )
                
                db.session.add(conta)
                contas_importadas += 1
                

                
            except Exception as e:
                contas_ignoradas += 1
                erros.append(f"Linha {linha_atual}: Erro inesperado - {str(e)}")
                #print(f"Erro na linha {linha_atual}: {e}")
                continue
        
        # Commit das alterações
        try:
            db.session.commit()
            #print(f"Importação concluída: {contas_importadas} contas salvas no banco")
        except Exception as e:
            db.session.rollback()
            return {
                'sucesso': False,
                'erro': f'Erro ao salvar no banco de dados: {str(e)}'
            }
        
        # Preparar resultado
        resultado = {
            'sucesso': True,
            'contas_importadas': contas_importadas,
            'contas_ignoradas': contas_ignoradas,
            'linhas_processadas': linhas_processadas,
            'erros': erros,
            'empresa_nome': empresa.nome
        }
        
        # Log final
        #print(f"Resultado final:")
        #print(f"- Linhas processadas: {linhas_processadas}")
        #print(f"- Contas importadas: {contas_importadas}")
        #print(f"- Contas ignoradas: {contas_ignoradas}")
        #print(f"- Erros: {len(erros)}")
        
        return resultado
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        
        return {
            'sucesso': False,
            'erro': f"Erro geral ao processar planilha: {str(e)}"
        }


# Funções de cálculo

def calcular_indicadores_anuais_rapido(ano, empresa_id):
    """Versão ultra-rápida sem prints e com menos consultas"""
    try:
        indicadores = {'faturamento': 0, 'lucro_bruto': 0, 'lucro_liquido': 0, 'reserva_caixa': 0}
        
        # Faturamento em uma consulta
        categoria_faturamento = Categoria.query.filter_by(empresa_id=empresa_id, eh_faturamento=True).first()
        if categoria_faturamento:
            faturamento_total = db.session.query(func.sum(Conta.valor)).filter(
                Conta.categoria_id == categoria_faturamento.id,
                Conta.empresa_id == empresa_id,
                extract('year', Conta.data) == ano,
                Conta.ativa == True
            ).scalar() or 0
            indicadores['faturamento'] = float(faturamento_total)
        
        # Outros indicadores em lote
        configs = ConfiguracaoCalculo.query.filter_by(empresa_id=empresa_id, ativa=True).all()
        for config in configs:
            valor_total = 0
            
            if config.categorias_positivas:
                pos_ids = json.loads(config.categorias_positivas)
                valor_pos = db.session.query(func.sum(Conta.valor)).filter(
                    Conta.categoria_id.in_(pos_ids),
                    Conta.empresa_id == empresa_id,
                    extract('year', Conta.data) == ano,
                    Conta.ativa == True
                ).scalar() or 0
                valor_total += float(valor_pos)
            
            if config.categorias_negativas:
                neg_ids = json.loads(config.categorias_negativas)
                valor_neg = db.session.query(func.sum(Conta.valor)).filter(
                    Conta.categoria_id.in_(neg_ids),
                    Conta.empresa_id == empresa_id,
                    extract('year', Conta.data) == ano,
                    Conta.ativa == True
                ).scalar() or 0
                valor_total -= float(valor_neg)
            
            indicadores[config.nome] = valor_total
        
        return indicadores
    except:
        return {'faturamento': 0, 'lucro_bruto': 0, 'lucro_liquido': 0, 'reserva_caixa': 0}

def calcular_dados_grafico_rapido(ano, empresa_id):
    """Versão ultra-rápida para gráficos"""
    try:
        dados = {
            'meses': ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'],
            'lucro_bruto': [0] * 12, 'lucro_liquido': [0] * 12, 'reserva_caixa': [0] * 12, 'faturamento': [0] * 12
        }
        
        # Buscar configurações uma vez
        config_lucro_bruto = ConfiguracaoCalculo.query.filter_by(empresa_id=empresa_id, nome='lucro_bruto', ativa=True).first()
        config_lucro_liquido = ConfiguracaoCalculo.query.filter_by(empresa_id=empresa_id, nome='lucro_liquido', ativa=True).first()
        config_reserva_caixa = ConfiguracaoCalculo.query.filter_by(empresa_id=empresa_id, nome='reserva_caixa', ativa=True).first()
        categoria_faturamento = Categoria.query.filter_by(empresa_id=empresa_id, eh_faturamento=True).first()
        
        # Calcular mês a mês (sem prints)
        for mes in range(1, 13):
            if config_lucro_bruto:
                dados['lucro_bruto'][mes-1] = calcular_por_configuracao_mes_rapido(config_lucro_bruto, mes, ano, empresa_id)
            if config_lucro_liquido:
                dados['lucro_liquido'][mes-1] = calcular_por_configuracao_mes_rapido(config_lucro_liquido, mes, ano, empresa_id)
            if config_reserva_caixa:
                dados['reserva_caixa'][mes-1] = calcular_por_configuracao_mes_rapido(config_reserva_caixa, mes, ano, empresa_id)
            
            if categoria_faturamento:
                faturamento_mes = db.session.query(func.sum(Conta.valor)).filter(
                    Conta.categoria_id == categoria_faturamento.id,
                    Conta.empresa_id == empresa_id,
                    extract('month', Conta.data) == mes,
                    extract('year', Conta.data) == ano,
                    Conta.ativa == True
                ).scalar() or 0
                dados['faturamento'][mes-1] = float(faturamento_mes)
        
        return dados
    except:
        return {
            'meses': ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'],
            'lucro_bruto': [0] * 12, 'lucro_liquido': [0] * 12, 'reserva_caixa': [0] * 12, 'faturamento': [0] * 12
        }

def calcular_por_configuracao_mes_rapido(config, mes, ano, empresa_id):
    """Versão rápida sem prints"""
    if not config:
        return 0
    try:
        valor_total = 0
        if config.categorias_positivas:
            pos_ids = json.loads(config.categorias_positivas)
            valor_pos = db.session.query(func.sum(Conta.valor)).filter(
                Conta.categoria_id.in_(pos_ids), Conta.empresa_id == empresa_id,
                extract('month', Conta.data) == mes, extract('year', Conta.data) == ano, Conta.ativa == True
            ).scalar() or 0
            valor_total += float(valor_pos)
        
        if config.categorias_negativas:
            neg_ids = json.loads(config.categorias_negativas)
            valor_neg = db.session.query(func.sum(Conta.valor)).filter(
                Conta.categoria_id.in_(neg_ids), Conta.empresa_id == empresa_id,
                extract('month', Conta.data) == mes, extract('year', Conta.data) == ano, Conta.ativa == True
            ).scalar() or 0
            valor_total -= float(valor_neg)
        
        return valor_total
    except:
        return 0


# Filtros para templates
@app.template_filter('from_json')
def from_json_filter(value):
    if value:
        try:
            return json.loads(value)
        except:
            return []
    return []

@app.template_filter('moeda_br')
def moeda_br_filter(valor):
    """Formata valor para moeda brasileira"""
    try:
        if isinstance(valor, str):
            valor_limpo = valor.replace('R$', '').replace(' ', '').strip()
            if ',' in valor_limpo:
                valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
            valor_float = float(valor_limpo)
        else:
            valor_float = float(valor)
        
        return f"R$ {valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError):
        return "R$ 0,00"

# Rotas de Autenticação
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('empresas'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data) and user.ativo:
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('dashboard')
            return redirect(next_page)
        else:
            flash('Usuário ou senha inválidos', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso', 'info')
    return redirect(url_for('login'))

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    form = RegistroForm()
    if form.validate_on_submit():
        user = Usuario(
            username=form.username.data,
            email=form.email.data,
            nome_completo=form.nome_completo.data,
            is_admin=False
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Usuário cadastrado com sucesso!', 'success')
        return redirect(url_for('login'))
    
    return render_template('registro.html', form=form)

# Rotas principais
@app.route('/dashboard')
@login_required
@empresa_required
def dashboard():
    try:
        empresa_id = session.get('empresa_selecionada')
        ano_atual = datetime.now().year
        ano_anterior = ano_atual - 1
        
        # Dados básicos (consultas simples)
        total_categorias = Categoria.query.filter_by(empresa_id=empresa_id, ativa=True).count()
        total_contas = Conta.query.filter_by(empresa_id=empresa_id, ativa=True).count()
        
        # Anos disponíveis (limitado para performance)
        anos_disponiveis_query = db.session.query(
            extract('year', Conta.data).label('ano')
        ).filter_by(empresa_id=empresa_id, ativa=True).distinct().order_by(db.desc('ano')).limit(3).all()
        anos_disponiveis = [str(int(ano.ano)) for ano in anos_disponiveis_query if int(ano.ano) != ano_atual]
        
        # Categorias disponíveis
        categorias_query = Categoria.query.filter_by(empresa_id=empresa_id, ativa=True).all()
        categorias_disponiveis = [{'id': cat.id, 'nome': cat.nome, 'eh_faturamento': cat.eh_faturamento} for cat in categorias_query]
        
        # Usar funções originais (comprovadamente mais rápidas)
        indicadores = calcular_indicadores_anuais_rapido(ano_atual, empresa_id)
        indicadores_ano_anterior = calcular_indicadores_anuais_rapido(ano_anterior, empresa_id)
        dados_grafico = calcular_dados_grafico_rapido(ano_atual, empresa_id)
        dados_grafico_anterior = calcular_dados_grafico_rapido(ano_anterior, empresa_id)
        
        return render_template('index.html',
                             indicadores=indicadores,
                             indicadores_ano_anterior=indicadores_ano_anterior,
                             total_categorias=total_categorias,
                             total_contas=total_contas,
                             dados_grafico=dados_grafico,
                             dados_grafico_anterior=dados_grafico_anterior,
                             anos_disponiveis=anos_disponiveis,
                             categorias_disponiveis=categorias_disponiveis,
                             ano_atual=ano_atual,
                             ano_anterior=ano_anterior)
        
    except Exception as e:
        # Fallback silencioso e rápido
        return render_template('index.html',
                             indicadores={'faturamento': 0, 'lucro_bruto': 0, 'lucro_liquido': 0, 'reserva_caixa': 0},
                             indicadores_ano_anterior={'faturamento': 0, 'lucro_bruto': 0, 'lucro_liquido': 0, 'reserva_caixa': 0},
                             total_categorias=0, total_contas=0,
                             dados_grafico={'meses': ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'], 'lucro_bruto': [0]*12, 'lucro_liquido': [0]*12, 'reserva_caixa': [0]*12, 'faturamento': [0]*12},
                             dados_grafico_anterior={'meses': ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'], 'lucro_bruto': [0]*12, 'lucro_liquido': [0]*12, 'reserva_caixa': [0]*12, 'faturamento': [0]*12},
                             anos_disponiveis=[], categorias_disponiveis=[], ano_atual=ano_atual, ano_anterior=ano_anterior)

# Rotas de Categorias
@app.route('/categorias')
@login_required
@empresa_required
def listar_categorias():
    try:
        empresa_id = session.get('empresa_selecionada')
        if empresa_id:
            # Mostrar ativas e inativas separadamente
            categorias_ativas = Categoria.query.filter_by(empresa_id=empresa_id, ativa=True).all()
            categorias_inativas = Categoria.query.filter_by(empresa_id=empresa_id, ativa=False).all()
        else:
            categorias_ativas = []
            categorias_inativas = []
            flash('Selecione uma empresa primeiro!', 'warning')
    except Exception as e:
        #print(f"Erro ao listar categorias: {e}")
        categorias_ativas = []
        categorias_inativas = []
        flash('Erro ao carregar categorias!', 'error')
    
    form = CategoriaForm()
    return render_template('categorias/cadastro.html', 
                         categorias_ativas=categorias_ativas,
                         categorias_inativas=categorias_inativas,
                         form=form)

@app.route('/contas')
@login_required
@empresa_required
def listar_contas():
    try:
        empresa_id = session.get('empresa_selecionada')
        if empresa_id:
            # Mostrar apenas contas ativas por padrão
            contas = Conta.query.filter_by(empresa_id=empresa_id, ativa=True).order_by(Conta.data.desc()).limit(100).all()
            categorias = Categoria.query.filter_by(empresa_id=empresa_id, ativa=True).all()
        else:
            contas = []
            categorias = []
            flash('Selecione uma empresa primeiro!', 'warning')
        
        anos_disponiveis = db.session.query(
            db.extract('year', Conta.data).label('ano')
        ).filter_by(empresa_id=empresa_id, ativa=True).distinct().order_by(db.desc('ano')).all()
        
        anos = [str(int(ano.ano)) for ano in anos_disponiveis]
        
    except Exception as e:
        #print(f"Erro ao listar contas: {e}")
        contas = []
        categorias = []
        anos = []
        flash('Erro ao carregar contas!', 'error')
    
    form = ContaForm()
    form.categoria_id.choices = [(c.id, c.nome) for c in categorias]
    return render_template('contas/registro.html', contas=contas, categorias=categorias, form=form, anos=anos)



@app.route('/categorias/nova', methods=['POST'])
@login_required
@empresa_required
def nova_categoria():
    form = CategoriaForm()
    if form.validate_on_submit():
        try:
            empresa_id = session.get('empresa_selecionada')
            if not empresa_id:
                flash('Selecione uma empresa primeiro!', 'warning')
                return redirect(url_for('empresas'))
            
            if form.eh_faturamento.data:
                Categoria.query.filter_by(empresa_id=empresa_id, eh_faturamento=True).update({'eh_faturamento': False})
            
            categoria = Categoria(
                nome=form.nome.data,
                descricao=form.descricao.data,
                eh_faturamento=form.eh_faturamento.data,
                empresa_id=empresa_id
            )
            db.session.add(categoria)
            db.session.commit()
            flash('Categoria criada com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar categoria: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')
    
    return redirect(url_for('listar_categorias'))



@app.route('/categorias/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@empresa_required
def editar_categoria(id):
    # ANTES: categoria = Categoria.query.get_or_404(id)
    # DEPOIS: (já está correto)
    categoria = Categoria.query.get_or_404(id)
    
    # Verificar se a categoria pertence à empresa selecionada
    empresa_id = session.get('empresa_selecionada')
    if categoria.empresa_id != empresa_id:
        return jsonify({'status': 'error', 'message': 'Categoria não encontrada'}), 404
    
    if request.method == 'GET':
        form_data = {
            'id': categoria.id,
            'nome': categoria.nome,
            'descricao': categoria.descricao,
            'eh_faturamento': categoria.eh_faturamento
        }
        return jsonify(form_data)
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # Se está marcando como faturamento, desmarcar outras da mesma empresa
            if data.get('eh_faturamento'):
                Categoria.query.filter_by(
                    empresa_id=empresa_id, 
                    eh_faturamento=True
                ).filter(Categoria.id != categoria.id).update({'eh_faturamento': False})
            
            categoria.nome = data.get('nome')
            categoria.descricao = data.get('descricao')
            categoria.eh_faturamento = data.get('eh_faturamento', False)
            
            db.session.commit()
            return jsonify({'status': 'success', 'message': 'Categoria atualizada com sucesso!'})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': f'Erro ao atualizar categoria: {str(e)}'})


@app.route('/categorias/excluir/<int:id>', methods=['POST'])
@login_required
@empresa_required
def excluir_categoria(id):
    try:
        categoria = Categoria.query.get_or_404(id)
        
        # Verificar se pertence à empresa selecionada
        empresa_id = session.get('empresa_selecionada')
        if categoria.empresa_id != empresa_id:
            return jsonify({'status': 'error', 'message': 'Categoria não encontrada'})
        
        if categoria.pode_ser_excluida():
            db.session.delete(categoria)
            message = 'Categoria excluída com sucesso!'
        else:
            categoria.inativar(current_user.username)
            message = 'Categoria inativada com sucesso! (Possui contas vinculadas)'
            
        db.session.commit()
        return jsonify({'status': 'success', 'message': message})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Erro: {str(e)}'})

@app.route('/categorias/reativar/<int:id>', methods=['POST'])
@login_required
@empresa_required
def reativar_categoria(id):
    try:
        categoria = Categoria.query.get_or_404(id)
        
        # Verificar se pertence à empresa selecionada
        empresa_id = session.get('empresa_selecionada')
        if categoria.empresa_id != empresa_id:
            return jsonify({'status': 'error', 'message': 'Categoria não encontrada'})
        
        categoria.ativa = True
        categoria.data_inativacao = None
        categoria.usuario_inativacao = None
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Categoria reativada com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Erro: {str(e)}'})


# Rotas de Contas@app.route('/contas')

@app.route('/contas/nova', methods=['POST'])
@login_required
@empresa_required
def nova_conta():
    # Obter empresa_id ANTES de tudo
    empresa_id = session.get('empresa_selecionada')
    #print(f"🔍 DEBUG nova_conta: empresa_id = {empresa_id}")
    
    if not empresa_id:
        flash('Nenhuma empresa selecionada!', 'error')
        return redirect(url_for('empresas'))
    
    form = ContaForm()
    
    try:
        categorias = Categoria.query.filter_by(empresa_id=empresa_id, ativa=True).all()
        form.categoria_id.choices = [(c.id, c.nome) for c in categorias]
        
        if not categorias:
            flash('Crie pelo menos uma categoria antes de registrar contas!', 'warning')
            return redirect(url_for('listar_categorias'))
            
    except Exception as e:
        flash('Erro ao carregar categorias!', 'error')
        return redirect(url_for('listar_categorias'))
    
    if form.validate_on_submit():
        try:
            # Verificar se a categoria pertence à empresa
            categoria = Categoria.query.filter_by(id=form.categoria_id.data, empresa_id=empresa_id).first()
            if not categoria:
                flash('Categoria inválida para esta empresa!', 'error')
                return redirect(url_for('listar_contas'))
            
            #print(f"🔍 DEBUG: Criando conta com empresa_id={empresa_id}, categoria_id={form.categoria_id.data}")
            
            conta = Conta(
                categoria_id=form.categoria_id.data,
                empresa_id=empresa_id,  # GARANTIR que está sendo passado
                data=form.data.data,
                valor=float(form.valor.data),
                descricao=form.descricao.data if form.descricao.data else ''
            )
            
            #print(f"🔍 DEBUG: Conta objeto criado - empresa_id={conta.empresa_id}")
            
            db.session.add(conta)
            db.session.commit()
            flash('Conta registrada com sucesso!', 'success')
            
        except Exception as e:
            db.session.rollback()
            #print(f"🔍 DEBUG: Erro ao salvar conta: {e}")
            flash(f'Erro ao registrar conta: {str(e)}', 'error')
    else:
        #print(f"🔍 DEBUG: Formulário inválido - erros: {form.errors}")
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')
    
    return redirect(url_for('listar_contas'))


@app.route('/contas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@empresa_required
def editar_conta(id):
    conta = Conta.query.get_or_404(id)
    
    if request.method == 'GET':
        form_data = {
            'id': conta.id,
            'categoria_id': conta.categoria_id,
            'data': conta.data.strftime('%Y-%m-%d'),
            'valor': float(conta.valor),
            'descricao': conta.descricao
        }
        return jsonify(form_data)
    
    elif request.method == 'POST':
        try:
            conta.categoria_id = request.json.get('categoria_id')
            conta.data = datetime.strptime(request.json.get('data'), '%Y-%m-%d').date()
            conta.valor = request.json.get('valor')
            conta.descricao = request.json.get('descricao')
            
            db.session.commit()
            return jsonify({'status': 'success', 'message': 'Conta atualizada com sucesso!'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'message': f'Erro ao atualizar conta: {str(e)}'})

@app.route('/contas/excluir/<int:id>', methods=['GET', 'POST'])
@login_required
@empresa_required
def excluir_conta(id):
    try:
        conta = Conta.query.get_or_404(id)
        
        # Contas sempre são inativadas, nunca excluídas fisicamente
        conta.inativar(current_user.username)
        db.session.commit()
        
        if request.method == 'POST':
            return jsonify({'status': 'success', 'message': 'Conta inativada com sucesso!'})
        else:
            flash('Conta inativada com sucesso!', 'success')
            return redirect(url_for('listar_contas'))
            
    except Exception as e:
        db.session.rollback()
        if request.method == 'POST':
            return jsonify({'status': 'error', 'message': f'Erro ao inativar conta: {str(e)}'})
        else:
            flash(f'Erro ao inativar conta: {str(e)}', 'error')
            return redirect(url_for('listar_contas'))

@app.route('/contas/reativar/<int:id>', methods=['POST'])
@login_required
@empresa_required
def reativar_conta(id):
    try:
        conta = Conta.query.get_or_404(id)
        conta.ativa = True
        conta.data_inativacao = None
        conta.usuario_inativacao = None
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Conta reativada com sucesso!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Erro ao reativar conta: {str(e)}'})


@app.route('/contas/baixar-template')
@login_required
def baixar_template_contas():
    try:
        wb, erro = gerar_template_planilha()
        
        if erro:
            flash(erro, 'warning')
            return redirect(url_for('listar_contas'))
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        wb.save(temp_file.name)
        temp_file.close()
        
        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name='template_contas_elevalucro.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        flash(f'Erro ao gerar template: {str(e)}', 'error')
        return redirect(url_for('listar_contas'))

@app.route('/contas/importar', methods=['POST'])
@login_required
@empresa_required
def importar_contas():
    try:
        # Obter empresa_id ANTES de chamar a função
        empresa_id = session.get('empresa_selecionada')
        
        if not empresa_id:
            flash('Nenhuma empresa selecionada', 'error')
            return redirect(url_for('empresas'))
        
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(url_for('listar_contas'))
        
        arquivo = request.files['arquivo']
        
        if arquivo.filename == '':
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(url_for('listar_contas'))
        
        if not arquivo.filename.endswith(('.xlsx', '.xls')):
            flash('Arquivo deve ser uma planilha Excel (.xlsx ou .xls)', 'error')
            return redirect(url_for('listar_contas'))
        
        # PASSAR empresa_id como parâmetro
        resultado = processar_importacao_planilha(arquivo, empresa_id)
        
        if resultado['sucesso']:
            mensagem = f"Importação concluída! {resultado['contas_importadas']} contas importadas"
            if resultado['contas_ignoradas'] > 0:
                mensagem += f", {resultado['contas_ignoradas']} ignoradas"
            
            flash(mensagem, 'success')
            
            if resultado['erros']:
                for erro in resultado['erros'][:5]:
                    flash(erro, 'warning')
                if len(resultado['erros']) > 5:
                    flash(f"... e mais {len(resultado['erros']) - 5} erros", 'warning')
        else:
            flash(resultado['erro'], 'error')
        
    except Exception as e:
        flash(f'Erro na importação: {str(e)}', 'error')
    
    return redirect(url_for('listar_contas'))

# Rotas de Configuração
@app.route('/configuracao-calculo')
@login_required
@empresa_required
def configuracao_calculo():
    try:
        empresa_id = session.get('empresa_selecionada')
        if not empresa_id:
            flash('Selecione uma empresa primeiro!', 'warning')
            return redirect(url_for('empresas'))

        categorias = Categoria.query.filter_by(empresa_id=empresa_id, ativa=True).all()
        configuracoes = ConfiguracaoCalculo.query.filter_by(empresa_id=empresa_id, ativa=True).all()
        
    except Exception as e:
        #print(f"Erro ao carregar configurações: {e}")
        categorias = []
        configuracoes = []
        flash('Erro ao carregar configurações!', 'error')
    
    return render_template('configuracao/calculo.html', categorias=categorias, configuracoes=configuracoes)

@app.route('/api/configuracoes')
@login_required
@empresa_required
def api_configuracoes():
    try:
        empresa_id = session.get('empresa_selecionada')
        if not empresa_id:
            return jsonify({'error': 'Nenhuma empresa selecionada'}), 400

        configuracoes = ConfiguracaoCalculo.query.filter_by(empresa_id=empresa_id, ativa=True).all()
        categorias = Categoria.query.filter_by(empresa_id=empresa_id, ativa=True).all()
        
        result = []
        for config in configuracoes:
            formula_parts = []
            
            if config.categorias_positivas:
                pos_ids = json.loads(config.categorias_positivas)
                pos_names = [cat.nome for cat in categorias if cat.id in pos_ids]
                if pos_names:
                    formula_parts.append(' + '.join(pos_names))
            
            if config.categorias_negativas:
                neg_ids = json.loads(config.categorias_negativas)
                neg_names = [cat.nome for cat in categorias if cat.id in neg_ids]
                if neg_names:
                    if formula_parts:
                        formula_parts.append(' - (' + ' + '.join(neg_names) + ')')
                    else:
                        formula_parts.append('-(' + ' + '.join(neg_names) + ')')
            
            formula = ''.join(formula_parts) if formula_parts else 'Nenhuma configuração'
            
            result.append({
                'id': config.id,
                'nome': config.nome,
                'formula': formula,
                'ativa': config.ativa
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/salvar-configuracao', methods=['POST'])
@login_required
@empresa_required
def api_salvar_configuracao():
    try:
        empresa_id = session.get('empresa_selecionada')
        if not empresa_id:
            return jsonify({'success': False, 'message': 'Nenhuma empresa selecionada'}), 400

        data = request.get_json()
        nome = data.get('nome')
        categorias_positivas = data.get('categorias_positivas', [])
        categorias_negativas = data.get('categorias_negativas', [])
        
        # Verificar se já existe configuração com esse nome para esta empresa
        config = ConfiguracaoCalculo.query.filter_by(empresa_id=empresa_id, nome=nome).first()
        if not config:
            config = ConfiguracaoCalculo(nome=nome, empresa_id=empresa_id)
        
        config.categorias_positivas = json.dumps(categorias_positivas) if categorias_positivas else None
        config.categorias_negativas = json.dumps(categorias_negativas) if categorias_negativas else None
        config.ativa = True
        
        if config.id is None:
            db.session.add(config)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Configuração salva com sucesso!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/configuracao/excluir/<int:id>', methods=['POST'])
@login_required
@empresa_required
def excluir_configuracao(id):
    try:
        empresa_id = session.get('empresa_selecionada')
        config = ConfiguracaoCalculo.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
        
        if config.pode_ser_excluida():
            db.session.delete(config)
            message = 'Configuração excluída com sucesso!'
        else:
            config.inativar(current_user.username)
            message = 'Configuração inativada com sucesso!'
            
        db.session.commit()
        return jsonify({'status': 'success', 'message': message})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Erro: {str(e)}'})

@app.route('/configuracao/reativar/<int:id>', methods=['POST'])
@login_required
def reativar_configuracao(id):
    try:
        empresa_id = session.get('empresa_selecionada')
        config = ConfiguracaoCalculo.query.filter_by(id=id, empresa_id=empresa_id).first_or_404()
        
        config.ativa = True
        config.data_inativacao = None
        config.usuario_inativacao = None
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Configuração reativada com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Erro: {str(e)}'})
    
# APIs do Dashboard
@app.route('/api/dashboard-filtrado', methods=['POST'])
@login_required
@empresa_required
def api_dashboard_filtrado():
    try:
        empresa_id = session.get('empresa_selecionada')
        data = request.get_json()
        ano = int(data.get('ano', datetime.now().year))
        meses = data.get('meses', list(range(1, 13)))
        
        # USAR AS FUNÇÕES COM PADRÃO _rapido (DEFINITIVO)
        indicadores = calcular_indicadores_anuais_rapido(ano, empresa_id)
        dados_grafico = calcular_dados_grafico_rapido(ano, empresa_id)
        
        return jsonify({
            'indicadores': indicadores,
            'dados_grafico': dados_grafico,
            'ano': ano,
            'meses_selecionados': meses
        })
        
    except Exception as e:
        print(f"❌ Erro em api_dashboard_filtrado: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/dados-categorias', methods=['POST'])
@login_required
@empresa_required
def api_dados_categorias():
    try:
        empresa_id = session.get('empresa_selecionada')
        if not empresa_id:
            return jsonify({'error': 'Nenhuma empresa selecionada'}), 400
        
        data = request.get_json()
        categorias_ids = data.get('categorias', [])
        ano = int(data.get('ano', datetime.now().year))
        meses = data.get('meses', list(range(1, 13)))
        
        resultado = []
        
        for categoria_id in categorias_ids:
            # Verificar se a categoria pertence à empresa
            categoria = Categoria.query.filter_by(
                id=categoria_id, 
                empresa_id=empresa_id
            ).first()
            
            if not categoria:
                continue
            
            total = 0
            for mes in meses:
                valor_mes = db.session.query(func.sum(Conta.valor)).filter(
                    Conta.categoria_id == categoria_id,
                    Conta.empresa_id == empresa_id,
                    extract('month', Conta.data) == mes,
                    extract('year', Conta.data) == ano,
                    Conta.ativa == True
                ).scalar() or 0
                total += float(valor_mes)
            
            resultado.append({
                'id': categoria.id,
                'nome': categoria.nome,
                'valor': total
            })
        
        resultado.sort(key=lambda x: x['valor'], reverse=True)
        
        return jsonify(resultado)
        
    except Exception as e:
        #print(f"❌ ERRO em api_dados_categorias: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Rotas de Usuários
@app.route('/usuarios')
@login_required
def listar_usuarios():
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem gerenciar usuários.', 'error')
        return redirect(url_for('dashboard'))
    
    usuarios = Usuario.query.all()
    return render_template('usuarios/lista.html', usuarios=usuarios)

@app.route('/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(id):
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem editar usuários.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        usuario = Usuario.query.get_or_404(id)
        form = UsuarioEditForm(obj=usuario)
        
        # Carregar empresas disponíveis
        empresas_disponiveis = Empresa.query.filter_by(ativa=True).all()
        
        if form.validate_on_submit():
            # Lógica de atualização...
            usuario.username = form.username.data
            usuario.email = form.email.data
            usuario.nome_completo = form.nome_completo.data
            usuario.is_admin = form.is_admin.data
            usuario.ativo = form.ativo.data
            
            if form.password.data:
                usuario.set_password(form.password.data)
            
            # Atualizar empresas associadas
            empresas_selecionadas_ids = request.form.getlist('empresas_selecionadas')
            if empresas_selecionadas_ids:
                empresas_selecionadas = Empresa.query.filter(Empresa.id.in_(empresas_selecionadas_ids)).all()
                usuario.empresas = empresas_selecionadas
            else:
                usuario.empresas = []
            
            db.session.commit()
            flash(f'Usuário {usuario.username} atualizado com sucesso!', 'success')
            return redirect(url_for('listar_usuarios'))
        
        return render_template('usuarios/editar.html', 
                             form=form, 
                             usuario=usuario, 
                             empresas_disponiveis=empresas_disponiveis)
        
    except Exception as e:
        #print(f"Erro ao editar usuário: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao carregar usuário: {str(e)}', 'error')
        return redirect(url_for('listar_usuarios'))


@app.route('/usuarios/inativar/<int:id>', methods=['POST'])
@login_required
def inativar_usuario(id):
    if not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'Acesso negado'}), 403
    
    try:
        usuario = Usuario.query.get_or_404(id)
        
        if usuario.id == current_user.id:
            return jsonify({'status': 'error', 'message': 'Você não pode inativar sua própria conta'})
        
        usuario.ativo = not usuario.ativo
        db.session.commit()
        
        status = 'ativado' if usuario.ativo else 'inativado'
        return jsonify({'status': 'success', 'message': f'Usuário {status} com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Erro: {str(e)}'})
    
@app.route('/usuarios/toggle/<int:id>', methods=['POST'])
@login_required
def toggle_usuario(id):
    if not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'Acesso negado'}), 403
    
    try:
        usuario = Usuario.query.get_or_404(id)
        if usuario.id == current_user.id:
            return jsonify({'status': 'error', 'message': 'Você não pode alterar o status da sua própria conta!'})
        
        usuario.ativo = not usuario.ativo
        db.session.commit()
        
        status = 'ativado' if usuario.ativo else 'desativado'
        return jsonify({'status': 'success', 'message': f'Usuário {status} com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Erro ao alterar usuário: {str(e)}'})

@app.route('/usuarios/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_usuario(id):
    if not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'Acesso negado'}), 403
    
    try:
        usuario = Usuario.query.get_or_404(id)
        
        if usuario.id == current_user.id:
            return jsonify({'status': 'error', 'message': 'Você não pode excluir sua própria conta!'})
        
        if usuario.is_admin:
            outros_admins = Usuario.query.filter(Usuario.is_admin == True, Usuario.id != id, Usuario.ativo == True).count()
            if outros_admins == 0:
                return jsonify({'status': 'error', 'message': 'Não é possível excluir o último administrador ativo!'})
        
        db.session.delete(usuario)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Usuário excluído com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Erro ao excluir usuário: {str(e)}'})

# Rotas de Empresas
@app.route('/empresas', methods=['GET'])
@login_required
def empresas():
    try:
        # Usuários comuns só veem suas empresas associadas
        if current_user.is_admin:
            empresas = Empresa.query.all()
        else:
            empresas = current_user.get_empresas_acessiveis()
        
    except Exception as e:
        #print(f"Erro ao listar empresas: {e}")
        empresas = []
        flash('Erro ao carregar empresas!', 'error')
    
    form = EmpresaForm()
    return render_template('empresas/cadastro_empresas.html', empresas=empresas, form=form)

@app.route('/empresas/nova', methods=['POST'])
@login_required
def nova_empresa():

    # Apenas administradores podem criar empresas
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem criar empresas.', 'error')
        return redirect(url_for('empresas'))
    form = EmpresaForm()

    if form.validate_on_submit():
        try:
            nome_banco = f"empresa_{form.cnpj.data.replace('.', '').replace('/', '').replace('-', '')}.db"
            clientes_dir = app.config.get('CLIENTES_DIR', 'clientes')
            os.makedirs(clientes_dir, exist_ok=True)
            caminho_banco = os.path.join(clientes_dir, nome_banco)
            empresa = Empresa(
                cnpj=form.cnpj.data,
                nome=form.nome.data,
                caminho_banco=caminho_banco
            )
            open(caminho_banco, 'a').close()
            db.session.add(empresa)
            db.session.commit()
            flash('Empresa cadastrada com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar empresa: {str(e)}', 'danger')
    else:
        flash('Dados inválidos para cadastro de empresa.', 'danger')
    return redirect(url_for('empresas'))

@app.route('/empresas/selecionar/<int:id>', methods=['POST'])
@login_required
def selecionar_empresa(id):
    try:
        # Verificar se o usuário pode acessar esta empresa
        if not current_user.pode_acessar_empresa(id):
            flash('Você não tem permissão para acessar esta empresa.', 'error')
            return redirect(url_for('empresas'))
        
        empresa = Empresa.query.filter_by(id=id, ativa=True).first()
        if empresa:
            session['empresa_selecionada'] = empresa.id
            flash(f'Empresa "{empresa.nome}" selecionada com sucesso!', 'success')
        else:
            flash('Empresa não encontrada ou inativa.', 'error')
    except Exception as e:
        flash(f'Erro ao selecionar empresa: {str(e)}', 'error')
    
    return redirect(url_for('empresas'))

@app.route('/empresas/editar/<int:id>', methods=['POST'])
@login_required
def editar_empresa(id):

    if not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'Acesso negado. Apenas administradores podem editar empresas.'}), 403
    
    try:
        empresa = Empresa.query.get_or_404(id)
        
        nome = request.form.get('nome')
        if nome:
            empresa.nome = nome
            db.session.commit()
            return jsonify({'status': 'success', 'message': 'Empresa atualizada com sucesso!'})
        else:
            return jsonify({'status': 'error', 'message': 'Nome da empresa é obrigatório'})
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Erro ao atualizar empresa: {str(e)}'})
    
@app.route('/empresas/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_empresa(id):
    try:
        empresa = Empresa.query.get_or_404(id)
        
        # Verificar se pode ser excluída ou deve ser inativada
        if empresa.pode_ser_excluida():
            # Pode excluir fisicamente
            db.session.delete(empresa)
            db.session.commit()
            flash('Empresa excluída com sucesso!', 'success')
        else:
            # Deve inativar
            empresa.inativar(current_user.username)
            db.session.commit()
            flash('Empresa inativada com sucesso! (Possui dados vinculados)', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao processar empresa: {str(e)}', 'error')
    
    return redirect(url_for('empresas'))

@app.route('/empresas/reativar/<int:id>', methods=['POST'])
@login_required
def reativar_empresa(id):
    try:
        empresa = Empresa.query.get_or_404(id)
        empresa.ativa = True
        empresa.data_inativacao = None
        empresa.usuario_inativacao = None
        db.session.commit()
        flash('Empresa reativada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao reativar empresa: {str(e)}', 'error')
    
    return redirect(url_for('empresas'))


@app.route('/empresas/exportar/<int:id>')
@login_required
def exportar_banco(id):
    empresa = Empresa.query.get_or_404(id)
    return send_file(
        empresa.caminho_banco,
        as_attachment=True,
        download_name=f"backup_{empresa.cnpj}.db"
    )

@app.route('/usuarios/novo', methods=['GET', 'POST'])
@login_required
def novo_usuario():
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem criar usuários.', 'error')
        return redirect(url_for('dashboard'))
    
    form = UsuarioForm()
    
    # ADICIONE ESTA LINHA: Definir empresas_disponiveis
    empresas_disponiveis = Empresa.query.filter_by(ativa=True).all()
    
    if form.validate_on_submit():
        try:
            # Verificar se username já existe
            if Usuario.query.filter_by(username=form.username.data).first():
                flash('Nome de usuário já existe!', 'error')
                return render_template('usuarios/novo.html', form=form, empresas_disponiveis=empresas_disponiveis)
            
            # Verificar se email já existe
            if Usuario.query.filter_by(email=form.email.data).first():
                flash('Email já está cadastrado!', 'error')
                return render_template('usuarios/novo.html', form=form, empresas_disponiveis=empresas_disponiveis)
            
            # Criar usuário
            usuario = Usuario(
                username=form.username.data,
                email=form.email.data,
                nome_completo=form.nome_completo.data,
                is_admin=form.is_admin.data
            )
            usuario.set_password(form.password.data)
            
            # Obter empresas selecionadas dos checkboxes
            empresas_selecionadas_ids = request.form.getlist('empresas_selecionadas')
            if empresas_selecionadas_ids:
                empresas_selecionadas = Empresa.query.filter(Empresa.id.in_(empresas_selecionadas_ids)).all()
                usuario.empresas = empresas_selecionadas
            
            db.session.add(usuario)
            db.session.commit()
            
            flash(f'Usuário {usuario.username} criado com sucesso!', 'success')
            return redirect(url_for('listar_usuarios'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar usuário: {str(e)}', 'error')
    
    # SEMPRE retornar com empresas_disponiveis definida
    return render_template('usuarios/novo.html', form=form, empresas_disponiveis=empresas_disponiveis)

@app.route('/empresas/importar', methods=['POST'])
@login_required
def importar_banco():
    arquivo = request.files.get('arquivo')
    if not arquivo or not arquivo.filename.endswith('.db'):
        flash('Selecione um arquivo .db válido.', 'danger')
        return redirect(url_for('empresas'))
    
    clientes_dir = app.config.get('CLIENTES_DIR', 'clientes')
    os.makedirs(clientes_dir, exist_ok=True)
    caminho = os.path.join(clientes_dir, arquivo.filename)
    arquivo.save(caminho)
    
    empresa = Empresa(
        cnpj=arquivo.filename.split('_')[1].replace('.db', ''),
        nome="Empresa Importada",
        caminho_banco=caminho
    )
    db.session.add(empresa)
    db.session.commit()
    flash('Banco de dados importado com sucesso!', 'success')
    return redirect(url_for('empresas'))

def criar_usuario_admin():
    """Cria usuário administrador padrão se não existir"""
    admin = Usuario.query.filter_by(username='admin').first()
    if not admin:
        admin = Usuario(
            username='admin',
            email='admin@elevalucro.com',
            nome_completo='Administrador ELEVALUCRO',
            is_admin=True,
            ativo=True
        )
        admin.set_password('123456')
        db.session.add(admin)
        db.session.commit()

def empresa_required(f):
    """Decorator para garantir que uma empresa esteja selecionada"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        empresa_id = session.get('empresa_selecionada')
        if not empresa_id:
            flash('Selecione uma empresa primeiro para acessar esta funcionalidade!', 'warning')
            return redirect(url_for('empresas'))
        
        # Verificar se a empresa ainda existe e está ativa
        empresa = Empresa.query.filter_by(id=empresa_id, ativa=True).first()
        if not empresa:
            session.pop('empresa_selecionada', None)
            flash('A empresa selecionada não está mais disponível. Selecione uma empresa válida.', 'warning')
            return redirect(url_for('empresas'))
        
        return f(*args, **kwargs)
    return decorated_function

# Criar tabelas e usuário admin
with app.app_context():
    db.create_all()
    criar_usuario_admin()
    #print("Banco de dados criado/verificado com sucesso!")

if __name__ == '__main__':
    #print("Acesse: http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)
