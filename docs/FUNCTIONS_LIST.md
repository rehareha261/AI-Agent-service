# 📋 Liste Complète des Fonctions - AI-Agent

## 📊 Vue d'ensemble

Ce document liste toutes les fonctions à implémenter pour le projet AI-Agent, organisées par module avec leur rôle et priorité.

**Total : 62 fonctions réparties sur 10 modules**

---

## 🚀 ORGANISATION PAR ÉTAPES CHRONOLOGIQUES

### **🎯 ÉTAPE 1 : BASE FONCTIONNELLE (P0) - 33 fonctions**

#### **Phase 1.1 : Infrastructure de base (5 fonctions)**
| **ORDRE** | **MODULE** | **FONCTION** | **RÔLE** | **APPELÉE DANS** | **ENDPOINT** | **POURQUOI MAINTENANT** |
|-----------|------------|--------------|----------|------------------|--------------|-------------------------|
| 1 | config | `get_settings` | Configuration singleton | Tous les modules | ❌ Aucun | Base de tout le système |
| 2 | utils | `configure_logging` | Setup logging | main.py, __init__ | ❌ Aucun | Debugging essentiel |
| 3 | utils | `get_logger` | Récupérer logger | Tous les modules | ❌ Aucun | Utilisé partout |
| 4 | utils | `validate_webhook_signature` | Validation sécurité | services/webhook_service | ❌ Aucun | Sécurité webhook |
| 5 | utils | `sanitize_branch_name` | Nettoyer noms | services/webhook_service | ❌ Aucun | Validation données |

#### **Phase 1.2 : Modèles et outils de base (8 fonctions)**
| **ORDRE** | **MODULE** | **FONCTION** | **RÔLE** | **APPELÉE DANS** | **ENDPOINT** | **POURQUOI MAINTENANT** |
|-----------|------------|--------------|----------|------------------|--------------|-------------------------|
| 6 | tools | `BaseTool.__init__` | Base pour tous les outils | Toutes les classes tools | ❌ Aucun | Architecture fondamentale |
| 7 | tools | `BaseTool._arun` | Méthode async abstraite | Classes héritantes | ❌ Aucun | Interface standard |
| 8 | tools | `BaseTool._run` | Version synchrone | LangChain | ❌ Aucun | Compatibilité LangChain |
| 9 | tools | `BaseTool.log_operation` | Logging opérations | Toutes les tools | ❌ Aucun | Traçabilité |
| 10 | tools | `BaseTool.handle_error` | Gestion d'erreurs | Toutes les tools | ❌ Aucun | Robustesse |
| 11 | utils | `log_workflow_step` | Logger étapes workflow | Tous les nodes | ❌ Aucun | Suivi progression |
| 12 | utils | `log_error` | Logger erreurs contexte | Gestion d'erreurs | ❌ Aucun | Debugging avancé |
| 13 | tools | `MondayTool.__init__` | Initialiser Monday API | services, nodes | ❌ Aucun | Intégration Monday |

#### **Phase 1.3 : Monday.com Integration (7 fonctions)**
| **ORDRE** | **MODULE** | **FONCTION** | **RÔLE** | **APPELÉE DANS** | **ENDPOINT** | **POURQUOI MAINTENANT** |
|-----------|------------|--------------|----------|------------------|--------------|-------------------------|
| 14 | tools | `MondayTool._execute_graphql_query` | Base requêtes Monday | Toutes méthodes Monday | ❌ Aucun | Infrastructure Monday |
| 15 | tools | `MondayTool.parse_monday_webhook` | Parser payload webhook | services/webhook_service | ❌ Aucun | Comprendre les webhooks |
| 16 | tools | `MondayTool._get_item_info` | Infos complètes item | services/webhook_service | ❌ Aucun | Récupérer données tâche |
| 17 | tools | `MondayTool._arun` | Dispatcher actions | services, nodes/update_node | ❌ Aucun | Interface unifiée |
| 18 | tools | `MondayTool._update_item_status` | MAJ statut | MondayTool._arun | ❌ Aucun | Retour vers Monday |
| 19 | tools | `MondayTool._add_comment` | Ajouter commentaire | MondayTool._arun | ❌ Aucun | Communication |
| 20 | services | `WebhookService.__init__` | Init service webhook | main.py | ❌ Aucun | Service principal |

