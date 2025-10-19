# 🚀 Guide de démarrage rapide - pg_partman

## ⚡ Installation rapide (Nouvelle installation)

```bash
# 1. Construire l'image PostgreSQL avec pg_partman
docker-compose -f docker-compose.rabbitmq.yml build postgres

# 2. Démarrer PostgreSQL
docker-compose -f docker-compose.rabbitmq.yml up -d postgres

# 3. Vérifier l'installation (attendre ~30 secondes)
docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin -c "
SELECT extname, extversion FROM pg_extension WHERE extname = 'pg_partman';
"

# 4. Vérifier les partitions créées
docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin -c "
SELECT tablename FROM pg_tables 
WHERE tablename LIKE 'webhook_events_%' 
ORDER BY tablename;
"
```

## 🔄 Migration (Installation existante)

```bash
# 1. IMPORTANT : Sauvegarder la base de données
mkdir -p backups
docker exec ai_agent_postgres pg_dump -U admin ai_agent_admin > backups/backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Arrêter tous les services
docker-compose -f docker-compose.rabbitmq.yml down

# 3. Construire la nouvelle image
docker-compose -f docker-compose.rabbitmq.yml build postgres

# 4. Démarrer PostgreSQL seul
docker-compose -f docker-compose.rabbitmq.yml up -d postgres

# 5. Attendre que PostgreSQL soit prêt
sleep 30
docker exec ai_agent_postgres pg_isready -U admin

# 6. Exécuter la migration
docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin < scripts/migrate_to_pg_partman.sql

# 7. Démarrer tous les services
docker-compose -f docker-compose.rabbitmq.yml up -d
```

## ✅ Vérification rapide

```bash
# Tout-en-un : vérifier que tout fonctionne
docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin << 'EOF'
\echo '==========================================\n📋 VÉRIFICATION PG_PARTMAN\n=========================================='

\echo '\n1️⃣ Extension pg_partman:'
SELECT extname, extversion FROM pg_extension WHERE extname = 'pg_partman';

\echo '\n2️⃣ Configuration webhook_events:'
SELECT 
    partition_interval AS "Intervalle",
    premake AS "Partitions futures",
    retention AS "Rétention"
FROM partman.part_config 
WHERE parent_table = 'public.webhook_events';

\echo '\n3️⃣ Partitions créées:'
SELECT COUNT(*) AS "Nombre de partitions"
FROM pg_tables 
WHERE tablename LIKE 'webhook_events_%';

\echo '\n4️⃣ Liste des partitions:'
SELECT 
    tablename AS "Partition",
    pg_size_pretty(pg_total_relation_size('public.'||tablename)) AS "Taille"
FROM pg_tables 
WHERE tablename LIKE 'webhook_events_%'
ORDER BY tablename DESC
LIMIT 6;

\echo '\n✅ Vérification terminée !\n=========================================='
EOF
```

## 🔧 Commandes utiles

### Maintenance manuelle
```bash
# Exécuter la maintenance manuellement
docker exec ai_agent_postgres /usr/local/bin/maintenance-partman.sh
```

### Voir les logs
```bash
# Logs de PostgreSQL
docker-compose -f docker-compose.rabbitmq.yml logs -f postgres

# Logs de maintenance pg_partman
docker exec ai_agent_postgres tail -f /var/log/postgresql/partman-maintenance.log
```

### Tester l'insertion
```bash
docker exec -it ai_agent_postgres psql -U admin -d ai_agent_admin -c "
INSERT INTO webhook_events (source, event_type, payload, headers)
VALUES ('test', 'test_event', '{\"test\": true}'::jsonb, '{}'::jsonb)
RETURNING webhook_events_id, tableoid::regclass AS partition;
"
```

## 📚 Documentation complète

- **Documentation détaillée** : `docs/PG_PARTMAN_IMPLEMENTATION.md`
- **Checklist de vérification** : `docs/VERIFICATION_PG_PARTMAN.md`
- **Script de migration** : `scripts/migrate_to_pg_partman.sql`

## 🆘 Problèmes courants

### Le container ne démarre pas
```bash
# Voir les erreurs
docker logs ai_agent_postgres

# Reconstruire sans cache
docker-compose -f docker-compose.rabbitmq.yml build --no-cache postgres
```

### pg_partman n'est pas installé
```bash
# Vérifier la construction
docker-compose -f docker-compose.rabbitmq.yml build postgres 2>&1 | grep -i partman

# Si erreur, vérifier les logs de build
```

### Les partitions ne sont pas créées
```bash
# Exécuter manuellement la configuration
docker exec -i ai_agent_postgres psql -U admin -d ai_agent_admin < scripts/migrate_to_pg_partman.sql
```

## 📞 Support

En cas de problème :

1. Consultez `docs/VERIFICATION_PG_PARTMAN.md` section "Dépannage"
2. Vérifiez les logs : `docker logs ai_agent_postgres`
3. Vérifiez que tous les fichiers sont présents (voir checklist)

---

**Prêt à déployer ? Suivez les étapes ci-dessus et vérifiez chaque ✅**

