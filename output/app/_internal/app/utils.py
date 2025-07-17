from __app.__models import db, Conta, Categoria, ConfiguracaoCalculo, TipoConta
from sqlalchemy import extract, func
import json
from datetime import datetime

def calcular_indicadores(ano):
    """Calcula os indicadores financeiros para um ano específico"""
    
    # Faturamento total
    faturamento = db.session.query(func.sum(Conta.valor)).join(Categoria).filter(
        Categoria.tipo == TipoConta.RECEITA,
        extract('year', Conta.data) == ano
    ).scalar() or 0
    
    # Configurações de cálculo
    config_lucro_bruto = ConfiguracaoCalculo.query.filter_by(nome='lucro_bruto', ativa=True).first()
    config_lucro_liquido = ConfiguracaoCalculo.query.filter_by(nome='lucro_liquido', ativa=True).first()
    config_reserva_caixa = ConfiguracaoCalculo.query.filter_by(nome='reserva_caixa', ativa=True).first()
    
    lucro_bruto = calcular_por_configuracao(config_lucro_bruto, ano) if config_lucro_bruto else 0
    lucro_liquido = calcular_por_configuracao(config_lucro_liquido, ano) if config_lucro_liquido else 0
    reserva_caixa = calcular_por_configuracao(config_reserva_caixa, ano) if config_reserva_caixa else 0
    
    return {
        'faturamento': float(faturamento),
        'lucro_bruto': float(lucro_bruto),
        'lucro_liquido': float(lucro_liquido),
        'reserva_caixa': float(reserva_caixa)
    }

def calcular_por_configuracao(config, ano):
    """Calcula um indicador baseado na configuração"""
    if not config:
        return 0
    
    valor_total = 0
    
    # Categorias que somam
    if config.categorias_positivas:
        categorias_pos = json.loads(config.categorias_positivas)
        valor_positivo = db.session.query(func.sum(Conta.valor)).filter(
            Conta.categoria_id.in_(categorias_pos),
            extract('year', Conta.data) == ano
        ).scalar() or 0
        valor_total += valor_positivo
    
    # Categorias que subtraem
    if config.categorias_negativas:
        categorias_neg = json.loads(config.categorias_negativas)
        valor_negativo = db.session.query(func.sum(Conta.valor)).filter(
            Conta.categoria_id.in_(categorias_neg),
            extract('year', Conta.data) == ano
        ).scalar() or 0
        valor_total -= valor_negativo
    
    return valor_total

def gerar_dados_grafico(ano):
    """Gera dados mensais para os gráficos"""
    dados = {
        'meses': ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 
                 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'],
        'lucro_bruto': [],
        'lucro_liquido': [],
        'reserva_caixa': []
    }
    
    for mes in range(1, 13):
        # Aqui você implementaria o cálculo mensal
        # Por simplicidade, vou usar um cálculo básico
        indicadores_mes = calcular_indicadores_mes(ano, mes)
        dados['lucro_bruto'].append(indicadores_mes['lucro_bruto'])
        dados['lucro_liquido'].append(indicadores_mes['lucro_liquido'])
        dados['reserva_caixa'].append(indicadores_mes['reserva_caixa'])
    
    return dados

def calcular_indicadores_mes(ano, mes):
    """Calcula indicadores para um mês específico"""
    # Implementação similar ao calcular_indicadores, mas filtrado por mês
    # Por brevidade, retorno valores exemplo
    return {
        'lucro_bruto': 0,
        'lucro_liquido': 0,
        'reserva_caixa': 0
    }
