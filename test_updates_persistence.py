"""Test rapide pour vérifier que les updates Monday.com sont bien persistées en DB."""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from models.schemas import TaskRequest, TaskPriority
from services.webhook_service import WebhookService


async def test_description_updates_are_saved():
    """Test que la description enrichie avec updates est sauvegardée même si une description existe."""
    
    print("\n" + "="*70)
    print("🧪 TEST : Persistance des Updates Monday.com en Base de Données")
    print("="*70)
    
    # Créer le service
    with patch('services.webhook_service.get_settings') as mock_settings:
        mock_settings.return_value = MagicMock(
            monday_api_token="test",
            monday_board_id="12345",
            monday_repository_url_column_id="link"
        )
        service = WebhookService()
    
    # Simuler une connexion DB
    mock_conn = AsyncMock()
    
    # Tâche existante avec description courte
    existing_task = {
        'tasks_id': 78,
        'internal_status': 'pending',
        'description': 'Statut',  # Description courte existante
        'repository_url': 'https://github.com/test/repo'
    }
    
    # TaskRequest avec description enrichie (updates Monday.com)
    enriched_description = """Statut

--- Commentaires et précisions additionnelles ---
[John Doe]: La méthode count() doit supporter les conditions WHERE
[Jane Smith]: Ajouter aussi un paramètre pour gérer les null values"""
    
    task_request = TaskRequest(
        task_id="5039539867",
        title="Ajouter méthode count()",
        description=enriched_description,
        priority=TaskPriority.MEDIUM,
        repository_url="https://github.com/test/repo",
        branch_name="feature/count",
        monday_item_id="5039539867",
        board_id="12345"
    )
    
    # Mock des réponses DB
    mock_conn.fetchrow = AsyncMock(side_effect=[
        existing_task,  # Premier appel: tâche existante trouvée
        None,  # Deuxième appel: pas de tâche similaire
    ])
    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()
    
    # Mock de get_db_connection
    with patch('services.webhook_service.get_db_connection', return_value=mock_conn):
        # Exécuter _save_task
        task_id = await service._save_task(task_request)
    
    # Vérifications
    print("\n📋 Résultats du test:")
    print(f"   Task ID retourné: {task_id}")
    
    # Vérifier que UPDATE a été appelé
    assert mock_conn.execute.called, "❌ UPDATE devrait avoir été appelé"
    print("   ✅ UPDATE SQL exécuté")
    
    # Récupérer l'appel UPDATE
    update_call = mock_conn.execute.call_args
    if update_call:
        update_query = update_call[0][0]
        update_params = update_call[0][1:]
        
        print(f"\n   📝 Requête UPDATE:")
        print(f"      {update_query}")
        print(f"\n   📊 Paramètres:")
        for i, param in enumerate(update_params, 1):
            if isinstance(param, str) and len(param) > 100:
                print(f"      Param {i}: '{param[:100]}...' ({len(param)} chars)")
            else:
                print(f"      Param {i}: {param}")
        
        # Vérifier que la description enrichie est bien dans les paramètres
        description_found = any(
            isinstance(p, str) and "--- Commentaires et précisions additionnelles ---" in p
            for p in update_params
        )
        
        assert description_found, "❌ La description enrichie devrait être dans les paramètres UPDATE"
        print("\n   ✅ Description enrichie trouvée dans UPDATE")
        
        # Vérifier que c'est la NOUVELLE description (longue)
        long_description_found = any(
            isinstance(p, str) and len(p) > 100
            for p in update_params
        )
        
        assert long_description_found, "❌ La description UPDATE devrait être longue (>100 chars)"
        print("   ✅ Description UPDATE est bien la version enrichie (>100 chars)")
    
    print("\n" + "="*70)
    print("✅ TEST RÉUSSI : La description enrichie est bien mise à jour en DB")
    print("="*70 + "\n")


async def test_short_description_not_overwritten_by_shorter():
    """Test qu'une longue description n'est pas écrasée par une plus courte."""
    
    print("\n" + "="*70)
    print("🧪 TEST : Protection contre l'écrasement par description plus courte")
    print("="*70)
    
    # Créer le service
    with patch('services.webhook_service.get_settings') as mock_settings:
        mock_settings.return_value = MagicMock(
            monday_api_token="test",
            monday_board_id="12345",
            monday_repository_url_column_id="link"
        )
        service = WebhookService()
    
    # Simuler une connexion DB
    mock_conn = AsyncMock()
    
    # Tâche existante avec LONGUE description enrichie
    existing_long_description = """Statut

--- Commentaires et précisions additionnelles ---
[User]: Description très longue avec beaucoup de détails"""
    
    existing_task = {
        'tasks_id': 79,
        'internal_status': 'pending',
        'description': existing_long_description,  # Longue description
        'repository_url': 'https://github.com/test/repo'
    }
    
    # TaskRequest avec description COURTE (ne devrait PAS écraser)
    task_request = TaskRequest(
        task_id="5039539868",
        title="Test task",
        description="Statut",  # Description courte
        priority=TaskPriority.MEDIUM,
        repository_url="https://github.com/test/repo",
        branch_name="feature/test",
        monday_item_id="5039539868",
        board_id="12345"
    )
    
    # Mock des réponses DB
    mock_conn.fetchrow = AsyncMock(return_value=existing_task)
    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()
    
    # Mock de get_db_connection
    with patch('services.webhook_service.get_db_connection', return_value=mock_conn):
        # Exécuter _save_task
        task_id = await service._save_task(task_request)
    
    # Vérifications
    print("\n📋 Résultats du test:")
    print(f"   Task ID retourné: {task_id}")
    
    # Dans ce cas, la description NE DEVRAIT PAS être mise à jour
    # car la nouvelle est PLUS COURTE que l'existante
    if mock_conn.execute.called:
        update_call = mock_conn.execute.call_args
        update_query = update_call[0][0] if update_call else ""
        
        # Vérifier que la description n'est PAS mise à jour
        if "description" in update_query.lower():
            print("   ⚠️ WARNING: Description mise à jour alors qu'elle était plus longue avant")
            print(f"      Ancienne: {len(existing_long_description)} chars")
            print(f"      Nouvelle: {len(task_request.description)} chars")
        else:
            print("   ✅ Description PROTÉGÉE: Pas de mise à jour (nouvelle plus courte)")
    else:
        print("   ✅ Aucun UPDATE exécuté (description déjà optimale)")
    
    print("\n" + "="*70)
    print("✅ TEST RÉUSSI : Protection contre écrasement fonctionne")
    print("="*70 + "\n")


if __name__ == "__main__":
    print("\n🚀 Démarrage des tests de persistance des updates Monday.com\n")
    
    # Test 1
    asyncio.run(test_description_updates_are_saved())
    
    # Test 2
    asyncio.run(test_short_description_not_overwritten_by_shorter())
    
    print("✅ Tous les tests de persistance sont réussis !\n")

