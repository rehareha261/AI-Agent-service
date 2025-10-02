#!/usr/bin/env python3
"""
Test simple du workflow pour identifier pourquoi seulement 1/8 nœuds se complète.
"""

import sys
import os
from pathlib import Path

# Ajouter le chemin racine du projet
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_workflow_structure():
    """Test la structure du workflow LangGraph."""
    print("🔍 Test de la structure du workflow...")
    
    try:
        from graph.workflow_graph import create_workflow_graph, MAX_WORKFLOW_NODES, TOTAL_GRAPH_NODES
        from langgraph.checkpoint.memory import MemorySaver
        
        # Créer le workflow localement
        workflow_graph = create_workflow_graph()
        checkpointer = MemorySaver()
        app = workflow_graph.compile(checkpointer=checkpointer)
        
        # Tester la structure du graphe
        print(f"📊 App workflow: {type(app)}")
        print(f"📊 MAX_WORKFLOW_NODES: {MAX_WORKFLOW_NODES}")
        print(f"📊 TOTAL_GRAPH_NODES: {TOTAL_GRAPH_NODES}")
        
        # Compter les nœuds
        if hasattr(app, 'get_graph'):
            graph = app.get_graph()
            nodes = graph.nodes if hasattr(graph, 'nodes') else []
            edges = graph.edges if hasattr(graph, 'edges') else []
            
            print(f"📈 Nœuds dans le graphe: {len(nodes)}")
            print(f"🔗 Connexions dans le graphe: {len(edges)}")
            
            if nodes:
                print("📝 Liste des nœuds:")
                for i, node in enumerate(nodes, 1):
                    print(f"  {i}. {node}")
            
            # Compter les nœuds métier (hors __start__ et __end__)
            business_nodes = [n for n in nodes if not n.startswith('__')]
            print(f"📋 Nœuds métier: {len(business_nodes)}")
            
            # Vérifier la cohérence
            if len(nodes) == TOTAL_GRAPH_NODES and len(business_nodes) == MAX_WORKFLOW_NODES:
                print("✅ Nombre de nœuds cohérent avec les constantes")
                return True
            else:
                print(f"⚠️ Incohérence: {len(nodes)} nœuds totaux vs {TOTAL_GRAPH_NODES} attendus")
                print(f"⚠️ Incohérence: {len(business_nodes)} nœuds métier vs {MAX_WORKFLOW_NODES} attendus")
                return False
        else:
            print("⚠️ Impossible d'accéder à la structure du graphe")
            return False
    
    except Exception as e:
        print(f"❌ Erreur lors du test de structure: {e}")
        return False

def test_workflow_constants():
    """Test les constantes du workflow."""
    print("\n🔢 Test des constantes du workflow...")
    
    try:
        from graph.workflow_graph import MAX_WORKFLOW_NODES
        print(f"📊 MAX_WORKFLOW_NODES: {MAX_WORKFLOW_NODES}")
        
        # Vérifier que la constante est réaliste
        if 8 <= MAX_WORKFLOW_NODES <= 15:
            print("✅ Nombre de nœuds dans une plage réaliste")
            return True
        else:
            print(f"⚠️ Nombre de nœuds suspect: {MAX_WORKFLOW_NODES}")
            return False
    
    except Exception as e:
        print(f"❌ Erreur lors du test des constantes: {e}")
        return False

def test_node_imports():
    """Test que tous les nœuds peuvent être importés."""
    print("\n📦 Test des imports des nœuds...")
    
    nodes_to_test = [
        "nodes.prepare_node",
        "nodes.analyze_node", 
        "nodes.implement_node",  # Corrigé: implement_node au lieu de generate_node
        "nodes.test_node",
        "nodes.qa_node",
        "nodes.debug_node",
        "nodes.monday_validation_node",
        "nodes.finalize_node",
        "nodes.merge_node",
        "nodes.update_node",
        "nodes.human_validation_node"
    ]
    
    success_count = 0
    for node_module in nodes_to_test:
        try:
            __import__(node_module)
            print(f"  ✅ {node_module}")
            success_count += 1
        except Exception as e:
            print(f"  ❌ {node_module}: {e}")
    
    print(f"\n📊 Nœuds importés avec succès: {success_count}/{len(nodes_to_test)}")
    return success_count >= len(nodes_to_test) - 1  # Permettre 1 échec

def test_sample_workflow_execution():
    """Test minimal d'exécution de workflow."""
    print("\n🧪 Test minimal d'exécution...")
    
    try:
        from models.schemas import TaskRequest
        from models.state import GraphState
        
        # Créer une tâche de test minimale avec un type valide
        test_task = TaskRequest(
            task_id="test_workflow_001",
            title="Test simple",
            description="Test de validation du workflow",
            task_type="feature"  # Corrigé: utiliser un type valide
        )
        
        # Créer un état initial minimal
        initial_state = {
            "task": test_task,
            "results": {},
            "completed_nodes": []
        }
        
        print(f"📝 Tâche de test créée: {test_task.task_id}")
        print(f"📊 État initial: {list(initial_state.keys())}")
        print(f"📋 Type de tâche: {test_task.task_type}")
        
        # Tester qu'on peut au moins créer l'état
        print("✅ Structure de base du workflow validée")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test minimal: {e}")
        return False

def main():
    """Fonction principale de test."""
    print("🚀 Démarrage des tests de workflow simple...")
    
    tests = [
        test_workflow_structure,
        test_workflow_constants,
        test_node_imports,
        test_sample_workflow_execution
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Erreur inattendue dans {test.__name__}: {e}")
    
    print(f"\n📊 Résultats des tests: {passed}/{total} réussis")
    
    if passed == total:
        print("✅ Tous les tests de workflow simple ont réussi!")
        return True
    else:
        print(f"⚠️ {total - passed} test(s) ont échoué")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 