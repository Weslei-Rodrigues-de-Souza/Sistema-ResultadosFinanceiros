import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Agora importe do arquivo app.py
from app import app, db

def migrar_multiempresa():
    with app.app_context():
        try:
            print("Iniciando migração...")
            
            # Verificar se as colunas já existem
            result = db.engine.execute(text("PRAGMA table_info(categorias)"))
            colunas_categorias = [row[1] for row in result.fetchall()]
            
            if 'empresa_id' not in colunas_categorias:
                print("Adicionando empresa_id na tabela categorias...")
                db.engine.execute(text("ALTER TABLE categorias ADD COLUMN empresa_id INTEGER"))
            else:
                print("Coluna empresa_id já existe na tabela categorias")
            
            result = db.engine.execute(text("PRAGMA table_info(contas)"))
            colunas_contas = [row[1] for row in result.fetchall()]
            
            if 'empresa_id' not in colunas_contas:
                print("Adicionando empresa_id na tabela contas...")
                db.engine.execute(text("ALTER TABLE contas ADD COLUMN empresa_id INTEGER"))
            else:
                print("Coluna empresa_id já existe na tabela contas")
            
            # Buscar primeira empresa para atribuir aos registros existentes
            result = db.engine.execute(text("SELECT id FROM empresas ORDER BY id LIMIT 1"))
            primeira_empresa = result.fetchone()
            
            if primeira_empresa:
                empresa_id = primeira_empresa[0]
                print(f"Atribuindo registros existentes à empresa ID: {empresa_id}")
                
                # Atualizar categorias existentes
                db.engine.execute(
                    text("UPDATE categorias SET empresa_id = :id WHERE empresa_id IS NULL"),
                    {"id": empresa_id}
                )
                
                # Atualizar contas existentes
                db.engine.execute(
                    text("UPDATE contas SET empresa_id = :id WHERE empresa_id IS NULL"),
                    {"id": empresa_id}
                )
                
                print("Registros atualizados com sucesso!")
            else:
                print("Nenhuma empresa encontrada. Crie uma empresa primeiro.")
            
            print("Migração concluída com sucesso!")
            
        except Exception as e:
            print(f"Erro na migração: {e}")
            db.session.rollback()

if __name__ == "__main__":
    migrar_multiempresa()
