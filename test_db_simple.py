#!/usr/bin/env python3
"""
Script simple de test pour valider les insertions dans les tables.
N'utilise pas les imports du projet pour éviter les dépendances circulaires.
"""
import asyncio
import asyncpg
import os
from datetime import datetime


async def test_database():
    """Test des insertions dans les tables critiques."""
    
    # Configuration DB depuis Celery logs: postgresql://admin:**@localhost:5432/ai_agent_admin
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))
    db_user = os.getenv("DB_USER", "admin")
    # Essayer plusieurs mots de passe courants
    db_passwords = [
        os.getenv("DB_PASSWORD"),
        "admin",
        "password",
        "admin123",
        "postgres",
        ""  # Pas de mot de passe
    ]
    db_name = os.getenv("DB_NAME", "ai_agent_admin")
    
    print(f"\n🔗 Tentative de connexion à {db_user}@{db_host}:{db_port}/{db_name}")
    
    # Essayer différents mots de passe
    conn = None
    last_error = None
    
    for password in [p for p in db_passwords if p is not None]:
        try:
            print(f"   Essai avec mot de passe: {'***' if password else '(vide)'}")
            conn = await asyncpg.connect(
                host=db_host,
                port=db_port,
                user=db_user,
                password=password,
                database=db_name
            )
            print(f"   ✅ Connexion réussie!")
            break
        except Exception as e:
            last_error = e
            if "password authentication failed" in str(e):
                continue  # Essayer le mot de passe suivant
            else:
                raise  # Autre erreur, on arrête
    
    if not conn:
        print(f"\n❌ Impossible de se connecter à la base de données")
        print(f"Dernière erreur: {last_error}")
        print(f"\n💡 Conseil: Vérifiez les informations de connexion PostgreSQL")
        return False
    
    try:
        print("\n" + "="*70)
        print("📋 TEST 1: Vérification de l'existence des tables")
        print("="*70)
        
        tables = ['human_validations', 'human_validation_responses', 'test_results']
        
        for table in tables:
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = $1
                )
            """, table)
            
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}") if exists else 0
            status = "✅" if exists else "❌"
            print(f"  {status} {table}: {count} enregistrement(s)")
        
        print("\n" + "="*70)
        print("📋 TEST 2: Dernières validations (human_validations)")
        print("="*70)
        
        validations = await conn.fetch("""
            SELECT 
                validation_id, 
                task_title, 
                status, 
                created_at,
                task_id,
                task_run_id,
                array_length(files_modified, 1) as files_count
            FROM human_validations 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        
        if validations:
            print(f"\n  ✅ {len(validations)} validation(s) trouvée(s):\n")
            for i, val in enumerate(validations, 1):
                files_count = val['files_count'] or 0
                print(f"  {i}. ID: {val['validation_id']}")
                print(f"     Tâche: {val['task_title']}")
                print(f"     Status: {val['status']}")
                print(f"     Task ID: {val['task_id']} | Run ID: {val['task_run_id']}")
                print(f"     Fichiers: {files_count} | Créé: {val['created_at']}")
                print()
        else:
            print("\n  ⚠️  Aucune validation trouvée")
        
        print("\n" + "="*70)
        print("📋 TEST 3: Réponses de validation (human_validation_responses)")
        print("="*70)
        
        responses = await conn.fetch("""
            SELECT 
                hvr.validation_id, 
                hvr.response_status, 
                hvr.validated_by,
                hvr.validated_at,
                hvr.should_merge,
                hv.task_title
            FROM human_validation_responses hvr
            JOIN human_validations hv ON hvr.human_validation_id = hv.human_validations_id
            ORDER BY hvr.validated_at DESC 
            LIMIT 10
        """)
        
        if responses:
            print(f"\n  ✅ {len(responses)} réponse(s) trouvée(s):\n")
            for i, resp in enumerate(responses, 1):
                print(f"  {i}. Validation ID: {resp['validation_id']}")
                print(f"     Tâche: {resp['task_title']}")
                print(f"     Décision: {resp['response_status']} | Merge: {resp['should_merge']}")
                print(f"     Par: {resp['validated_by']} | Quand: {resp['validated_at']}")
                print()
        else:
            print("\n  ⚠️  Aucune réponse trouvée")
        
        print("\n" + "="*70)
        print("📋 TEST 4: Résultats de tests (test_results)")
        print("="*70)
        
        tests = await conn.fetch("""
            SELECT 
                tr.test_results_id,
                tr.task_run_id, 
                tr.passed, 
                tr.status,
                tr.tests_total,
                tr.tests_passed,
                tr.tests_failed,
                tr.executed_at,
                t.title as task_title
            FROM test_results tr
            JOIN task_runs runs ON tr.task_run_id = runs.tasks_runs_id
            JOIN tasks t ON runs.task_id = t.tasks_id
            ORDER BY tr.executed_at DESC 
            LIMIT 10
        """)
        
        if tests:
            print(f"\n  ✅ {len(tests)} test(s) trouvé(s):\n")
            for i, test in enumerate(tests, 1):
                status_emoji = "✅" if test['passed'] else "❌"
                print(f"  {i}. {status_emoji} Test ID: {test['test_results_id']}")
                print(f"     Tâche: {test['task_title']}")
                print(f"     Status: {test['status']} | Passé: {test['passed']}")
                print(f"     Tests: {test['tests_passed']}/{test['tests_total']} réussis")
                print(f"     Run ID: {test['task_run_id']} | Exécuté: {test['executed_at']}")
                print()
        else:
            print("\n  ⚠️  Aucun test trouvé")
        
        print("\n" + "="*70)
        print("📊 STATISTIQUES GLOBALES")
        print("="*70)
        
        stats = await conn.fetchrow("""
            SELECT 
                (SELECT COUNT(*) FROM human_validations) as total_validations,
                (SELECT COUNT(*) FROM human_validations WHERE status = 'pending') as pending,
                (SELECT COUNT(*) FROM human_validations WHERE status = 'approved') as approved,
                (SELECT COUNT(*) FROM human_validations WHERE status = 'rejected') as rejected,
                (SELECT COUNT(*) FROM human_validation_responses) as total_responses,
                (SELECT COUNT(*) FROM test_results) as total_tests,
                (SELECT COUNT(*) FROM test_results WHERE passed = true) as passed_tests
        """)
        
        print(f"\n  Validations:")
        print(f"    Total: {stats['total_validations']}")
        print(f"    ⏳ En attente: {stats['pending']}")
        print(f"    ✅ Approuvées: {stats['approved']}")
        print(f"    ❌ Rejetées: {stats['rejected']}")
        print(f"\n  Réponses: {stats['total_responses']}")
        print(f"\n  Tests:")
        print(f"    Total: {stats['total_tests']}")
        print(f"    ✅ Réussis: {stats['passed_tests']}")
        print(f"    ❌ Échoués: {stats['total_tests'] - stats['passed_tests']}")
        
        print("\n" + "="*70)
        print("🔍 RÉSUMÉ")
        print("="*70)
        
        issues = []
        
        if stats['total_validations'] == 0:
            issues.append("❌ Aucune validation dans human_validations")
        
        if stats['total_responses'] == 0:
            issues.append("❌ Aucune réponse dans human_validation_responses")
        
        if stats['total_tests'] == 0:
            issues.append("❌ Aucun test dans test_results")
        
        if issues:
            print(f"\n⚠️  {len(issues)} problème(s) détecté(s):")
            for issue in issues:
                print(f"  {issue}")
            print("\n💡 Conseil: Lancez un workflow complet pour générer des données")
            return False
        else:
            print("\n✅ Toutes les tables sont correctement alimentées!")
            return True
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await conn.close()


if __name__ == "__main__":
    print("\n🧪 Test d'insertion des données en base")
    print("="*70)
    
    try:
        success = asyncio.run(test_database())
        
        print("\n" + "="*70)
        if success:
            print("✅ Tests terminés avec succès!")
            exit(0)
        else:
            print("⚠️  Tests terminés avec des avertissements")
            exit(1)
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        exit(2)
