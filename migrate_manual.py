import pymysql
import hashlib
from datetime import datetime

# Configurações MySQL
# MYSQL_CONFIG = {
#     'host': '162.241.203.176',
#     'port': 3306,
#     'user': 'gerent67_weslei',
#     'password': '1saZfK(rg',
#     'database': 'gerent67_sistemas'
# }

MYSQL_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '992132',
    'database': 'elevalucro_db'
}

def conectar_mysql():
    return pymysql.connect(
        host=MYSQL_CONFIG['host'],
        port=MYSQL_CONFIG['port'],
        user=MYSQL_CONFIG['user'],
        password=MYSQL_CONFIG['password'],
        database=MYSQL_CONFIG['database'],
        charset='utf8mb4'
    )

def criar_estrutura_completa():
    """Cria todas as tabelas necessárias no MySQL"""
    mysql_conn = conectar_mysql()
    cursor = mysql_conn.cursor()
    
    print("🗄️ Criando estrutura completa do banco MySQL...")
    
    # 1. Tabela usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(80) UNIQUE NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            nome_completo VARCHAR(200) NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            ativo BOOLEAN DEFAULT TRUE,
            data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP,
            ultimo_login DATETIME
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    # 2. Tabela empresas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS empresas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            cnpj VARCHAR(18) UNIQUE NOT NULL,
            nome VARCHAR(100) NOT NULL,
            caminho_banco VARCHAR(255) NOT NULL,
            data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP,
            ativa BOOLEAN DEFAULT TRUE,
            data_inativacao DATETIME,
            usuario_inativacao VARCHAR(100)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    # 3. Tabela categorias
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INT AUTO_INCREMENT PRIMARY KEY,
            empresa_id INT NOT NULL,
            nome VARCHAR(50) NOT NULL,
            descricao TEXT,
            eh_faturamento BOOLEAN DEFAULT FALSE,
            ativa BOOLEAN DEFAULT TRUE,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_inativacao DATETIME,
            usuario_inativacao VARCHAR(100),
            FOREIGN KEY (empresa_id) REFERENCES empresas(id),
            UNIQUE KEY unique_empresa_categoria (empresa_id, nome)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    # 4. Tabela contas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            empresa_id INT NOT NULL,
            categoria_id INT NOT NULL,
            data DATE NOT NULL,
            valor DECIMAL(15,2) NOT NULL,
            descricao VARCHAR(255),
            ativa BOOLEAN DEFAULT TRUE,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_inativacao DATETIME,
            usuario_inativacao VARCHAR(100),
            FOREIGN KEY (empresa_id) REFERENCES empresas(id),
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    # 5. Tabela configuracao_calculo
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracao_calculo (
            id INT AUTO_INCREMENT PRIMARY KEY,
            empresa_id INT NOT NULL,
            nome VARCHAR(50) NOT NULL,
            categorias_positivas TEXT,
            categorias_negativas TEXT,
            ativa BOOLEAN DEFAULT TRUE,
            data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            data_inativacao DATETIME,
            usuario_inativacao VARCHAR(100),
            FOREIGN KEY (empresa_id) REFERENCES empresas(id),
            UNIQUE KEY unique_empresa_config (empresa_id, nome)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    # 6. Tabela user_empresas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_empresas (
            user_id INT NOT NULL,
            empresa_id INT NOT NULL,
            data_associacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, empresa_id),
            FOREIGN KEY (user_id) REFERENCES usuarios(id),
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    
    mysql_conn.commit()
    cursor.close()
    mysql_conn.close()
    print("✅ Estrutura de tabelas criada com sucesso!")

def criar_usuario_admin():
    """Cria APENAS o usuário administrador"""
    mysql_conn = conectar_mysql()
    cursor = mysql_conn.cursor()
    
    print("👤 Criando usuário administrador...")
    
    # Verificar se o usuário admin já existe
    cursor.execute("SELECT id FROM usuarios WHERE username = 'admin'")
    if cursor.fetchone():
        print("⚠️ Usuário admin já existe, não será criado novamente.")
        cursor.close()
        mysql_conn.close()
        return
    
    # Criar hash da senha usando o mesmo método do Flask
    from werkzeug.security import generate_password_hash
    password_hash = generate_password_hash('123456')
    
    # Criar usuário admin
    cursor.execute("""
        INSERT INTO usuarios (username, email, password_hash, nome_completo, is_admin, ativo)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, ('admin', 'admin@elevalucro.com', password_hash, 'Administrador do Sistema', True, True))
    
    admin_id = cursor.lastrowid
    mysql_conn.commit()
    cursor.close()
    mysql_conn.close()
    
    print(f"✅ Usuário admin criado com sucesso! (ID: {admin_id})")
    print("📋 Dados de acesso:")
    print("   👤 Usuário: admin")
    print("   🔑 Senha: 123456")

if __name__ == "__main__":
    try:
        print("🚀 Iniciando setup MySQL - APENAS usuário admin")
        print("=" * 50)
        
        # Criar estrutura de tabelas
        criar_estrutura_completa()
        
        # Criar APENAS o usuário admin
        criar_usuario_admin()
        
        print("\n" + "=" * 50)
        print("✅ Setup finalizado!")
        print("🎯 Criado APENAS:")
        print("   - Estrutura de tabelas")
        print("   - Usuário admin")
        print("📝 Nenhum outro registro foi criado")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Erro no setup: {e}")
        import traceback
        traceback.print_exc()
