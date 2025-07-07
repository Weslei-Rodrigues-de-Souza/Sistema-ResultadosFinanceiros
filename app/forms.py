from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField, TextAreaField, SelectMultipleField
from wtforms.validators import DataRequired, NumberRange, Length
from wtforms.widgets import CheckboxInput, ListWidget
from app.models import TipoConta, Categoria

class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class CategoriaForm(FlaskForm):
    nome = StringField('Nome da Categoria', validators=[DataRequired(), Length(min=2, max=100)])
    tipo = SelectField('Tipo', choices=[(tipo.value, tipo.value.title()) for tipo in TipoConta], validators=[DataRequired()])
    descricao = TextAreaField('Descrição')

class ContaForm(FlaskForm):
    categoria_id = SelectField('Categoria', coerce=int, validators=[DataRequired()])
    data = DateField('Data', validators=[DataRequired()])
    valor = DecimalField('Valor', validators=[DataRequired(), NumberRange(min=0.01)], places=2)
    descricao = StringField('Descrição', validators=[Length(max=255)])
    data_faturamento = DateField('Data de Faturamento')

class ConfiguracaoCalculoForm(FlaskForm):
    nome = StringField('Nome do Cálculo', validators=[DataRequired()])
    categorias_positivas = MultiCheckboxField('Categorias que Somam', coerce=int)
    categorias_negativas = MultiCheckboxField('Categorias que Subtraem', coerce=int)