#### **Phase 1.4 : Service Webhook (6 fonctions)**
| **ORDRE** | **MODULE** | **FONCTION** | **RÔLE** | **APPELÉE DANS** | **ENDPOINT** | **POURQUOI MAINTENANT** |
|-----------|------------|--------------|----------|------------------|--------------|-------------------------|
| 21 | services | `WebhookService._validate_signature` | Validation HMAC | process_webhook | ❌ Aucun | Sécurité |
| 22 | services | `WebhookService._extract_column_value` | Extraire données Monday | _create_task_request | ❌ Aucun | Parser données |
| 23 | services | `WebhookService._generate_branch_name` | Générer nom branche | _create_task_request | ❌ Aucun | Convention Git |
| 24 | services | `WebhookService._create_task_request` | Créer objet tâche | process_webhook | ❌ Aucun | Transformation données |
| 25 | services | `WebhookService.process_webhook` | Traiter webhook complet | main.py:receive_monday_webhook | ❌ Aucun | Logique principale |
| 26 | graph | `_create_initial_state` | État initial graphe | run_workflow | ❌ Aucun | Base workflow |

#### **Phase 1.5 : Workflow et API (7 fonctions)**
| **ORDRE** | **MODULE** | **FONCTION** | **RÔLE** | **APPELÉE DANS** | **ENDPOINT** | **POURQUOI MAINTENANT** |
|-----------|------------|--------------|----------|------------------|--------------|-------------------------|
| 27 | graph | `should_debug_or_finalize` | Décision workflow | workflow transitions | ❌ Aucun | Logique conditionnelle |
| 28 | graph | `create_workflow_graph` | Créer graphe LangGraph | run_workflow | ❌ Aucun | Structure workflow |
| 29 | graph | `run_workflow` | Exécuter workflow | services/webhook_service | ❌ Aucun | Orchestration |
| 30 | main | `health_check` | Endpoint santé | FastAPI route | ✅ GET /health | Monitoring |
| 31 | main | `validate_monday_webhook` | Validation GET webhook | FastAPI route | ✅ GET /webhook/monday | Vérification Monday |
| 32 | main | `receive_monday_webhook` | Réception POST webhook | FastAPI route | ✅ POST /webhook/monday | Point d'entrée |
| 33 | main | `process_webhook_background` | Traitement async | Background task | ❌ Aucun | Performance |

---

### **🔄 ÉTAPE 2 : WORKFLOW COMPLET (P1) - 26 fonctions**

#### **Phase 2.1 : Claude Code Tool (8 fonctions)**
| **ORDRE** | **MODULE** | **FONCTION** | **RÔLE** | **APPELÉE DANS** | **ENDPOINT** | **DÉPEND DE** |
|-----------|------------|--------------|----------|------------------|--------------|---------------|
| 34 | tools | `ClaudeCodeTool.__init__` | Init client Claude | Tous les nodes | ❌ Aucun | BaseTool |
| 35 | tools | `ClaudeCodeTool._arun` | Dispatcher Claude | Tous les nodes | ❌ Aucun | BaseTool._arun |
| 36 | tools | `ClaudeCodeTool._clone_repository` | Cloner repo Git | nodes/prepare_node | ❌ Aucun | Git commands |
| 37 | tools | `ClaudeCodeTool._checkout_branch` | Créer/checkout branche | nodes/prepare_node | ❌ Aucun | Git commands |
| 38 | tools | `ClaudeCodeTool._install_dependencies` | Installer deps | nodes/prepare_node | ❌ Aucun | Shell commands |
| 39 | tools | `ClaudeCodeTool._read_file` | Lire fichier | nodes/implement_node, debug_node | ❌ Aucun | File system |
| 40 | tools | `ClaudeCodeTool._write_file` | Écrire fichier | nodes/implement_node, debug_node | ❌ Aucun | File system |
| 41 | tools | `ClaudeCodeTool._run_command` | Exécuter commande | nodes/test_node, prepare_node | ❌ Aucun | Shell access |

#### **Phase 2.2 : Nœuds Workflow (6 fonctions)**
| **ORDRE** | **MODULE** | **FONCTION** | **RÔLE** | **APPELÉE DANS** | **ENDPOINT** | **DÉPEND DE** |
|-----------|------------|--------------|----------|------------------|--------------|---------------|
| 42 | nodes | `prepare_environment` | Préparer environnement | graph/workflow_graph | ❌ Aucun | ClaudeCodeTool |
| 43 | nodes | `implement_task` | Implémenter avec Claude | graph/workflow_graph | ❌ Aucun | ClaudeCodeTool |
| 44 | nodes | `run_tests` | Lancer tests | graph/workflow_graph | ❌ Aucun | ClaudeCodeTool |
| 45 | nodes | `_detect_test_commands` | Détecter commandes test | nodes/test_node:run_tests | ❌ Aucun | File analysis |
| 46 | nodes | `_analyze_test_results` | Analyser résultats | nodes/test_node:run_tests | ❌ Aucun | Test output |
| 47 | nodes | `debug_code` | Débugger erreurs | graph/workflow_graph | ❌ Aucun | ClaudeCodeTool |

