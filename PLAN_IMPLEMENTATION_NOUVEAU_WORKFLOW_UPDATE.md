# 🚀 Plan d'Implémentation - Nouveau Workflow sur Updates Monday

**Date**: 11 octobre 2025  
**Objectif**: Déclencher automatiquement un nouveau workflow quand un nouveau commentaire de **demande** arrive dans les Updates Monday d'une tâche terminée.

---

## 📋 Table des Matières

1. [Contexte et Besoin](#contexte-et-besoin)
2. [Architecture de la Solution](#architecture-de-la-solution)
3. [Étapes d'Implémentation](#étapes-dimplémentation)
4. [Structure de la Base de Données](#structure-de-la-base-de-données)
5. [Fichiers à Modifier](#fichiers-à-modifier)
6. [Tests à Créer](#tests-à-créer)
7. [Checklist de Déploiement](#checklist-de-déploiement)

---

## 🎯 Contexte et Besoin

### Situation Actuelle
- ✅ Le workflow se déclenche quand un nouvel item est créé dans Monday
- ✅ Le workflow attend les réponses de validation dans les Updates
- ❌ Après qu'une tâche soit terminée, un nouveau commentaire ne déclenche PAS de workflow

### Besoin Identifié
Quand une tâche est **terminée** (`internal_status = 'completed'` ou `monday_status = 'Done'`), et qu'un nouveau commentaire **de demande** (pas d'affirmation) arrive dans les Updates Monday :
- ✅ Détecter automatiquement ce commentaire
- ✅ Analyser s'il s'agit d'une **nouvelle demande** (pas juste une affirmation/remerciement)
- ✅ Déclencher un **nouveau workflow** pour traiter cette demande
- ✅ Créer un nouveau `task_run` lié à la même tâche

---

## 🏗️ Architecture de la Solution

### Composants Principaux

```
┌─────────────────────────────────────────────────────────────┐
│                    Monday.com Webhook                        │
│              (create_update / create_reply)                  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│         WebhookPersistenceService                            │
│  _handle_update_event() - MODIFIÉ                           │
│                                                               │
│  1. Récupérer la tâche par pulse_id                         │
│  2. Vérifier le statut de la tâche (completed?)             │
│  3. Analyser le contenu du commentaire avec LLM             │
│  4. Si nouvelle demande → déclencher workflow               │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│         UpdateAnalyzerService (NOUVEAU)                      │
│                                                               │
│  • analyze_update_intent(text) → Intent                     │
│  • is_new_request(text) → bool                              │
│  • extract_requirements(text) → Dict                        │
│  • classify_update_type() → UpdateType                      │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│         WorkflowTriggerService (NOUVEAU)                     │
│                                                               │
│  • trigger_new_workflow_from_update()                       │
│  • create_task_run_from_update()                            │
│  • submit_to_celery()                                       │
└─────────────────────────────────────────────────────────────┘
```

### Flux de Données

```
1. Update Monday → Webhook → FastAPI
                              │
2. Persist Webhook ───────────┤
                              │
3. Check Task Status ─────────┤
                              │
4. Analyze Update (LLM) ──────┤ → Is New Request?
                              │         │
                              │         ├─ NO → Log + Ignorer
                              │         │
                              │         └─ YES → Create TaskRequest
                              │                        │
5. Create new task_run ───────┴────────────────────────┤
                                                       │
6. Submit to Celery Queue ─────────────────────────────┤
                                                       │
7. Execute Workflow ───────────────────────────────────┘
```

---

## 📝 Étapes d'Implémentation

### **ÉTAPE 1 : Créer le Service d'Analyse des Updates** (45 min)

#### Fichier : `services/update_analyzer_service.py`

**Fonctionnalités** :
1. **Analyser l'intention** d'un commentaire avec LLM
2. **Classifier** : Nouvelle demande vs Affirmation/Question/Remerciement
3. **Extraire les requirements** d'une nouvelle demande

**Méthodes principales** :
```python
class UpdateAnalyzerService:
    async def analyze_update_intent(self, update_text: str, context: Dict) -> UpdateIntent
    async def is_new_request(self, update_text: str) -> bool
    async def extract_requirements(self, update_text: str) -> Dict[str, Any]
    def classify_update_type(self, update_text: str) -> UpdateType
```

**Types d'Updates à détecter** :
- ✅ **NEW_REQUEST** : Nouvelle demande d'implémentation
- ⚠️ **MODIFICATION** : Modification d'une feature existante
- 🐛 **BUG_REPORT** : Signalement de bug
- ❓ **QUESTION** : Question (pas d'action)
- 💬 **AFFIRMATION** : Commentaire/Remerciement (pas d'action)
- 📋 **VALIDATION_RESPONSE** : Réponse à une validation (déjà géré)

**Prompt LLM** :
```python
ANALYZE_UPDATE_PROMPT = """
Analyse ce commentaire Monday.com et détermine s'il s'agit d'une NOUVELLE DEMANDE nécessitant un workflow.

CONTEXTE:
- Tâche : {task_title}
- Statut actuel : {task_status}
- Description originale : {original_description}

COMMENTAIRE À ANALYSER:
{update_text}

INSTRUCTIONS:
1. Détermine le TYPE de commentaire :
   - NEW_REQUEST : Nouvelle fonctionnalité/implémentation demandée
   - MODIFICATION : Modification d'une feature existante
   - BUG_REPORT : Signalement de bug nécessitant correction
   - QUESTION : Simple question sans action requise
   - AFFIRMATION : Commentaire/Remerciement
   - VALIDATION_RESPONSE : Réponse à une validation (oui/non/approuvé)

2. Si NEW_REQUEST, MODIFICATION ou BUG_REPORT, extrais :
   - Ce qui est demandé (description claire)
   - Type de tâche (feature/bugfix/refactor/etc)
   - Priorité estimée (low/medium/high/urgent)
   - Fichiers potentiellement concernés

RÉPONDS EN JSON:
{{
  "type": "NEW_REQUEST|MODIFICATION|BUG_REPORT|QUESTION|AFFIRMATION|VALIDATION_RESPONSE",
  "confidence": 0.0-1.0,
  "requires_workflow": true/false,
  "reasoning": "Explication de la décision",
  "extracted_requirements": {{
    "title": "Titre court de la demande",
    "description": "Description détaillée",
    "task_type": "feature|bugfix|refactor|etc",
    "priority": "low|medium|high|urgent",
    "files_mentioned": ["file1.py", "file2.js"],
    "technical_keywords": ["React", "API", "Database"]
  }}
}}
"""
```

---

### **ÉTAPE 2 : Créer le Service de Déclenchement de Workflow** (30 min)

#### Fichier : `services/workflow_trigger_service.py`

**Fonctionnalités** :
1. **Créer un nouveau TaskRequest** depuis un update analysé
2. **Créer un nouveau task_run** lié à la tâche existante
3. **Soumettre à Celery** pour exécution

**Méthodes principales** :
```python
class WorkflowTriggerService:
    async def trigger_workflow_from_update(
        self, 
        task_id: int, 
        update_analysis: UpdateIntent,
        monday_item_id: int,
        update_id: str
    ) -> Dict[str, Any]
    
    async def create_task_request_from_update(
        self,
        original_task: Dict,
        update_analysis: UpdateIntent
    ) -> TaskRequest
    
    async def create_new_task_run(
        self,
        task_id: int,
        task_request: TaskRequest
    ) -> int  # Returns run_id
    
    def submit_to_celery(
        self,
        task_request: TaskRequest,
        priority: int = 5
    ) -> str  # Returns celery_task_id
```

**Logique importante** :
```python
async def trigger_workflow_from_update(self, ...):
    # 1. Récupérer la tâche originale depuis la DB
    original_task = await db_persistence.get_task_by_id(task_id)
    
    # 2. Créer un nouveau TaskRequest basé sur l'update
    task_request = await self.create_task_request_from_update(
        original_task, 
        update_analysis
    )
    
    # 3. Créer un nouveau run dans la DB
    run_id = await self.create_new_task_run(task_id, task_request)
    
    # 4. Logger l'événement
    await db_persistence.log_application_event(
        task_id=task_id,
        level="INFO",
        source_component="workflow_trigger",
        action="new_workflow_triggered_from_update",
        message=f"Nouveau workflow déclenché depuis update: {update_analysis.extracted_requirements.title}",
        metadata={
            "update_id": update_id,
            "run_id": run_id,
            "task_type": task_request.task_type,
            "priority": task_request.priority
        }
    )
    
    # 5. Soumettre à Celery
    celery_task_id = self.submit_to_celery(task_request, priority=7)
    
    # 6. Poster un commentaire dans Monday
    await monday_tool.add_comment(
        item_id=monday_item_id,
        comment=f"🤖 Nouvelle demande détectée et prise en compte !\n\n"
                f"📋 **{task_request.title}**\n"
                f"🎯 Type: {task_request.task_type}\n"
                f"⚡ Priorité: {task_request.priority}\n\n"
                f"Le workflow a été lancé automatiquement."
    )
    
    return {
        "success": True,
        "run_id": run_id,
        "celery_task_id": celery_task_id,
        "task_request": task_request.dict()
    }
```

---

### **ÉTAPE 3 : Modifier le Service de Persistence des Webhooks** (45 min)

#### Fichier : `services/webhook_persistence_service.py`

**Modifications dans `_handle_update_event()`** :

```python
@staticmethod
async def _handle_update_event(payload: Dict[str, Any], webhook_id: int):
    """Traite un événement d'update/commentaire Monday.com."""
    try:
        pulse_id = payload.get("pulseId")
        update_text = payload.get("textBody", "")
        update_id = payload.get("updateId") or payload.get("id")
        
        # Rechercher la tâche liée
        task_id = await db_persistence._find_task_by_monday_id(pulse_id)
        
        if not task_id:
            logger.warning(f"⚠️ Tâche non trouvée pour pulse_id {pulse_id}")
            return
        
        # ✅ NOUVEAU: Récupérer les détails de la tâche
        async with db_persistence.pool.acquire() as conn:
            task_details = await conn.fetchrow("""
                SELECT 
                    tasks_id,
                    monday_item_id,
                    title,
                    description,
                    internal_status,
                    monday_status,
                    repository_url,
                    priority,
                    task_type
                FROM tasks 
                WHERE tasks_id = $1
            """, task_id)
        
        if not task_details:
            logger.error(f"❌ Impossible de récupérer les détails de la tâche {task_id}")
            return
        
        # ✅ NOUVEAU: Vérifier si la tâche est terminée
        is_completed = (
            task_details['internal_status'] == 'completed' or
            task_details['monday_status'] == 'Done'
        )
        
        # Logger le commentaire
        await db_persistence.log_application_event(
            task_id=task_id,
            level="INFO",
            source_component="monday_webhook",
            action="item_update_received",
            message=f"Commentaire Monday.com: {update_text[:200]}...",
            metadata={
                "webhook_id": webhook_id,
                "full_text": update_text,
                "monday_pulse_id": pulse_id,
                "update_id": update_id,
                "task_completed": is_completed
            }
        )
        
        await db_persistence._link_webhook_to_task(webhook_id, task_id)
        
        # ✅ NOUVEAU: Si tâche terminée, analyser le commentaire
        if is_completed:
            logger.info(f"🔍 Tâche {task_id} terminée - analyse du commentaire pour nouveau workflow")
            
            # Initialiser le service d'analyse
            from services.update_analyzer_service import update_analyzer_service
            from services.workflow_trigger_service import workflow_trigger_service
            
            # Préparer le contexte pour l'analyse
            context = {
                "task_title": task_details['title'],
                "task_status": task_details['internal_status'],
                "monday_status": task_details['monday_status'],
                "original_description": task_details['description']
            }
            
            # Analyser l'intention du commentaire
            update_analysis = await update_analyzer_service.analyze_update_intent(
                update_text=update_text,
                context=context
            )
            
            logger.info(f"📊 Analyse update: type={update_analysis.type}, "
                       f"requires_workflow={update_analysis.requires_workflow}, "
                       f"confidence={update_analysis.confidence}")
            
            # ✅ NOUVEAU: Si c'est une nouvelle demande, déclencher le workflow
            if update_analysis.requires_workflow and update_analysis.confidence > 0.7:
                logger.info(f"🚀 Déclenchement d'un nouveau workflow depuis update {update_id}")
                
                try:
                    trigger_result = await workflow_trigger_service.trigger_workflow_from_update(
                        task_id=task_id,
                        update_analysis=update_analysis,
                        monday_item_id=task_details['monday_item_id'],
                        update_id=update_id
                    )
                    
                    if trigger_result['success']:
                        logger.info(f"✅ Nouveau workflow déclenché: run_id={trigger_result['run_id']}, "
                                  f"celery_task_id={trigger_result['celery_task_id']}")
                    else:
                        logger.error(f"❌ Échec déclenchement workflow: {trigger_result.get('error')}")
                        
                except Exception as e:
                    logger.error(f"❌ Erreur lors du déclenchement du workflow: {e}", exc_info=True)
                    # Ne pas bloquer - juste logger l'erreur
            else:
                logger.info(f"ℹ️ Commentaire analysé mais pas de workflow requis: "
                          f"type={update_analysis.type}, confidence={update_analysis.confidence}")
        else:
            logger.info(f"💬 Commentaire traité pour tâche en cours {task_id} (status={task_details['internal_status']})")
                
    except Exception as e:
        logger.error(f"❌ Erreur traitement update event: {e}", exc_info=True)
        raise
```

---

### **ÉTAPE 4 : Ajouter les Modèles de Données** (15 min)

#### Fichier : `models/schemas.py`

**Nouveaux Enums et Classes** :

```python
class UpdateType(str, Enum):
    """Types d'updates Monday détectés."""
    NEW_REQUEST = "new_request"
    MODIFICATION = "modification"
    BUG_REPORT = "bug_report"
    QUESTION = "question"
    AFFIRMATION = "affirmation"
    VALIDATION_RESPONSE = "validation_response"


class UpdateIntent(BaseModel):
    """Intention détectée dans un update Monday."""
    type: UpdateType
    confidence: float = Field(ge=0.0, le=1.0, description="Confiance du LLM (0-1)")
    requires_workflow: bool
    reasoning: str
    extracted_requirements: Optional[Dict[str, Any]] = None
    
    class Config:
        use_enum_values = True


class UpdateAnalysisContext(BaseModel):
    """Contexte pour l'analyse d'un update."""
    task_title: str
    task_status: str
    monday_status: Optional[str] = None
    original_description: str
    task_type: Optional[str] = None
    priority: Optional[str] = None
```

---

### **ÉTAPE 5 : Mettre à Jour la Base de Données** (15 min)

#### Nouvelle Table : `task_update_triggers`

```sql
-- Table pour tracker les déclenchements de workflow depuis des updates
CREATE TABLE IF NOT EXISTS task_update_triggers (
    trigger_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    task_id BIGINT REFERENCES tasks(tasks_id) ON DELETE CASCADE,
    monday_update_id VARCHAR(255) NOT NULL,
    webhook_id BIGINT REFERENCES webhooks(webhook_id) ON DELETE SET NULL,
    update_text TEXT NOT NULL,
    
    -- Analyse LLM
    detected_type VARCHAR(50) NOT NULL,  -- UpdateType enum
    confidence FLOAT NOT NULL,
    requires_workflow BOOLEAN NOT NULL DEFAULT FALSE,
    analysis_reasoning TEXT,
    extracted_requirements JSONB,
    
    -- Workflow déclenché
    triggered_workflow BOOLEAN DEFAULT FALSE,
    new_run_id BIGINT REFERENCES task_runs(tasks_runs_id) ON DELETE SET NULL,
    celery_task_id VARCHAR(255),
    
    -- Métadonnées
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    
    CONSTRAINT unique_monday_update UNIQUE (monday_update_id)
);

CREATE INDEX idx_update_triggers_task_id ON task_update_triggers(task_id);
CREATE INDEX idx_update_triggers_workflow ON task_update_triggers(triggered_workflow) 
    WHERE triggered_workflow = TRUE;
CREATE INDEX idx_update_triggers_created_at ON task_update_triggers(created_at DESC);

COMMENT ON TABLE task_update_triggers IS 'Suivi des déclenchements de workflow depuis des updates Monday';
```

#### Nouvelle colonne dans `task_runs` :

```sql
-- Ajouter une colonne pour lier un run à un update Monday
ALTER TABLE task_runs 
ADD COLUMN IF NOT EXISTS triggered_by_update_id VARCHAR(255);

COMMENT ON COLUMN task_runs.triggered_by_update_id IS 'ID de l''update Monday qui a déclenché ce run';
```

---

### **ÉTAPE 6 : Créer les Tests** (60 min)

#### Fichier : `test_update_workflow_trigger.py`

**Tests à implémenter** :

```python
import pytest
from services.update_analyzer_service import update_analyzer_service
from services.workflow_trigger_service import workflow_trigger_service

class TestUpdateAnalyzer:
    """Tests pour l'analyse des updates Monday."""
    
    @pytest.mark.asyncio
    async def test_detect_new_request(self):
        """Test: Détecter une nouvelle demande."""
        update_text = "Bonjour, j'aimerais ajouter un bouton d'export CSV sur la page des utilisateurs"
        context = {
            "task_title": "Créer dashboard admin",
            "task_status": "completed",
            "original_description": "Dashboard avec liste des utilisateurs"
        }
        
        result = await update_analyzer_service.analyze_update_intent(update_text, context)
        
        assert result.type == "NEW_REQUEST"
        assert result.requires_workflow == True
        assert result.confidence > 0.7
        assert "export" in result.extracted_requirements['description'].lower()
    
    @pytest.mark.asyncio
    async def test_detect_affirmation(self):
        """Test: Détecter une affirmation (pas de workflow)."""
        update_text = "Merci beaucoup, ça fonctionne parfaitement !"
        context = {"task_title": "Test", "task_status": "completed", "original_description": "Test"}
        
        result = await update_analyzer_service.analyze_update_intent(update_text, context)
        
        assert result.type == "AFFIRMATION"
        assert result.requires_workflow == False
    
    @pytest.mark.asyncio
    async def test_detect_bug_report(self):
        """Test: Détecter un signalement de bug."""
        update_text = "Il y a un bug, le bouton ne fonctionne plus sur mobile"
        context = {"task_title": "Feature", "task_status": "completed", "original_description": "Feature"}
        
        result = await update_analyzer_service.analyze_update_intent(update_text, context)
        
        assert result.type == "BUG_REPORT"
        assert result.requires_workflow == True
        assert result.extracted_requirements['task_type'] == "bugfix"
    
    @pytest.mark.asyncio
    async def test_detect_question(self):
        """Test: Détecter une simple question."""
        update_text = "Comment je peux configurer cette feature ?"
        context = {"task_title": "Feature", "task_status": "completed", "original_description": "Feature"}
        
        result = await update_analyzer_service.analyze_update_intent(update_text, context)
        
        assert result.type == "QUESTION"
        assert result.requires_workflow == False


class TestWorkflowTrigger:
    """Tests pour le déclenchement de workflow."""
    
    @pytest.mark.asyncio
    async def test_trigger_workflow_from_update(self):
        """Test: Déclencher un workflow complet depuis un update."""
        # TODO: Mock DB, Mock Celery, etc.
        pass
    
    @pytest.mark.asyncio
    async def test_create_task_request_from_update(self):
        """Test: Créer un TaskRequest depuis une analyse d'update."""
        # TODO: Implémenter
        pass
```

---

## 📂 Fichiers à Créer/Modifier

### **Nouveaux Fichiers** :

1. ✅ `services/update_analyzer_service.py` (Nouveau)
2. ✅ `services/workflow_trigger_service.py` (Nouveau)
3. ✅ `test_update_workflow_trigger.py` (Nouveau)
4. ✅ `data/migration_task_update_triggers.sql` (Nouveau)
5. ✅ `PLAN_IMPLEMENTATION_NOUVEAU_WORKFLOW_UPDATE.md` (Ce fichier)

### **Fichiers à Modifier** :

1. ✅ `services/webhook_persistence_service.py`
   - Modifier `_handle_update_event()`
   
2. ✅ `models/schemas.py`
   - Ajouter `UpdateType`, `UpdateIntent`, `UpdateAnalysisContext`
   
3. ✅ `services/database_persistence_service.py`
   - Ajouter méthodes pour `task_update_triggers`
   - Ajouter `get_task_by_id()` avec tous les détails
   
4. ✅ `main.py`
   - Aucune modification nécessaire (webhook déjà géré)
   
5. ✅ `requirements.txt`
   - Aucune dépendance supplémentaire nécessaire

---

## ✅ Checklist de Déploiement

### **Phase 1 : Développement (2-3 heures)**

- [ ] Créer `services/update_analyzer_service.py` avec analyse LLM
- [ ] Créer `services/workflow_trigger_service.py` avec déclenchement
- [ ] Ajouter les modèles dans `models/schemas.py`
- [ ] Modifier `webhook_persistence_service.py`
- [ ] Ajouter méthodes DB dans `database_persistence_service.py`

### **Phase 2 : Base de Données (30 min)**

- [ ] Créer le script de migration SQL
- [ ] Tester la migration sur une DB de test
- [ ] Appliquer la migration sur la DB de production

### **Phase 3 : Tests (1-2 heures)**

- [ ] Écrire les tests unitaires pour `UpdateAnalyzerService`
- [ ] Écrire les tests unitaires pour `WorkflowTriggerService`
- [ ] Écrire les tests d'intégration complets
- [ ] Tester manuellement avec Monday.com

### **Phase 4 : Déploiement (30 min)**

- [ ] Commit et push du code
- [ ] Redémarrer les services (FastAPI + Celery)
- [ ] Vérifier les logs
- [ ] Tester avec un commentaire réel dans Monday

### **Phase 5 : Monitoring (Continu)**

- [ ] Surveiller les logs pour les déclenchements
- [ ] Vérifier les métriques de confiance du LLM
- [ ] Ajuster les prompts si nécessaire
- [ ] Documenter les cas edge

---

## 🎯 Critères de Succès

1. ✅ Un commentaire de demande sur une tâche terminée déclenche automatiquement un nouveau workflow
2. ✅ Les affirmations/remerciements ne déclenchent PAS de workflow
3. ✅ Le nouveau workflow crée un nouveau `task_run` lié à la même tâche
4. ✅ L'historique complet est conservé dans la DB
5. ✅ Un commentaire de confirmation est posté dans Monday
6. ✅ Le système fonctionne sans intervention manuelle

---

## 🚨 Points d'Attention

### **Sécurité**
- ⚠️ Limiter le nombre de workflows déclenchés par update (max 1)
- ⚠️ Vérifier que l'update n'est pas déjà traité (idempotence)
- ⚠️ Limiter le taux de déclenchement (rate limiting)

### **Performance**
- ⚠️ L'analyse LLM ajoute ~1-2s de latence
- ⚠️ Prévoir un cache pour les analyses similaires
- ⚠️ Utiliser un timeout pour les appels LLM

### **Gestion d'Erreurs**
- ⚠️ Si l'analyse LLM échoue → logger et ignorer (pas de workflow)
- ⚠️ Si Celery échoue → retry automatique
- ⚠️ Si DB échoue → rollback et notification

---

## 📊 Métriques à Suivre

1. **Nombre d'updates analysés** par jour
2. **Taux de déclenchement** (workflows déclenchés / updates analysés)
3. **Confiance moyenne** du LLM dans la détection
4. **Faux positifs** (workflows déclenchés à tort)
5. **Faux négatifs** (demandes manquées)
6. **Temps de réponse** de l'analyse LLM

---

## 🔄 Évolutions Futures

1. **Détection multi-langue** (Français + Anglais)
2. **Analyse de sentiment** pour la priorité
3. **Extraction automatique des fichiers** mentionnés
4. **Suggestion de type de tâche** (feature/bugfix/etc)
5. **Notification Slack/Email** pour les nouvelles demandes
6. **Dashboard de monitoring** des déclenchements

---

## 📚 Documentation Associée

- `SYNTHESE_IMPLEMENTATION_LLM.md` - Première implémentation LLM
- `RAPPORT_VERIFICATION_WORKFLOW.md` - Vérification du workflow actuel
- `GUIDE_IMPLEMENTATION_LLM_DETECTION.md` - Guide détection de langage

---

**Prêt pour l'implémentation ! 🚀**
