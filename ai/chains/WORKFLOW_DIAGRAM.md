# 📊 Diagramme de flux - Intégration LangChain Étape 1

## Vue d'ensemble du flux

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WORKFLOW COMPLET ÉTAPE 1                          │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  Monday.com      │
│  Webhook         │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  main.py         │
│  FastAPI         │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Celery Worker   │
│  RabbitMQ        │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   LANGGRAPH WORKFLOW                                  │
│  ┌──────────┐   ┌──────────┐   ┌─────────────┐   ┌──────────┐      │
│  │ prepare  │──▶│ analyze  │──▶│ IMPLEMENT   │──▶│ test     │ ...  │
│  │ _env     │   │ _req     │   │ _task       │   │          │      │
│  └──────────┘   └──────────┘   └──────┬──────┘   └──────────┘      │
│                                        │                              │
│                                        │ ◄── ÉTAPE 1 ICI             │
└────────────────────────────────────────┼──────────────────────────────┘
                                         │
                                         ▼
```

---

## Zoom sur `implement_task` (nœud modifié)

```
┌─────────────────────────────────────────────────────────────────────┐
│                   nodes/implement_node.py                            │
│                   implement_task(state)                              │
└─────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────┐
    │  1. Initialisation                                │
    │     - Valider état (ensure_state_integrity)      │
    │     - Récupérer working_directory                │
    │     - Initialiser outils (ClaudeCodeTool)        │
    └──────────────────┬───────────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────────┐
    │  2. Analyser structure projet                     │
    │     - Lister fichiers (.py, .js, .json...)       │
    │     - Détecter type de projet                    │
    └──────────────────┬───────────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────────┐
    │  3. Créer prompt d'implémentation                 │
    │     - Inclure task, structure, erreurs           │
    └──────────────────┬───────────────────────────────┘
                       │
                       ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │  ✨ 4. NOUVEAU: Génération plan structuré (ÉTAPE 1)             │
    │                                                                  │
    │  ┌────────────────────────────────────────────────────────┐    │
    │  │  TRY: LangChain Plan Structuré                          │    │
    │  │  ┌────────────────────────────────────────┐             │    │
    │  │  │ generate_implementation_plan(...)      │             │    │
    │  │  │   ├─ Provider: Anthropic (principal)   │             │    │
    │  │  │   │  ├─ Prompt Template                │             │    │
    │  │  │   │  ├─ ChatAnthropic                  │             │    │
    │  │  │   │  └─ PydanticOutputParser           │             │    │
    │  │  │   │                                     │             │    │
    │  │  │   └─ Fallback: OpenAI (si erreur)      │             │    │
    │  │  │      ├─ ChatOpenAI                     │             │    │
    │  │  │      └─ PydanticOutputParser           │             │    │
    │  │  └────────────────┬───────────────────────┘             │    │
    │  │                   │                                      │    │
    │  │                   ▼                                      │    │
    │  │  ┌────────────────────────────────────────┐             │    │
    │  │  │ ImplementationPlan (Pydantic)          │             │    │
    │  │  │   - task_summary                       │             │    │
    │  │  │   - architecture_approach              │             │    │
    │  │  │   - steps: [ImplementationStep...]     │             │    │
    │  │  │   - total_estimated_complexity         │             │    │
    │  │  │   - overall_risk_assessment            │             │    │
    │  │  │   - potential_blockers                 │             │    │
    │  │  └────────────────┬───────────────────────┘             │    │
    │  │                   │                                      │    │
    │  │                   ▼                                      │    │
    │  │  ┌────────────────────────────────────────┐             │    │
    │  │  │ extract_plan_metrics(plan)             │             │    │
    │  │  │   → 8 métriques calculées              │             │    │
    │  │  └────────────────┬───────────────────────┘             │    │
    │  │                   │                                      │    │
    │  │                   ▼                                      │    │
    │  │  ┌────────────────────────────────────────┐             │    │
    │  │  │ Stockage dans state["results"]         │             │    │
    │  │  │   - implementation_plan_structured     │             │    │
    │  │  │   - implementation_plan_metrics        │             │    │
    │  │  └────────────────┬───────────────────────┘             │    │
    │  │                   │                                      │    │
    │  │                   ▼                                      │    │
    │  │  ┌────────────────────────────────────────┐             │    │
    │  │  │ _convert_structured_plan_to_text()     │             │    │
    │  │  │   → implementation_plan (texte)        │             │    │
    │  │  └─────────────────────────────────────────             │    │
    │  └─────────────────────────────────────────────────────────┘    │
    │                                                                  │
    │  ┌────────────────────────────────────────────────────────┐    │
    │  │  CATCH: Exception                                       │    │
    │  │    ├─ Log warning                                       │    │
    │  │    └─ use_legacy_plan = True                            │    │
    │  └────────────────┬───────────────────────────────────────┘    │
    │                   │                                             │
    │                   ▼                                             │
    │  ┌────────────────────────────────────────────────────────┐   │
    │  │  IF use_legacy_plan:                                    │   │
    │  │    Legacy method (ai_hub.generate_code)                 │   │
    │  │      ├─ AIRequest                                       │   │
    │  │      ├─ ai_hub.generate_code(request)                   │   │
    │  │      └─ implementation_plan (texte)                     │   │
    │  └─────────────────────────────────────────────────────────   │
    └─────────────────────────────────────────────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────────┐
    │  5. Exécuter plan d'implémentation                │
    │     - _execute_implementation_plan()             │
    │     - Parser actions                             │
    │     - Appliquer modifications fichiers           │
    └──────────────────┬───────────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────────┐
    │  6. Valider résultats                             │
    │     - Vérifier fichiers modifiés                 │
    │     - Logger métriques                           │
    └──────────────────┬───────────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────────┐
    │  7. Retourner state mis à jour                    │
    └──────────────────────────────────────────────────┘