#### **Phase 2.3 : GitHub Integration (5 fonctions)**
| **ORDRE** | **MODULE** | **FONCTION** | **RÔLE** | **APPELÉE DANS** | **ENDPOINT** | **DÉPEND DE** |
|-----------|------------|--------------|----------|------------------|--------------|---------------|
| 48 | tools | `GitHubTool.__init__` | Init client GitHub | nodes/finalize_node | ❌ Aucun | BaseTool |
| 49 | tools | `GitHubTool._arun` | Dispatcher GitHub | nodes/finalize_node | ❌ Aucun | BaseTool._arun |
| 50 | tools | `GitHubTool._get_repository` | Récupérer repo object | GitHubTool méthodes internes | ❌ Aucun | GitHub API |
| 51 | tools | `GitHubTool._push_branch` | Pousser branche | GitHubTool._arun | ❌ Aucun | Git + GitHub |
| 52 | tools | `GitHubTool._create_pull_request` | Créer PR | GitHubTool._arun | ❌ Aucun | GitHub API |

#### **Phase 2.4 : Finalisation (7 fonctions)**
| **ORDRE** | **MODULE** | **FONCTION** | **RÔLE** | **APPELÉE DANS** | **ENDPOINT** | **DÉPEND DE** |
|-----------|------------|--------------|----------|------------------|--------------|---------------|
| 53 | nodes | `finalize_pr` | Créer PR finale | graph/workflow_graph | ❌ Aucun | GitHubTool |
| 54 | nodes | `update_monday` | MAJ Monday final | graph/workflow_graph | ❌ Aucun | MondayTool |
| 55 | services | `WebhookService.handle_task_completion` | Gérer fin tâche | nodes/update_node | ❌ Aucun | MondayTool |
| 56 | tools | `MondayTool._complete_task` | Marquer terminé | MondayTool._arun | ❌ Aucun | Monday API |
| 57 | tools | `MondayTool._update_column_value` | MAJ colonne custom | MondayTool._arun | ❌ Aucun | Monday API |
| 58 | utils | `generate_unique_branch_name` | Nom branche unique | services/webhook_service | ❌ Aucun | String utils |
| 59 | utils | `extract_error_details` | Extraire détails erreur | Gestion d'erreurs | ❌ Aucun | Error handling |

---

### **✨ ÉTAPE 3 : OPTIMISATIONS (P2) - 3 fonctions**

| **ORDRE** | **MODULE** | **FONCTION** | **RÔLE** | **APPELÉE DANS** | **ENDPOINT** | **OPTIONNEL** |
|-----------|------------|--------------|----------|------------------|--------------|---------------|
| 60 | tools | `ClaudeCodeTool._analyze_codebase` | Analyse avancée code | nodes/implement_node | ❌ Aucun | Performance |
| 61 | tools | `GitHubTool._add_pr_comment` | Commentaire PR | GitHubTool._arun | ❌ Aucun | UX améliorée |
| 62 | utils | `format_duration` | Formater durée | Logs de performance | ❌ Aucun | Métriques |

---

## 🗃️ TABLEAU PRINCIPAL - TOUTES LES FONCTIONS

