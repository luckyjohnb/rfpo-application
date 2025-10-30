#!/bin/bash
# Local Development Environment Manager for RFPO Application
# Uses Azure PostgreSQL database with local containers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="docker-compose.dev.yml"
ENV_FILE=".env.local"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}🏗️  RFPO Local Development Environment${NC}"
    echo -e "${BLUE}Uses Azure PostgreSQL + Local Containers${NC}"
    echo "================================================"
}

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_prerequisites() {
    echo "🔍 Checking prerequisites..."

    # Check if .env.local exists
    if [[ ! -f "$ENV_FILE" ]]; then
        print_error ".env.local file not found!"
        echo "Please create .env.local with Azure database configuration."
        exit 1
    fi

    # Check if docker-compose.dev.yml exists
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        print_error "docker-compose.dev.yml file not found!"
        exit 1
    fi

    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker Desktop."
        exit 1
    fi

    print_status "Prerequisites check passed"
}

test_azure_connection() {
    echo "🔗 Testing Azure PostgreSQL connection..."

    if python3 test_azure_db_connection.py; then
        print_status "Azure database connection successful"
    else
        print_error "Azure database connection failed"
        echo "Please check:"
        echo "  - Your IP address is whitelisted in Azure PostgreSQL firewall"
        echo "  - Database credentials in .env.local are correct"
        echo "  - psycopg2-binary is installed: pip3 install psycopg2-binary"
        exit 1
    fi
}

start_services() {
    echo "🚀 Starting local development services..."

    docker-compose -f "$COMPOSE_FILE" up --build -d

    echo "⏳ Waiting for services to be healthy..."
    sleep 10

    # Check service health
    echo "🏥 Checking service health..."

    API_HEALTH=$(curl -s http://localhost:5002/api/health | jq -r '.status' 2>/dev/null || echo "error")
    ADMIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5111/login 2>/dev/null || echo "error")
    USER_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/ 2>/dev/null || echo "error")

    echo "Service Status:"
    if [[ "$API_HEALTH" == "healthy" ]]; then
        print_status "API Layer (5002): $API_HEALTH"
    else
        print_error "API Layer (5002): $API_HEALTH"
    fi

    if [[ "$ADMIN_STATUS" == "200" ]]; then
        print_status "Admin Panel (5111): Ready"
    else
        print_error "Admin Panel (5111): HTTP $ADMIN_STATUS"
    fi

    if [[ "$USER_STATUS" == "200" ]]; then
        print_status "User App (5001): Ready"
    else
        print_error "User App (5001): HTTP $USER_STATUS"
    fi
}

show_urls() {
    echo ""
    echo "🌐 Local Development URLs:"
    echo "  Admin Panel:  http://localhost:5111/login"
    echo "  User App:     http://localhost:5001"
    echo "  API Health:   http://localhost:5002/api/health"
    echo ""
    echo "📊 Admin Credentials:"
    echo "  Email:    admin@rfpo.com"
    echo "  Password: admin123"
    echo ""
    echo "💾 Database: Azure PostgreSQL (Production Data)"
    echo "📁 Files: Local ./uploads directory"
}

stop_services() {
    echo "🛑 Stopping local development services..."
    docker-compose -f "$COMPOSE_FILE" down
    print_status "Services stopped"
}

show_logs() {
    echo "📄 Showing service logs..."
    docker-compose -f "$COMPOSE_FILE" logs -f
}

show_status() {
    echo "📊 Service Status:"
    docker-compose -f "$COMPOSE_FILE" ps
}

show_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start     Start local development environment"
    echo "  stop      Stop local development environment"
    echo "  restart   Restart local development environment"
    echo "  status    Show service status"
    echo "  logs      Show service logs (follow mode)"
    echo "  test      Test Azure database connection"
    echo "  urls      Show development URLs"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start      # Start development environment"
    echo "  $0 logs       # View live logs"
    echo "  $0 restart    # Restart all services"
}

case "${1:-}" in
    "start")
        print_header
        check_prerequisites
        test_azure_connection
        start_services
        show_urls
        ;;
    "stop")
        print_header
        stop_services
        ;;
    "restart")
        print_header
        stop_services
        check_prerequisites
        test_azure_connection
        start_services
        show_urls
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs
        ;;
    "test")
        test_azure_connection
        ;;
    "urls")
        show_urls
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        print_header
        echo "🎯 Quick Start:"
        echo "  ./local-dev.sh start    # Start development environment"
        echo "  ./local-dev.sh logs     # View logs"
        echo "  ./local-dev.sh help     # Full help"
        echo ""
        show_help
        ;;
esac
