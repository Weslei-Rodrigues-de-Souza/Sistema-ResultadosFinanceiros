# Script: corrigir_associacoes_usuarios.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app
from sqlalchemy import text

def corrigir_associacoes_usuarios():
    with app.app.app_context():
        try:
            print("🔧 Verificando e corrigindo associações de usuários...")
            
            with app.db.engine.connect() as connection:
                # 1. Listar todos os usuários não-admin
                usuarios = connection.execute(text(
                    "SELECT id, username, is_admin FROM usuarios WHERE is_admin = 0 OR is_admin IS NULL"
                )).fetchall()
                
                print(f"👤 Usuários comuns encontrados: {len(usuarios)}")
                for user in usuarios:
                    print(f"  - {user[1]} (ID: {user[0]})")
                
                # 2. Listar empresas ativas
                empresas = connection.execute(text(
                    "SELECT id, nome FROM empresas WHERE ativa = 1"
                )).fetchall()
                
                print(f"🏢 Empresas ativas: {len(empresas)}")
                for emp in empresas:
                    print(f"  - {emp[1]} (ID: {emp[0]})")
                
                # 3. Verificar associações existentes
                associacoes = connection.execute(text(
                    """SELECT u.username, e.nome, ue.ativo 
                       FROM usuarios_empresas ue
                       JOIN usuarios u ON ue.usuario_id = u.id
                       JOIN empresas e ON ue.empresa_id = e.id
                       WHERE u.is_admin = 0 OR u.is_admin IS NULL"""
                )).fetchall()
                
                print(f"🔗 Associações existentes para usuários comuns: {len(associacoes)}")
                for assoc in associacoes:
                    status = "ATIVA" if assoc[2] else "INATIVA"
                    print(f"  - {assoc[0]} → {assoc[1]} ({status})")
                
                # 4. Se um usuário específico não tem associações, vamos criar
                print(f"\n🎯 Verificando usuários sem associações...")
                
                for usuario in usuarios:
                    user_id = usuario[0]
                    username = usuario[1]
                    
                    # Verificar se tem associações
                    count_assoc = connection.execute(text(
                        "SELECT COUNT(*) FROM usuarios_empresas WHERE usuario_id = :uid AND ativo = 1"
                    ), {"uid": user_id}).scalar()
                    
                    if count_assoc == 0:
                        print(f"⚠️ Usuário {username} sem associações ativas!")
                        
                        # Para demonstração, vamos associar à primeira empresa ativa
                        # VOCÊ DEVE AJUSTAR ISSO CONFORME SUA REGRA DE NEGÓCIO
                        if empresas:
                            primeira_empresa = empresas[0]
                            connection.execute(text(
                                """INSERT INTO usuarios_empresas (usuario_id, empresa_id, ativo, data_associacao) 
                                   VALUES (:uid, :eid, 1, NOW())"""
                            ), {"uid": user_id, "eid": primeira_empresa[0]})
                            connection.commit()
                            print(f"✅ Associação criada: {username} → {primeira_empresa[1]}")
                    else:
                        print(f"✅ Usuário {username} já tem {count_assoc} associação(ões)")
                
                print(f"\n🎯 Verificação e correção concluída!")
                
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    corrigir_associacoes_usuarios()