| **MODULE** | **CLASSE/FICHIER** | **FONCTION** | **RÔLE** | **APPELÉE DANS** | **PRIORITÉ** |
|------------|-------------------|--------------|----------|------------------|--------------|
| **services** | WebhookService | `__init__` | Initialiser le service webhook | main.py | P0 |
| **services** | WebhookService | `process_webhook` | Traiter un webhook Monday.com | main.py:receive_monday_webhook | P0 |
| **services** | WebhookService | `_validate_signature` | Valider la signature HMAC | process_webhook | P0 |
| **services** | WebhookService | `_create_task_request` | Créer TaskRequest depuis Monday data | process_webhook | P0 |
| **services** | WebhookService | `_extract_column_value` | Extraire valeur colonne Monday | _create_task_request | P0 |
| **services** | WebhookService | `_generate_branch_name` | Générer nom de branche Git | _create_task_request | P0 |
| **services** | WebhookService | `handle_task_completion` | Gérer fin de tâche | nodes/update_node | P1 |
| **tools** | BaseTool | `__init__` | Initialiser outil de base | Toutes les classes tools | P0 |
| **tools** | BaseTool | `_arun` | Méthode abstraite async | Classes héritantes | P0 |
| **tools** | BaseTool | `_run` | Version sync (délègue à _arun) | LangChain | P0 |
| **tools** | BaseTool | `log_operation` | Logger une opération | Toutes les tools | P0 |
| **tools** | BaseTool | `handle_error` | Gestion standardisée d'erreurs | Toutes les tools | P0 |
| **tools** | MondayTool | `__init__` | Initialiser client Monday API | webhook_service, nodes | P0 |
| **tools** | MondayTool | `_arun` | Dispatcher des actions Monday | webhook_service, update_node | P0 |
| **tools** | MondayTool | `_update_item_status` | Mettre à jour statut item | _arun | P0 |
| **tools** | MondayTool | `_add_comment` | Ajouter commentaire à item | _arun | P0 |
| **tools** | MondayTool | `_update_column_value` | Mettre à jour colonne custom | _arun | P1 |
| **tools** | MondayTool | `_get_item_info` | Récupérer infos complètes item | _arun, webhook_service | P0 |
| **tools** | MondayTool | `_complete_task` | Marquer tâche comme terminée | _arun | P1 |
| **tools** | MondayTool | `parse_monday_webhook` | Parser payload webhook Monday | webhook_service | P0 |
| **tools** | MondayTool | `_execute_graphql_query` | Exécuter requête GraphQL | Toutes méthodes Monday | P0 |
| **tools** | GitHubTool | `__init__` | Initialiser client GitHub | finalize_node | P1 |
| **tools** | GitHubTool | `_arun` | Dispatcher actions GitHub | finalize_node | P1 |
| **tools** | GitHubTool | `_create_pull_request` | Créer PR sur GitHub | _arun | P1 |
| **tools** | GitHubTool | `_push_branch` | Pousser branche vers GitHub | _arun | P1 |
| **tools** | GitHubTool | `_add_pr_comment` | Ajouter commentaire à PR | _arun | P2 |
| **tools** | GitHubTool | `_get_repository` | Récupérer objet repository | Méthodes internes | P1 |
| **tools** | ClaudeCodeTool | `__init__` | Initialiser client Claude/Anthropic | Tous les nodes | P1 |
| **tools** | ClaudeCodeTool | `_arun` | Dispatcher actions Claude Code | Tous les nodes | P1 |
| **tools** | ClaudeCodeTool | `_clone_repository` | Cloner repo Git | prepare_node | P1 |
| **tools** | ClaudeCodeTool | `_checkout_branch` | Créer/checkout branche | prepare_node | P1 |
| **tools** | ClaudeCodeTool | `_install_dependencies` | Installer deps (npm/pip) | prepare_node | P1 |
| **tools** | ClaudeCodeTool | `_read_file` | Lire fichier du repo | implement_node, debug_node | P1 |
| **tools** | ClaudeCodeTool | `_write_file` | Écrire/modifier fichier | implement_node, debug_node | P1 |
| **tools** | ClaudeCodeTool | `_run_command` | Exécuter commande shell | test_node, prepare_node | P1 |
| **tools** | ClaudeCodeTool | `_analyze_codebase` | Analyser structure du code | implement_node | P2 |
| **tools** | ClaudeCodeTool | `_generate_code` | Générer code avec Claude | implement_node, debug_node | P1 |
| **nodes** | prepare_node | `prepare_environment` | Préparer environnement de travail | workflow_graph | P1 |
| **nodes** | implement_node | `implement_task` | Implémenter la tâche avec Claude | workflow_graph | P1 |
| **nodes** | test_node | `run_tests` | Lancer et analyser tests | workflow_graph | P1 |
| **nodes** | test_node | `_detect_test_commands` | Détecter commandes de test | run_tests | P1 |
| **nodes** | test_node | `_analyze_test_results` | Analyser résultats de tests | run_tests | P1 |
| **nodes** | debug_node | `debug_code` | Débugger et corriger erreurs | workflow_graph | P1 |
| **nodes** | finalize_node | `finalize_pr` | Créer Pull Request finale | workflow_graph | P1 |
| **nodes** | update_node | `update_monday` | Mettre à jour Monday.com | workflow_graph | P1 |
| **graph** | workflow_graph | `create_workflow_graph` | Créer graphe LangGraph | run_workflow | P0 |
| **graph** | workflow_graph | `run_workflow` | Exécuter workflow complet | webhook_service | P0 |
| **graph** | workflow_graph | `should_debug_or_finalize` | Décision debug vs finalize | workflow transitions | P0 |
| **graph** | workflow_graph | `_create_initial_state` | Créer état initial GraphState | run_workflow | P0 |
| **utils** | logger | `configure_logging` | Configurer système de logs | main.py, __init__ | P0 |
| **utils** | logger | `get_logger` | Récupérer logger pour module | Tous les modules | P0 |
| **utils** | logger | `log_workflow_step` | Logger étape de workflow | Tous les nodes | P0 |
| **utils** | logger | `log_error` | Logger erreur avec contexte | Gestion d'erreurs | P0 |
| **utils** | helpers | `validate_webhook_signature` | Valider signature webhook | webhook_service | P0 |
| **utils** | helpers | `sanitize_branch_name` | Nettoyer nom de branche | webhook_service | P0 |
| **utils** | helpers | `generate_unique_branch_name` | Générer nom branche unique | webhook_service | P1 |
| **utils** | helpers | `extract_error_details` | Extraire détails d'erreur | Gestion d'erreurs | P1 |
| **utils** | helpers | `format_duration` | Formater durée | Logs de performance | P2 |
| **config** | settings | `get_settings` | Récupérer config singleton | Tous les modules | P0 |
| **main** | FastAPI app | `health_check` | Endpoint santé du service | Route GET /health | P0 |
| **main** | FastAPI app | `validate_monday_webhook` | Validation GET webhook Monday | Route GET /webhook/monday | P0 |
| **main** | FastAPI app | `receive_monday_webhook` | Réception POST webhook Monday | Route POST /webhook/monday | P0 |
| **main** | FastAPI app | `process_webhook_background` | Traitement async webhook | Background task | P0 |

