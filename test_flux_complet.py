# -*- coding: utf-8 -*-
"""
Test complet du flux du projet AI-Agent.
Verifie la coherence de bout en bout du workflow.
"""

import sys
import os


class FluxAnalyzer:
    """Analyseur de flux du projet."""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.successes = []
    
    def add_issue(self, category, message):
        """Ajoute un probleme critique."""
        self.issues.append((category, message))
    
    def add_warning(self, category, message):
        """Ajoute un avertissement."""
        self.warnings.append((category, message))
    
    def add_success(self, category, message):
        """Ajoute un succes."""
        self.successes.append((category, message))
    
    def analyze_webhook_to_celery_flow(self):
        """Analyse le flux webhook -> celery."""
        print("\n[Analyse 1] Flux Webhook Monday.com -> Celery")
        print("-" * 70)
        
        try:
            with open("services/celery_app.py", "r", encoding="utf-8") as f:
                celery_source = f.read()
            
            with open("services/webhook_service.py", "r", encoding="utf-8") as f:
                webhook_source = f.read()
            
            # Check 1: Webhook retourne task_id
            if '"task_id":' in webhook_source and ("result.get('task_id')" in celery_source or 'result.get("task_id")' in celery_source):
                self.add_success("Webhook->Celery", "task_id transmis correctement")
            else:
                self.add_issue("Webhook->Celery", "task_id non transmis")
            
            # Check 2: Verification des doublons
            if "task_exists" in webhook_source and "task_exists" in celery_source:
                self.add_success("Webhook->Celery", "Detection doublons presente")
            else:
                self.add_warning("Webhook->Celery", "Pas de detection doublons")
            
            # Check 3: Chargement donnees depuis DB
            if "load_task_from_db" in celery_source or "SELECT" in celery_source:
                self.add_success("Webhook->Celery", "Chargement donnees DB present")
            else:
                self.add_issue("Webhook->Celery", "Pas de chargement donnees DB")
            
        except Exception as e:
            self.add_issue("Webhook->Celery", f"Erreur analyse: {e}")
    
    def analyze_celery_to_workflow_flow(self):
        """Analyse le flux celery -> workflow."""
        print("\n[Analyse 2] Flux Celery -> Workflow LangGraph")
        print("-" * 70)
        
        try:
            with open("services/celery_app.py", "r", encoding="utf-8") as f:
                celery_source = f.read()
            
            with open("graph/workflow_graph.py", "r", encoding="utf-8") as f:
                workflow_source = f.read()
            
            # Check 1: Protection contre re-demarrage
            if "check_if_completed_sync" in celery_source:
                self.add_success("Celery->Workflow", "Protection re-demarrage presente")
            else:
                self.add_issue("Celery->Workflow", "Pas de protection re-demarrage")
            
            # Check 2: Passage de task_db_id
            if "task_db_id" in celery_source and "task_db_id" in workflow_source:
                self.add_success("Celery->Workflow", "task_db_id transmis")
            else:
                self.add_issue("Celery->Workflow", "task_db_id non transmis")
            
            # Check 3: Gestion event loop
            if "asyncio.new_event_loop()" in celery_source and "loop.close()" in celery_source:
                self.add_success("Celery->Workflow", "Event loop geree correctement")
            else:
                self.add_warning("Celery->Workflow", "Event loop non geree")
            
        except Exception as e:
            self.add_issue("Celery->Workflow", f"Erreur analyse: {e}")
    
    def analyze_workflow_nodes_flow(self):
        """Analyse le flux entre les noeuds du workflow."""
        print("\n[Analyse 3] Flux entre noeuds du workflow")
        print("-" * 70)
        
        try:
            with open("graph/workflow_graph.py", "r", encoding="utf-8") as f:
                workflow_source = f.read()
            
            # Check 1: Tous les noeuds sont declares
            required_nodes = [
                "prepare_environment",
                "analyze_requirements",
                "implement_task",
                "run_tests",
                "quality_assurance_automation",
                "finalize_pr",
                "monday_validation",
                "merge_after_validation",
                "update_monday"
            ]
            
            missing_nodes = []
            for node in required_nodes:
                if f'add_node("{node}"' not in workflow_source:
                    missing_nodes.append(node)
            
            if not missing_nodes:
                self.add_success("Workflow Nodes", f"Tous les {len(required_nodes)} noeuds declares")
            else:
                self.add_issue("Workflow Nodes", f"Noeuds manquants: {missing_nodes}")
            
            # Check 2: Point d'entree defini
            if 'set_entry_point("prepare_environment")' in workflow_source:
                self.add_success("Workflow Nodes", "Point entree correct")
            else:
                self.add_issue("Workflow Nodes", "Point entree non defini")
            
            # Check 3: Edges definis
            critical_edges = [
                ('prepare_environment", "analyze_requirements', "prepare->analyze"),
                ('analyze_requirements", "implement_task', "analyze->implement"),
                ('finalize_pr", "monday_validation', "finalize->validation"),
                ('merge_after_validation", "update_monday', "merge->update"),
            ]
            
            for edge_str, edge_name in critical_edges:
                if edge_str in workflow_source:
                    self.add_success("Workflow Edges", f"{edge_name} present")
                else:
                    self.add_issue("Workflow Edges", f"{edge_name} manquant")
            
        except Exception as e:
            self.add_issue("Workflow Nodes", f"Erreur analyse: {e}")
    
    def analyze_status_transitions(self):
        """Analyse les transitions de statut."""
        print("\n[Analyse 4] Transitions de statut")
        print("-" * 70)
        
        try:
            with open("services/database_persistence_service.py", "r", encoding="utf-8") as f:
                db_source = f.read()
            
            with open("data/fonction.sql", "r", encoding="utf-8") as f:
                sql_source = f.read()
            
            # Check 1: Protection completed->processing
            if "current_status = await conn.fetchval" in db_source:
                self.add_success("Status Transitions", "Verification statut avant transition")
            else:
                self.add_issue("Status Transitions", "Pas de verification statut")
            
            if 'if current_status == \'completed\'' in db_source:
                self.add_success("Status Transitions", "Protection completed->processing")
            else:
                self.add_issue("Status Transitions", "Pas de protection completed")
            
            # Check 2: Trigger SQL valide transitions
            if "validate_status_transition" in sql_source:
                self.add_success("Status Transitions", "Trigger validation SQL present")
            else:
                self.add_warning("Status Transitions", "Pas de trigger validation SQL")
            
            # Check 3: Transitions identiques autorisees
            if "OLD.internal_status = NEW.internal_status" in sql_source:
                self.add_success("Status Transitions", "Transitions identiques autorisees")
            else:
                self.add_warning("Status Transitions", "Transitions identiques non gerees")
            
        except Exception as e:
            self.add_issue("Status Transitions", f"Erreur analyse: {e}")
    
    def analyze_quality_assurance_flow(self):
        """Analyse le flux d'assurance qualite."""
        print("\n[Analyse 5] Flux Assurance Qualite")
        print("-" * 70)
        
        try:
            with open("nodes/qa_node.py", "r", encoding="utf-8") as f:
                qa_source = f.read()
            
            with open("graph/workflow_graph.py", "r", encoding="utf-8") as f:
                workflow_source = f.read()
            
            # Check 1: QA stocke dans quality_assurance
            if 'state["results"]["quality_assurance"]' in qa_source:
                self.add_success("QA Flow", "Stockage dans quality_assurance")
            else:
                self.add_issue("QA Flow", "Stockage incorrect")
            
            # Check 2: Workflow lit depuis quality_assurance
            if 'results.get("quality_assurance")' in workflow_source:
                self.add_success("QA Flow", "Lecture depuis quality_assurance")
            else:
                self.add_issue("QA Flow", "Lecture depuis mauvaise cle")
            
            # Check 3: Score calcule correctement
            if "_analyze_qa_results" in qa_source:
                self.add_success("QA Flow", "Fonction calcul score presente")
            else:
                self.add_issue("QA Flow", "Pas de calcul score")
            
            # Check 4: Seuil coherent
            if "overall_score >= 30" in qa_source and "< 30" in workflow_source:
                self.add_success("QA Flow", "Seuil coherent (30)")
            else:
                self.add_warning("QA Flow", "Seuils potentiellement incoherents")
            
        except Exception as e:
            self.add_issue("QA Flow", f"Erreur analyse: {e}")
    
    def analyze_pr_creation_flow(self):
        """Analyse le flux de creation PR."""
        print("\n[Analyse 6] Flux Creation Pull Request")
        print("-" * 70)
        
        try:
            with open("nodes/finalize_node.py", "r", encoding="utf-8") as f:
                finalize_source = f.read()
            
            with open("tools/github_tool.py", "r", encoding="utf-8") as f:
                github_source = f.read()
            
            # Check 1: Verification repository_url
            if "repo_url" in finalize_source and "validation_errors" in finalize_source:
                self.add_success("PR Creation", "Validation repository URL")
            else:
                self.add_warning("PR Creation", "Pas de validation URL")
            
            # Check 2: Push avant PR
            if "_push_branch" in finalize_source:
                push_pos = finalize_source.find("_push_branch")
                pr_pos = finalize_source.find("create_pull_request")
                if push_pos < pr_pos:
                    self.add_success("PR Creation", "Push AVANT create PR (correct)")
                else:
                    self.add_issue("PR Creation", "Ordre incorrect push/PR")
            else:
                self.add_issue("PR Creation", "Pas de push branche")
            
            # Check 3: Gestion erreurs push
            if "push_success" in finalize_source:
                self.add_success("PR Creation", "Gestion erreurs push")
            else:
                self.add_warning("PR Creation", "Pas de gestion erreurs push")
            
            # Check 4: Nettoyage LangSmith
            if "langsmith_config._client = None" in finalize_source:
                self.add_success("PR Creation", "Nettoyage LangSmith present")
            else:
                self.add_issue("PR Creation", "Pas de nettoyage LangSmith (risque SIGSEGV)")
            
        except Exception as e:
            self.add_issue("PR Creation", f"Erreur analyse: {e}")
    
    def analyze_human_validation_flow(self):
        """Analyse le flux de validation humaine."""
        print("\n[Analyse 7] Flux Validation Humaine")
        print("-" * 70)
        
        try:
            with open("nodes/monday_validation_node.py", "r", encoding="utf-8") as f:
                validation_source = f.read()
            
            with open("graph/workflow_graph.py", "r", encoding="utf-8") as f:
                workflow_source = f.read()
            
            # Check 1: Creation update Monday
            if "post_validation_update" in validation_source or "monday_validation_service" in validation_source:
                self.add_success("Validation", "Creation update Monday")
            else:
                self.add_warning("Validation", "Pas de creation update")
            
            # Check 2: Attente reply
            if "check_for_human_replies" in validation_source or "timeout" in validation_source:
                self.add_success("Validation", "Attente reply humaine")
            else:
                self.add_issue("Validation", "Pas d'attente reply")
            
            # Check 3: Analyse intention
            if "analyze_human_intention" in validation_source or "approve" in validation_source:
                self.add_success("Validation", "Analyse intention presente")
            else:
                self.add_warning("Validation", "Pas d'analyse intention")
            
            # Check 4: Decision routing
            if "_should_merge_or_debug_after_monday_validation" in workflow_source:
                self.add_success("Validation", "Routing decision present")
            else:
                self.add_issue("Validation", "Pas de routing decision")
            
        except Exception as e:
            self.add_issue("Validation", f"Erreur analyse: {e}")
    
    def analyze_merge_flow(self):
        """Analyse le flux de merge."""
        print("\n[Analyse 8] Flux Merge Pull Request")
        print("-" * 70)
        
        try:
            with open("nodes/merge_node.py", "r", encoding="utf-8") as f:
                merge_source = f.read()
            
            # Check 1: Verification PR existe
            if "pr_info" in merge_source:
                self.add_success("Merge", "Verification PR existe")
            else:
                self.add_warning("Merge", "Pas de verification PR")
            
            # Check 2: Merge PR
            if "merge_pull_request" in merge_source or "_arun" in merge_source:
                self.add_success("Merge", "Appel merge PR present")
            else:
                self.add_issue("Merge", "Pas d'appel merge")
            
            # Check 3: Suppression branche
            if "delete_branch" in merge_source or "delete" in merge_source:
                self.add_success("Merge", "Suppression branche apres merge")
            else:
                self.add_warning("Merge", "Branche non supprimee")
            
        except Exception as e:
            self.add_issue("Merge", f"Erreur analyse: {e}")
    
    def analyze_monday_update_flow(self):
        """Analyse le flux de mise a jour Monday."""
        print("\n[Analyse 9] Flux Mise a jour Monday.com")
        print("-" * 70)
        
        try:
            # Correction: le fichier s'appelle update_node.py
            with open("nodes/update_node.py", "r", encoding="utf-8") as f:
                update_source = f.read()
            
            # Check 1: Update statut
            if "update_item_status" in update_source or "change_column_value" in update_source:
                self.add_success("Monday Update", "Update statut Monday")
            else:
                self.add_issue("Monday Update", "Pas d'update statut")
            
            # Check 2: Ajout commentaire
            if "add_update" in update_source or "create_update" in update_source:
                self.add_success("Monday Update", "Ajout commentaire")
            else:
                self.add_warning("Monday Update", "Pas de commentaire")
            
            # Check 3: Gestion erreurs
            if "try:" in update_source and "except" in update_source:
                self.add_success("Monday Update", "Gestion erreurs presente")
            else:
                self.add_warning("Monday Update", "Pas de gestion erreurs")
            
        except Exception as e:
            self.add_issue("Monday Update", f"Erreur analyse: {e}")
    
    def analyze_error_handling(self):
        """Analyse la gestion globale des erreurs."""
        print("\n[Analyse 10] Gestion globale des erreurs")
        print("-" * 70)
        
        try:
            with open("services/celery_app.py", "r", encoding="utf-8") as f:
                celery_source = f.read()
            
            # Check 1: Dead Letter Queue
            if "handle_dead_letter" in celery_source:
                self.add_success("Error Handling", "Dead Letter Queue presente")
            else:
                self.add_warning("Error Handling", "Pas de DLQ")
            
            # Check 2: Retry logic
            if "retry" in celery_source and "max_retries" in celery_source:
                self.add_success("Error Handling", "Retry logic presente")
            else:
                self.add_warning("Error Handling", "Pas de retry")
            
            # Check 3: Error reporting
            if "logger.error" in celery_source:
                self.add_success("Error Handling", "Logging erreurs present")
            else:
                self.add_warning("Error Handling", "Pas de logging erreurs")
            
        except Exception as e:
            self.add_issue("Error Handling", f"Erreur analyse: {e}")
    
    def print_report(self):
        """Affiche le rapport complet."""
        print("\n" + "="*70)
        print("📊 RAPPORT D'ANALYSE DU FLUX")
        print("="*70 + "\n")
        
        # Issues critiques
        if self.issues:
            print("❌ PROBLEMES CRITIQUES:")
            for category, message in self.issues:
                print(f"   [{category}] {message}")
            print()
        
        # Warnings
        if self.warnings:
            print("⚠️  AVERTISSEMENTS:")
            for category, message in self.warnings:
                print(f"   [{category}] {message}")
            print()
        
        # Successes
        if self.successes:
            print("✅ VERIFICATIONS REUSSIES:")
            for category, message in self.successes:
                print(f"   [{category}] {message}")
            print()
        
        # Summary
        total = len(self.issues) + len(self.warnings) + len(self.successes)
        print("="*70)
        print(f"Total: {len(self.successes)} succes, {len(self.warnings)} warnings, {len(self.issues)} problemes")
        print("="*70)
        
        return len(self.issues) == 0


def main():
    """Fonction principale."""
    print("\n" + "="*70)
    print("🔍 ANALYSE COMPLETE DU FLUX DU PROJET AI-AGENT")
    print("="*70)
    
    analyzer = FluxAnalyzer()
    
    # Executer toutes les analyses
    analyzer.analyze_webhook_to_celery_flow()
    analyzer.analyze_celery_to_workflow_flow()
    analyzer.analyze_workflow_nodes_flow()
    analyzer.analyze_status_transitions()
    analyzer.analyze_quality_assurance_flow()
    analyzer.analyze_pr_creation_flow()
    analyzer.analyze_human_validation_flow()
    analyzer.analyze_merge_flow()
    analyzer.analyze_monday_update_flow()
    analyzer.analyze_error_handling()
    
    # Afficher le rapport
    success = analyzer.print_report()
    
    if success:
        print("\n🎉 Aucun probleme critique detecte!\n")
        return 0
    else:
        print("\n⚠️  Des problemes critiques ont ete detectes. Consultez le rapport ci-dessus.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