```

---

## Détail de la chaîne LCEL

```
┌───────────────────────────────────────────────────────────────────────┐
│              ai/chains/implementation_plan_chain.py                    │
│           create_implementation_plan_chain(provider)                   │
└───────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────┐
    │  1. PydanticOutputParser                      │
    │     - Schéma: ImplementationPlan             │
    │     - Génère format_instructions             │
    └──────────────────┬───────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────┐
    │  2. ChatPromptTemplate                        │
    │  ┌─────────────────────────────────────────┐ │
    │  │ System:                                 │ │
    │  │   "Tu es un architecte logiciel..."     │ │
    │  │   {format_instructions}                 │ │
    │  └─────────────────────────────────────────┘ │
    │  ┌─────────────────────────────────────────┐ │
    │  │ User:                                   │ │
    │  │   "Tâche: {task_title}"                 │ │
    │  │   "Description: {task_description}"     │ │
    │  │   "Type: {task_type}"                   │ │
    │  │   "Contexte: {additional_context}"      │ │
    │  └─────────────────────────────────────────┘ │
    └──────────────────┬───────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────┐
    │  3. LLM (ChatAnthropic ou ChatOpenAI)         │
    │     - model: claude-3-5-sonnet-20241022      │
    │              ou gpt-4                        │
    │     - temperature: 0.1 (précision)           │
    │     - max_tokens: 4000                       │
    └──────────────────┬───────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────┐
    │  4. PydanticOutputParser.parse()              │
    │     - Parse JSON response                    │
    │     - Valide avec Pydantic                   │
    │     - Raise si invalide                      │
    └──────────────────┬───────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────┐
    │  5. ImplementationPlan (validé)               │
    │     - Tous les champs typés                  │
    │     - Contraintes respectées                 │
    │     - Prêt à l'emploi                        │
    └───────────────────────────────────────────────┘

    LCEL Expression:
    chain = prompt | llm | parser
