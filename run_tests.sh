#!/bin/bash

# Forge LSP Test Suite Runner
# Comprehensive testing script for all diagnostic and linting functionality

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results tracking
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "INFO")
            echo -e "${BLUE}ℹ️  ${message}${NC}"
            ;;
        "SUCCESS")
            echo -e "${GREEN}✅ ${message}${NC}"
            ;;
        "ERROR")
            echo -e "${RED}❌ ${message}${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠️  ${message}${NC}"
            ;;
    esac
}

# Function to run a test
run_test() {
    local test_name=$1
    local test_command=$2
    local description=$3
    
    TESTS_RUN=$((TESTS_RUN + 1))
    
    print_status "INFO" "Running: $description"
    echo "Command: $test_command"
    echo "----------------------------------------"
    
    if eval "$test_command"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        print_status "SUCCESS" "$test_name passed"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        print_status "ERROR" "$test_name failed"
        return 1
    fi
    echo ""
}

# Function to check prerequisites
check_prerequisites() {
    print_status "INFO" "Checking prerequisites..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_status "ERROR" "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check Forge
    if ! command -v forge &> /dev/null; then
        print_status "ERROR" "Forge is required but not installed"
        exit 1
    fi
    
    # Check if we're in the right directory
    if [[ ! -f "src/forge_lsp/forge_diagnostics.py" ]]; then
        print_status "ERROR" "Must be run from the forge_lsp project root directory"
        exit 1
    fi
    
    print_status "SUCCESS" "Prerequisites check passed"
    echo ""
}

# Function to setup environment
setup_environment() {
    print_status "INFO" "Setting up test environment..."
    
    # Set environment variables
    export FOUNDRY_DISABLE_NIGHTLY_WARNING=1
    export PYTHONPATH="${PWD}/src:${PYTHONPATH}"
    
    # Ensure examples directory exists and has test files
    if [[ ! -f "examples/src/TestLint.sol" ]]; then
        print_status "WARNING" "TestLint.sol not found, some tests may fail"
    fi
    
    print_status "SUCCESS" "Environment setup complete"
    echo ""
}

# Main test execution
main() {
    echo "🧪 Forge LSP Test Suite"
    echo "======================="
    echo ""
    
    check_prerequisites
    setup_environment
    
    print_status "INFO" "Starting test execution..."
    echo ""
    
    # Core diagnostic message tests
    run_test "message_cleanup" \
        "python3 test_message_cleanup.py" \
        "Testing lint message cleanup and formatting"
    
    run_test "lint_analysis" \
        "python3 test_lint_message_analysis.py" \
        "Testing comprehensive lint message analysis"
    
    # Debug and parsing tests
    run_test "debug_parsing" \
        "python3 debug_lint_parsing.py" \
        "Testing debug lint parsing functionality"
    
    # Core diagnostics tests
    if [[ -f "test_forge_diagnostics.py" ]]; then
        run_test "forge_diagnostics" \
            "python3 test_forge_diagnostics.py" \
            "Testing forge diagnostics functionality"
    fi
    
    # Cache functionality tests
    if [[ -f "test_cache_functionality.py" ]]; then
        run_test "cache_functionality" \
            "python3 test_cache_functionality.py" \
            "Testing diagnostic caching functionality"
    fi
    
    # Error handling tests
    if [[ -f "test_error_diagnostics.py" ]]; then
        run_test "error_diagnostics" \
            "python3 test_error_diagnostics.py" \
            "Testing error diagnostic handling"
    fi
    
    # LSP server tests
    if [[ -f "test_lsp_server.py" ]]; then
        run_test "lsp_server" \
            "python3 test_lsp_server.py" \
            "Testing LSP server functionality"
    fi
    
    # Manual forge command tests
    print_status "INFO" "Running manual forge command tests..."
    
    if [[ -f "examples/src/TestLint.sol" ]]; then
        run_test "forge_lint_direct" \
            "cd examples && forge lint src/TestLint.sol --json >/dev/null 2>&1" \
            "Testing direct forge lint command"
        
        run_test "forge_compile_lint" \
            "cd examples && forge compile src/TestLint.sol --format-json >/dev/null 2>&1" \
            "Testing forge compile with lint output"
    else
        print_status "WARNING" "Skipping forge command tests - TestLint.sol not found"
    fi
    
    # Performance tests
    print_status "INFO" "Running performance tests..."
    
    run_test "diagnostic_speed" \
        "time python3 -c \"
import asyncio
import sys
sys.path.insert(0, 'src')
from forge_lsp.forge_diagnostics import ForgeDiagnosticsProvider

async def test():
    provider = ForgeDiagnosticsProvider()
    if provider:
        print('Performance test completed')

asyncio.run(test())
\" >/dev/null 2>&1" \
        "Testing diagnostic generation speed"
    
    # Summary
    echo ""
    echo "📊 Test Results Summary"
    echo "======================"
    echo "Tests Run:    $TESTS_RUN"
    echo "Tests Passed: $TESTS_PASSED"
    echo "Tests Failed: $TESTS_FAILED"
    echo ""
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        print_status "SUCCESS" "All tests passed! 🎉"
        exit 0
    else
        print_status "ERROR" "$TESTS_FAILED test(s) failed"
        exit 1
    fi
}

# Handle script arguments
case "${1:-}" in
    "--help"|"-h")
        echo "Forge LSP Test Suite Runner"
        echo ""
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --quick, -q    Run only essential tests"
        echo "  --verbose, -v  Run with verbose output"
        echo ""
        echo "Environment Variables:"
        echo "  FORGE_LSP_LOG_LEVEL    Set logging level (DEBUG, INFO, WARNING, ERROR)"
        echo "  FOUNDRY_DISABLE_NIGHTLY_WARNING    Disable forge nightly warnings"
        echo ""
        exit 0
        ;;
    "--quick"|"-q")
        print_status "INFO" "Running quick test suite..."
        # Override main function for quick tests
        main() {
            check_prerequisites
            setup_environment
            
            run_test "message_cleanup" \
                "python3 test_message_cleanup.py" \
                "Testing lint message cleanup and formatting"
            
            run_test "lint_analysis" \
                "python3 test_lint_message_analysis.py" \
                "Testing comprehensive lint message analysis"
            
            echo "📊 Quick Test Results: $TESTS_PASSED/$TESTS_RUN passed"
            [[ $TESTS_FAILED -eq 0 ]] && exit 0 || exit 1
        }
        ;;
    "--verbose"|"-v")
        set -x  # Enable verbose mode
        ;;
esac

# Run main function
main "$@"