---

## 📋 LÉGENDE DES PRIORITÉS

### **P0 - CRITIQUE** (Étape 1 - Test Webhook)
Fonctions essentielles pour faire fonctionner le webhook et les bases du système.
- Services webhook
- Configuration et logging
- Modèles de données de base
- Endpoints FastAPI

### **P1 - IMPORTANT** (Workflow Complet)
Fonctions nécessaires pour le workflow d'automatisation complet.
- Tous les nœuds LangGraph
- Intégrations IA (Claude, GitHub)
- Logique métier principale

### **P2 - BONUS** (Améliorations)
Fonctionnalités avancées et optimisations.
- Fonctions d'analyse avancée
- Métriques et monitoring
- Features optionnelles

---

## 📊 RÉPARTITION PAR MODULE

| **MODULE** | **FONCTIONS** | **P0** | **P1** | **P2** | **COMPLEXITÉ** |
|------------|---------------|--------|--------|--------|----------------|
| services/webhook_service | 7 | 6 | 1 | 0 | Moyenne |
| tools/base_tool | 5 | 5 | 0 | 0 | Faible |
| tools/monday_tool | 9 | 7 | 2 | 0 | Élevée |
| tools/github_tool | 6 | 0 | 5 | 1 | Moyenne |
| tools/claude_code_tool | 9 | 0 | 8 | 1 | Élevée |
| nodes/* | 8 | 0 | 8 | 0 | Moyenne |
| graph/workflow_graph | 4 | 4 | 0 | 0 | Moyenne |
| utils/* | 9 | 6 | 2 | 1 | Faible |
| config/settings | 1 | 1 | 0 | 0 | Faible |
| main.py | 4 | 4 | 0 | 0 | Faible |
| **TOTAL** | **62** | **33** | **26** | **3** | - |

---

## 🎯 PLAN D'IMPLÉMENTATION PAR ÉTAPES

### **ÉTAPE 1 : Webhook Fonctionnel (P0 uniquement)**
- ✅ Configuration et settings
- ✅ Modèles de données (schemas, state)
- ✅ Logging
- ✅ WebhookService de base
- ✅ MondayTool minimal
- ✅ Endpoints FastAPI
- ✅ Workflow graph minimal

### **ÉTAPE 2 : Workflow Complet (P1)**
- 🔄 Tous les nœuds LangGraph
- 🔄 ClaudeCodeTool complet
- 🔄 GitHubTool
- 🔄 Logique métier complète

### **ÉTAPE 3 : Optimisations (P2)**
- 🔮 Fonctions d'analyse avancée
- 🔮 Monitoring et métriques
- 🔮 Features bonus

---

## 📝 NOTES POUR EXCEL

Pour importer dans Excel :
1. Copier le tableau principal
2. Ajouter colonnes : **Statut**, **Assigné**, **Date limite**, **Notes**
3. Filtrer par **Priorité** pour organiser le travail
4. Utiliser **MODULE** pour regrouper les tâches

---

## 🔗 RÉFÉRENCES

- Voir `SETUP_GUIDE.md` pour l'installation
- Voir `docs/ARCHITECTURE.md` pour la vue d'ensemble
- Voir le code existant pour les signatures de fonctions 