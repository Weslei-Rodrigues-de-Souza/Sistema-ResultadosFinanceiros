from flask import Blueprint, render_template, request, redirect, url_for, flash
from __app import db
from __app.__models import Categoria, Conta, ConfiguracaoCalculo, TipoConta
from app.forms import CategoriaForm, ContaForm, ConfiguracaoCalculoForm
from datetime import datetime
from sqlalchemy.exc import OperationalError

main = Blueprint('main', __name__)

@main.route('/')
def dashboard():
    try:
        # Dashboard com tratamento de erro
        total_categorias = Categoria.query.filter_by(ativa=True).count()
        total_contas = Conta.query.count()
        
        # Calcular totais básicos
        total_receitas = 0
        total_despesas = 0
        
        try:
            # Buscar receitas
            receitas = db.session.query(db.func.sum(Conta.valor)).join(Categoria).filter(
                Categoria.tipo == TipoConta.RECEITA
            ).scalar()
            total_receitas = float(receitas) if receitas else 0
            
            # Buscar despesas
            despesas = db.session.query(db.func.sum(Conta.valor)).join(Categoria).filter(
                Categoria.tipo.in_([TipoConta.DESPESA, TipoConta.CUSTO, TipoConta.IMPOSTO])
            ).scalar()
            total_despesas = float(despesas) if despesas else 0
            
        except Exception as e:
            print(f"Erro ao calcular totais: {e}")
            total_receitas = 0
            total_despesas = 0
        
        # Valores básicos para o dashboard
        indicadores = {
            'faturamento': total_receitas,
            'lucro_bruto': total_receitas - total_despesas,
            'lucro_liquido': total_receitas - total_despesas,
            'reserva_caixa': total_receitas - total_despesas
        }
        
    except OperationalError as e:
        # Se as tabelas não existirem, criar valores padrão
        total_categorias = 0
        total_contas = 0
        indicadores = {
            'faturamento': 0,
            'lucro_bruto': 0,
            'lucro_liquido': 0,
            'reserva_caixa': 0
        }
        flash('Banco de dados inicializado. Comece criando suas categorias!', 'info')
    
    return render_template('index.html', 
                         indicadores=indicadores,
                         total_categorias=total_categorias,
                         total_contas=total_contas)

@main.route('/categorias')
def listar_categorias():
    try:
        categorias = Categoria.query.filter_by(ativa=True).all()
    except OperationalError:
        categorias = []
        flash('Tabelas criadas. Você pode começar a cadastrar categorias!', 'info')
    
    form = CategoriaForm()
    return render_template('categorias/cadastro.html', categorias=categorias, form=form)

@main.route('/categorias/nova', methods=['POST'])
def nova_categoria():
    form = CategoriaForm()
    if form.validate_on_submit():
        try:
            categoria = Categoria(
                nome=form.nome.data,
                tipo=TipoConta(form.tipo.data),
                descricao=form.descricao.data
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
    
    return redirect(url_for('main.listar_categorias'))

@main.route('/contas')
def listar_contas():
    try:
        contas = Conta.query.order_by(Conta.data.desc()).limit(50).all()
        categorias = Categoria.query.filter_by(ativa=True).all()
    except OperationalError:
        contas = []
        categorias = []
        flash('Crie algumas categorias primeiro antes de registrar contas!', 'warning')
    
    form = ContaForm()
    form.categoria_id.choices = [(c.id, c.nome) for c in categorias]
    return render_template('contas/registro.html', contas=contas, form=form)

@main.route('/contas/nova', methods=['POST'])
def nova_conta():
    form = ContaForm()
    try:
        categorias = Categoria.query.filter_by(ativa=True).all()
        form.categoria_id.choices = [(c.id, c.nome) for c in categorias]
    except OperationalError:
        flash('Crie categorias primeiro!', 'error')
        return redirect(url_for('main.listar_categorias'))
    
    if form.validate_on_submit():
        try:
            conta = Conta(
                categoria_id=form.categoria_id.data,
                data=form.data.data,
                valor=form.valor.data,
                descricao=form.descricao.data,
                data_faturamento=form.data_faturamento.data
            )
            db.session.add(conta)
            db.session.commit()
            flash('Conta registrada com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao registrar conta: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')
    
    return redirect(url_for('main.listar_contas'))

@main.route('/categorias/excluir/<int:id>')
def excluir_categoria(id):
    try:
        categoria = Categoria.query.get_or_404(id)
        categoria.ativa = False
        db.session.commit()
        flash('Categoria excluída com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir categoria: {str(e)}', 'error')
    return redirect(url_for('main.listar_categorias'))

@main.route('/contas/excluir/<int:id>')
def excluir_conta(id):
    try:
        conta = Conta.query.get_or_404(id)
        db.session.delete(conta)
        db.session.commit()
        flash('Conta excluída com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir conta: {str(e)}', 'error')
    return redirect(url_for('main.listar_contas'))

@main.route('/configuracao-calculo')
def configuracao_calculo():
    try:
        categorias = Categoria.query.filter_by(ativa=True).all()
        configuracoes = ConfiguracaoCalculo.query.filter_by(ativa=True).all()
    except Exception as e:
        print(f"Erro ao carregar configurações: {e}")
        categorias = []
        configuracoes = []
        flash('Erro ao carregar configurações!', 'error')
    
    return render_template('configuracao/calculo.html', categorias=categorias, configuracoes=configuracoes)

