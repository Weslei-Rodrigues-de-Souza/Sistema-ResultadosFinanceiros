import sys
import os

# Adicionar o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar diretamente do módulo app
import app
from sqlalchemy import text

def criar_tabelas_plano_contas():
    with app.app.app_context():
        try:
            print("🗄️ Criando tabelas do Plano de Contas...")
            
            # Tabela Grupos
            app.db.engine.execute(text("""
                CREATE TABLE IF NOT EXISTS grupos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    empresa_id INT NOT NULL,
                    categoria_id INT NOT NULL,
                    codigo VARCHAR(10) NOT NULL,
                    nome VARCHAR(100) NOT NULL,
                    descricao TEXT,
                    ativo BOOLEAN DEFAULT TRUE,
                    data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                    data_inativacao DATETIME,
                    usuario_inativacao VARCHAR(100),
                    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
                    FOREIGN KEY (categoria_id) REFERENCES categorias(id),
                    UNIQUE KEY unique_empresa_categoria_codigo (empresa_id, categoria_id, codigo),
                    INDEX idx_grupos_empresa_categoria (empresa_id, categoria_id),
                    INDEX idx_grupos_ativo (ativo)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """))
            
            print("✅ Tabela 'grupos' criada com sucesso!")
            
            # Tabela Plano de Contas
            app.db.engine.execute(text("""
                CREATE TABLE IF NOT EXISTS plano_contas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    empresa_id INT NOT NULL,
                    categoria_id INT NOT NULL,
                    grupo_id INT NOT NULL,
                    codigo VARCHAR(20) NOT NULL,
                    nome VARCHAR(150) NOT NULL,
                    descricao TEXT,
                    tipo_conta ENUM('ATIVO', 'PASSIVO', 'RECEITA', 'DESPESA', 'PATRIMONIO') NOT NULL,
                    aceita_lancamento BOOLEAN DEFAULT TRUE,
                    ativo BOOLEAN DEFAULT TRUE,
                    data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                    data_inativacao DATETIME,
                    usuario_inativacao VARCHAR(100),
                    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
                    FOREIGN KEY (categoria_id) REFERENCES categorias(id),
                    FOREIGN KEY (grupo_id) REFERENCES grupos(id),
                    UNIQUE KEY unique_empresa_codigo (empresa_id, codigo),
                    INDEX idx_plano_empresa_grupo (empresa_id, grupo_id),
                    INDEX idx_plano_ativo (ativo),
                    INDEX idx_plano_tipo (tipo_conta)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """))
            
            print("✅ Tabela 'plano_contas' criada com sucesso!")
            print("🎯 Migração concluída! Estrutura do Plano de Contas implementada.")
            
        except Exception as e:
            print(f"❌ Erro ao criar tabelas: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    criar_tabelas_plano_contas()