```

---

## Double fallback en action

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SCÉNARIOS DE FALLBACK                             │
└─────────────────────────────────────────────────────────────────────┘

SCÉNARIO 1: Tout fonctionne (happy path)
────────────────────────────────────────────────────
generate_implementation_plan(provider="anthropic")
    │
    ├─▶ ChatAnthropic: ✅ SUCCESS
    │
    └─▶ ImplementationPlan validé
        │
        └─▶ Métriques extraites
            │
            └─▶ Conversion en texte
                │
                └─▶ Exécution du plan


SCÉNARIO 2: Anthropic échoue → Fallback OpenAI (Niveau 1)
─────────────────────────────────────────────────────────
generate_implementation_plan(provider="anthropic", fallback=True)
    │
    ├─▶ ChatAnthropic: ❌ ERROR (529 overloaded)
    │
    ├─▶ Log warning: "Anthropic failed, trying OpenAI..."
    │
    ├─▶ ChatOpenAI: ✅ SUCCESS
    │
    └─▶ ImplementationPlan validé
        │
        └─▶ Métriques extraites
            │
            └─▶ Conversion en texte
                │
                └─▶ Exécution du plan


SCÉNARIO 3: LangChain échoue → Fallback Legacy (Niveau 2)
──────────────────────────────────────────────────────────
try:
    generate_implementation_plan(...)
        │
        ├─▶ ChatAnthropic: ❌ ERROR
        │
        ├─▶ ChatOpenAI: ❌ ERROR (tous échouent)
        │
        └─▶ raise Exception
catch Exception:
    │
    ├─▶ Log warning: "LangChain failed, using legacy"
    │
    ├─▶ use_legacy_plan = True
    │
    └─▶ ai_hub.generate_code(ai_request)
        │
        └─▶ Implementation plan (texte brut)
            │
            └─▶ Exécution du plan (comme avant)


RÉSULTAT: Workflow TOUJOURS fonctionnel, zéro régression
```

---

## Flux de données dans `state["results"]`

```
┌─────────────────────────────────────────────────────────────────────┐
│                    STATE ENRICHI APRÈS ÉTAPE 1                       │
└─────────────────────────────────────────────────────────────────────┘

state["results"] = {

    // ✨ NOUVEAU: Plan structuré (si LangChain OK)
    "implementation_plan_structured": {
        "task_summary": "Créer API REST...",
        "architecture_approach": "FastAPI + PostgreSQL",
        "steps": [
            {
                "step_number": 1,
                "title": "Créer modèles Pydantic",
                "description": "Définir User, Post...",
                "files_to_modify": ["models/user.py", "models/post.py"],
                "dependencies": ["pydantic", "sqlalchemy"],
                "estimated_complexity": 4,
                "risk_level": "low",
                "risk_mitigation": "Tests unitaires",
                "validation_criteria": ["Modèles valident", "Tests OK"]
            },
            {
                "step_number": 2,
                "title": "Créer endpoints CRUD",
                ...
            }
        ],
        "total_estimated_complexity": 18,
        "overall_risk_assessment": "Risque modéré",
        "recommended_testing_strategy": "Tests unitaires + intégration",
        "potential_blockers": ["Schéma DB non finalisé"]
    },

    // ✨ NOUVEAU: Métriques calculées
    "implementation_plan_metrics": {
        "total_steps": 5,
        "total_complexity": 18,
        "average_complexity": 3.6,
        "high_risk_steps_count": 1,
        "high_risk_steps_percentage": 20.0,
        "total_files_to_modify": 8,
        "total_blockers": 1,
        "has_critical_risks": false
    },

    // EXISTANT: Autres données (inchangé)
    "ai_messages": [...],
    "error_logs": [...],
    "modified_files": [...],
    "code_changes": {...},
    ...
}
```

---

## Comparaison Avant/Après

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AVANT (Legacy)                                     │
└──────────────────────────────────────────────────────────────────────┘

    ai_hub.generate_code(prompt)
        │
        ├─▶ Anthropic: texte brut
        │   "Créer les fichiers suivants:..."
        │   "1. models/user.py..."
        │   [Texte non structuré]
        │
        └─▶ implementation_plan = texte
            │
            └─▶ Parsing manuel fragile
                ├─▶ Regex pour extraire actions
                ├─▶ Parfois JSON malformé
                ├─▶ _repair_json() si cassé
                └─▶ Pas de métriques

    ❌ Problèmes:
       - Parsing fragile
       - Pas de validation
       - JSON parfois cassé
       - Pas de métriques
       - Difficile à débugger


