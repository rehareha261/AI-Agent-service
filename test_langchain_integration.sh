#!/bin/bash

# ================================================================
# Script de Test - Intégration LangChain Phases 0-4
# ================================================================
# Ce script exécute tous les tests unitaires des phases LangChain
# et génère un rapport de résultats.
#
# Usage:
#   chmod +x test_langchain_integration.sh
#   ./test_langchain_integration.sh
# ================================================================

set -e  # Arrêter en cas d'erreur

# Couleurs pour le terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Test Intégration LangChain - AI-Agent (Phases 0-4)       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ Erreur: requirements.txt non trouvé${NC}"
    echo "Assurez-vous d'être dans le répertoire racine du projet AI-Agent"
    exit 1
fi

# Activer l'environnement virtuel si disponible
if [ -d "venv" ]; then
    echo -e "${YELLOW}📦 Activation de l'environnement virtuel...${NC}"
    source venv/bin/activate
    echo -e "${GREEN}✅ Environnement virtuel activé${NC}"
else
    echo -e "${YELLOW}⚠️  Pas de venv trouvé, utilisation de l'environnement système${NC}"
fi

echo ""

# Vérifier les dépendances
echo -e "${YELLOW}🔍 Vérification des dépendances LangChain...${NC}"
python -c "import langchain_core; import langchain_anthropic; import langchain_openai; print('✅ Dépendances OK')" 2>/dev/null || {
    echo -e "${RED}❌ Dépendances manquantes${NC}"
    echo "Installation des dépendances..."
    pip install -q langchain-core langchain-anthropic langchain-openai
}

echo ""

# Fonction pour exécuter un test
run_test() {
    local test_file=$1
    local test_name=$2
    local phase=$3
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🧪 Test ${phase}: ${test_name}${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    if pytest "${test_file}" -v --tb=short --no-header 2>&1 | tee /tmp/test_output.txt; then
        local passed=$(grep -c "PASSED" /tmp/test_output.txt || echo "0")
        echo -e "${GREEN}✅ Phase ${phase} - ${test_name}: ${passed} tests passés${NC}"
        return 0
    else
        echo -e "${RED}❌ Phase ${phase} - ${test_name}: ÉCHEC${NC}"
        return 1
    fi
}

# Compteurs
total_tests=0
passed_phases=0
failed_phases=0

# ================================================================
# PHASE 1 - Implementation Plan Chain
# ================================================================
if run_test "tests/test_implementation_plan_chain.py" "Implementation Plan Chain" "1"; then
    ((passed_phases++))
else
    ((failed_phases++))
fi
((total_tests++))

echo ""

# ================================================================
# PHASE 2 - Requirements Analysis Chain
# ================================================================
if run_test "tests/test_chains_requirements_analysis.py" "Requirements Analysis Chain" "2"; then
    ((passed_phases++))
else
    ((failed_phases++))
fi
((total_tests++))

echo ""

# ================================================================
# PHASE 3 - Debug Error Classification Chain
# ================================================================
if run_test "tests/test_chains_debug_classification.py" "Debug Error Classification Chain" "3"; then
    ((passed_phases++))
else
    ((failed_phases++))
fi
((total_tests++))

echo ""

# ================================================================
# PHASE 4 - LLM Factory with Fallback
# ================================================================
if run_test "tests/test_llm_fallback.py" "LLM Factory with Fallback" "4"; then
    ((passed_phases++))
else
    ((failed_phases++))
fi
((total_tests++))

echo ""

# ================================================================
# RÉSUMÉ
# ================================================================
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    RÉSUMÉ DES TESTS                        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ $failed_phases -eq 0 ]; then
    echo -e "${GREEN}🎉 SUCCÈS COMPLET${NC}"
    echo -e "${GREEN}✅ ${passed_phases}/${total_tests} phases testées avec succès${NC}"
    echo ""
    echo -e "${GREEN}Toutes les phases LangChain sont opérationnelles !${NC}"
    exit_code=0
else
    echo -e "${RED}⚠️  ÉCHECS DÉTECTÉS${NC}"
    echo -e "${GREEN}✅ ${passed_phases} phases réussies${NC}"
    echo -e "${RED}❌ ${failed_phases} phases échouées${NC}"
    echo ""
    echo -e "${YELLOW}Consultez les logs ci-dessus pour plus de détails.${NC}"
    exit_code=1
fi

echo ""

# ================================================================
# VÉRIFICATIONS SUPPLÉMENTAIRES
# ================================================================
echo -e "${YELLOW}🔍 Vérifications supplémentaires...${NC}"

# Vérifier que les fichiers principaux existent
files_to_check=(
    "ai/chains/implementation_plan_chain.py"
    "ai/chains/requirements_analysis_chain.py"
    "ai/chains/debug_error_classification_chain.py"
    "ai/llm/llm_factory.py"
    "nodes/analyze_node.py"
    "nodes/debug_node.py"
)

all_files_exist=true
for file in "${files_to_check[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅${NC} $file"
    else
        echo -e "${RED}❌${NC} $file (manquant)"
        all_files_exist=false
    fi
done

echo ""

# Vérifier les flags d'activation
echo -e "${YELLOW}🎛️  Vérification des flags d'activation...${NC}"

if grep -q "USE_LANGCHAIN_ANALYSIS = True" nodes/analyze_node.py; then
    echo -e "${GREEN}✅${NC} Phase 2 (Requirements Analysis) activée"
else
    echo -e "${YELLOW}⚠️${NC}  Phase 2 (Requirements Analysis) désactivée"
fi

if grep -q "USE_LANGCHAIN_ERROR_CLASSIFICATION = True" nodes/debug_node.py; then
    echo -e "${GREEN}✅${NC} Phase 3 (Error Classification) activée"
else
    echo -e "${YELLOW}⚠️${NC}  Phase 3 (Error Classification) désactivée"
fi

echo ""

# ================================================================
# RECOMMENDATIONS
# ================================================================
if [ $exit_code -eq 0 ]; then
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    PROCHAINES ÉTAPES                       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "1. Configurer les variables d'environnement (.env)"
    echo "   - ANTHROPIC_API_KEY"
    echo "   - OPENAI_API_KEY (pour fallback)"
    echo "   - LANGSMITH_API_KEY (pour tracing)"
    echo ""
    echo "2. Tester sur un workflow réel"
    echo ""
    echo "3. Monitorer les métriques LangSmith"
    echo "   → https://smith.langchain.com/"
    echo ""
    echo "4. (Optionnel) Implémenter Phase 5: Optimisations avancées"
    echo ""
fi

# Retourner le code de sortie approprié
exit $exit_code