┌──────────────────────────────────────────────────────────────────────┐
│                    APRÈS (Avec LangChain)                             │
└──────────────────────────────────────────────────────────────────────┘

    generate_implementation_plan()
        │
        ├─▶ ChatPromptTemplate (instructions strictes)
        │
        ├─▶ Anthropic: JSON structuré
        │   {
        │     "task_summary": "...",
        │     "steps": [{...}, {...}],
        │     "total_estimated_complexity": 18,
        │     ...
        │   }
        │
        ├─▶ PydanticOutputParser
        │   ├─ Validation automatique
        │   └─ Raise si invalide
        │
        └─▶ ImplementationPlan (Pydantic)
            │
            ├─▶ Plan structuré garanti valide
            │
            ├─▶ Métriques calculées auto
            │
            └─▶ Conversion texte pour compatibilité

    ✅ Avantages:
       - Zéro parsing fragile
       - Validation stricte
       - JSON toujours valide
       - 8 métriques automatiques
       - Debugging facile (Pydantic errors)
       - Fallback double sécurité
```

---

## Roadmap des étapes suivantes

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ROADMAP COMPLÈTE                              │
└─────────────────────────────────────────────────────────────────────┘

✅ ÉTAPE 1: Plan d'implémentation structuré
    ├─ Fichier: ai/chains/implementation_plan_chain.py
    ├─ Nœud modifié: nodes/implement_node.py
    ├─ Gain: Plans Pydantic + métriques
    └─ Statut: ✅ COMPLÉTÉ

🔄 ÉTAPE 2: Analyse requirements structurée
    ├─ Fichier: ai/chains/analysis_chain.py (à créer)
    ├─ Nœud modifié: nodes/analyze_node.py
    ├─ Gain: Éliminer _repair_json(), validation stricte
    └─ Statut: 🔄 À FAIRE

🔄 ÉTAPE 3: Classification d'erreurs
    ├─ Fichier: ai/chains/error_classification_chain.py (à créer)
    ├─ Nœud modifié: nodes/debug_node.py
    ├─ Gain: Regroupement erreurs, -20% appels redondants
    └─ Statut: 🔄 À FAIRE

🔄 ÉTAPE 4: Factory LLM centralisée
    ├─ Fichier: ai/chains/llm_factory.py (à créer)
    ├─ Modification: Tous les nœuds
    ├─ Gain: with_fallback() natif, nouveau provider = 1 ligne
    └─ Statut: 🔄 À FAIRE

🔄 ÉTAPE 5: Mémoire et cache (optionnel)
    ├─ Modification: Toutes les chaînes
    ├─ Gain: Cache -30% appels, mémoire sessions
    └─ Statut: 🔄 OPTIONNEL


TIMELINE SUGGÉRÉE:
    Étape 1: ✅ 1 jour (fait)
    Étape 2: 🔄 1 jour
    Étape 3: 🔄 1 jour
    Étape 4: 🔄 0.5 jour
    Étape 5: 🔄 0.5 jour (si besoin)
    ─────────────────────
    TOTAL: 4 jours
```

---

## Légende des symboles

```
✅  Complété/Validé
🔄  En cours/À faire
❌  Erreur/Bloqué
⚠️  Attention/Warning
🟢  Risque faible
🟡  Risque moyen
🔴  Risque élevé
📊  Métriques/Analytics
🎯  Objectif
💡  Conseil
📚  Documentation
🧪  Tests
🔧  Configuration
🚀  Déploiement
```

---

**Ce diagramme est une représentation visuelle du flux implémenté.**  
**Pour les détails techniques, consulter `docs/LANGCHAIN_INTEGRATION_STEP1.md`**

