# LogPets PRO - Deployment & Configuration Complete
# Docker + CI/CD + Environment Setup

## docker-compose.yml (Production Ready)
```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: logpets_postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-logpets_pro}
      POSTGRES_USER: ${POSTGRES_USER:-logpets_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-logpets_password}
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data/pgdata
      - ./backup:/backup
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-logpets_user}"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - logpets_network

  # Redis for Caching (Optional)
  redis:
    image: redis:7-alpine
    container_name: logpets_redis
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - logpets_network

  # Backend FastAPI
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: logpets_backend
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER:-logpets_user}:${POSTGRES_PASSWORD:-logpets_password}@postgres:5432/${POSTGRES_DB:-logpets_pro}
      - SECRET_KEY=${SECRET_KEY}
      - DEBUG=${DEBUG:-false}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS:-localhost,127.0.0.1}
      - SMTP_SERVER=${SMTP_SERVER}
      - SMTP_PORT=${SMTP_PORT:-587}
      - SMTP_USERNAME=${SMTP_USERNAME}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
      - REDIS_URL=redis://redis:6379/0
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    volumes:
      - ./backend/uploads:/app/uploads
      - ./backend/static:/app/static
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - logpets_network

  # Frontend Next.js
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-http://localhost:8000}
    container_name: logpets_frontend
    environment:
      - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-http://localhost:8000}
    ports:
      - "${FRONTEND_PORT:-3000}:3000"
    depends_on:
      - backend
    restart: unless-stopped
    networks:
      - logpets_network

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: logpets_nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
      - ./frontend/dist:/var/www/html
      - ./backend/static:/var/www/static
    depends_on:
      - frontend
      - backend
    restart: unless-stopped
    networks:
      - logpets_network

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local

networks:
  logpets_network:
    driver: bridge
```

## backend/Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for uploads and static files
RUN mkdir -p uploads static/pdfs static/images logs

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

## backend/requirements.txt
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1
bcrypt==4.1.1
pyjwt==2.8.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-dateutil==2.8.2
email-validator==2.1.0
pydantic[email]==2.5.0
reportlab==4.0.7
pillow==10.1.0
redis==5.0.1
celery==5.3.4
python-decouple==3.8
httpx==0.25.2
aiofiles==23.2.1
```

## frontend/Dockerfile
```dockerfile
FROM node:18-alpine AS base

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --only=production

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Set build-time environment variables
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Set the correct permission for prerender cache
RUN mkdir .next
RUN chown nextjs:nodejs .next

# Automatically leverage output traces to reduce image size
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]
```

## frontend/next.config.js (Production)
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  output: 'standalone',
  
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/:path*`,
      },
    ]
  },
  
  // Security headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'origin-when-cross-origin',
          },
        ],
      },
    ]
  },
  
  // PWA Configuration
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
      };
    }
    return config;
  },
  
  // Image optimization
  images: {
    domains: ['localhost'],
    formats: ['image/webp', 'image/avif'],
  },
  
  // Compression
  compress: true,
  
  // Experimental features
  experimental: {
    appDir: true,
    serverComponentsExternalPackages: ['sharp'],
  },
}

module.exports = nextConfig
```

## nginx/nginx.conf
```nginx
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    
    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    
    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log;
    
    # Basic Settings
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 50M;
    
    # Gzip Settings
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;
    
    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=1r/s;
    
    # Upstream servers
    upstream backend {
        server backend:8000;
    }
    
    upstream frontend {
        server frontend:3000;
    }
    
    # HTTP Redirect to HTTPS
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }
    
    # Main server block
    server {
        listen 443 ssl http2;
        server_name localhost;
        
        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;
        
        # Security Headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header Referrer-Policy "origin-when-cross-origin";
        
        # API routes
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }
        
        # Login endpoint with stricter rate limiting
        location /api/auth/login {
            limit_req zone=login burst=5 nodelay;
            
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # Static files (backend)
        location /static/ {
            alias /var/www/static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
        
        # Frontend application
        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # WebSocket support
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_cache_bypass $http_upgrade;
        }
    }
}
```

## .env.example
```env
# Database Configuration
POSTGRES_DB=logpets_pro
POSTGRES_USER=logpets_user
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_PORT=5432

# Backend Configuration
SECRET_KEY=your_super_secret_key_here_change_in_production
DEBUG=false
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

# Frontend Configuration
NEXT_PUBLIC_API_URL=https://yourdomain.com
FRONTEND_PORT=3000
BACKEND_PORT=8000

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# Redis Configuration
REDIS_PORT=6379

# SSL Configuration (for production)
SSL_CERT_PATH=./nginx/ssl/cert.pem
SSL_KEY_PATH=./nginx/ssl/key.pem

# Google Maps API Key (for mobile app)
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here

# JWT Configuration
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# File Upload Configuration
MAX_FILE_SIZE=50MB
ALLOWED_FILE_TYPES=image/jpeg,image/png,application/pdf

# Monitoring (optional)
SENTRY_DSN=your_sentry_dsn_here
```

## .github/workflows/ci-cd.yml
```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install Python dependencies
      run: |
        cd backend
        pip install -r requirements.txt
        pip install pytest pytest-asyncio httpx
    
    - name: Run Python tests
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
        SECRET_KEY: test_secret_key
      run: |
        cd backend
        pytest tests/ -v
    
    - name: Set up Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '18'
        cache: 'npm'
        cache-dependency-path: frontend/package-lock.json
    
    - name: Install Node.js dependencies
      run: |
        cd frontend
        npm ci
    
    - name: Run frontend tests
      run: |
        cd frontend
        npm run test
    
    - name: Build frontend
      run: |
        cd frontend
        npm run build

  build-and-push:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    permissions:
      contents: read
      packages: write
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Log in to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=sha
    
    - name: Build and push Docker images
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Deploy to production
      uses: appleboy/ssh-action@v1.0.0
      with:
        host: ${{ secrets.PRODUCTION_HOST }}
        username: ${{ secrets.PRODUCTION_USER }}
        key: ${{ secrets.PRODUCTION_SSH_KEY }}
        script: |
          cd /opt/logpets-pro
          git pull origin main
          docker-compose down
          docker-compose pull
          docker-compose up -d
          docker system prune -f
```

## scripts/deploy.sh
```bash
#!/bin/bash

# LogPets PRO - Deploy Script

set -e

echo "🚀 Iniciando deploy do LogPets PRO..."

# Verificar se .env existe
if [ ! -f .env ]; then
    echo "❌ Arquivo .env não encontrado!"
    echo "📋 Copie .env.example para .env e configure as variáveis"
    exit 1
fi

# Carregar variáveis de ambiente
source .env

# Verificar se Docker está rodando
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker não está rodando!"
    exit 1
fi

# Verificar se Docker Compose está instalado
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose não está instalado!"
    exit 1
fi

echo "✅ Pré-requisitos verificados"

# Parar containers existentes
echo "🛑 Parando containers existentes..."
docker-compose down

# Construir imagens
echo "🔨 Construindo imagens..."
docker-compose build --no-cache

# Iniciar serviços
echo "🚀 Iniciando serviços..."
docker-compose up -d

# Aguardar serviços iniciarem
echo "⏳ Aguardando serviços iniciarem..."
sleep 30

# Verificar saúde dos serviços
echo "🏥 Verificando saúde dos serviços..."

# Verificar PostgreSQL
if docker-compose exec -T postgres pg_isready -U $POSTGRES_USER; then
    echo "✅ PostgreSQL está funcionando"
else
    echo "❌ PostgreSQL não está respondendo"
    exit 1
fi

# Verificar Backend
if curl -f http://localhost:${BACKEND_PORT:-8000}/health > /dev/null 2>&1; then
    echo "✅ Backend está funcionando"
else
    echo "❌ Backend não está respondendo"
    exit 1
fi

# Verificar Frontend
if curl -f http://localhost:${FRONTEND_PORT:-3000} > /dev/null 2>&1; then
    echo "✅ Frontend está funcionando"
else
    echo "❌ Frontend não está respondendo"
    exit 1
fi

# Executar migrações do banco
echo "🗃️ Executando migrações do banco..."
docker-compose exec backend alembic upgrade head

echo "🎉 Deploy concluído com sucesso!"
echo ""
echo "📱 Aplicação disponível em:"
echo "   Frontend: http://localhost:${FRONTEND_PORT:-3000}"
echo "   Backend:  http://localhost:${BACKEND_PORT:-8000}"
echo "   API Docs: http://localhost:${BACKEND_PORT:-8000}/docs"
echo ""
echo "📊 Para monitorar os logs:"
echo "   docker-compose logs -f"
echo ""
echo "🔧 Para parar a aplicação:"
echo "   docker-compose down"
```

## scripts/backup.sh
```bash
#!/bin/bash

# LogPets PRO - Backup Script

set -e

# Carregar variáveis de ambiente
if [ -f .env ]; then
    source .env
fi

BACKUP_DIR="./backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
POSTGRES_CONTAINER="logpets_postgres"

echo "🗄️ Iniciando backup do LogPets PRO..."

# Criar diretório de backup se não existir
mkdir -p $BACKUP_DIR

# Backup do banco de dados
echo "📊 Fazendo backup do banco de dados..."
docker exec $POSTGRES_CONTAINER pg_dump -U $POSTGRES_USER $POSTGRES_DB > $BACKUP_DIR/database_$TIMESTAMP.sql

# Backup dos uploads
echo "📁 Fazendo backup dos arquivos..."
tar -czf $BACKUP_DIR/uploads_$TIMESTAMP.tar.gz backend/uploads/

# Backup dos arquivos estáticos
tar -czf $BACKUP_DIR/static_$TIMESTAMP.tar.gz backend/static/

# Limpar backups antigos (manter apenas os últimos 7 dias)
echo "🧹 Limpando backups antigos..."
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "✅ Backup concluído: $BACKUP_DIR/"
echo "   - database_$TIMESTAMP.sql"
echo "   - uploads_$TIMESTAMP.tar.gz"
echo "   - static_$TIMESTAMP.tar.gz"
```

## scripts/setup.sh
```bash
#!/bin/bash

# LogPets PRO - Setup Script

set -e

echo "🔧 Configurando ambiente LogPets PRO..."

# Verificar sistema operacional
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    DISTRO=$(lsb_release -si)
    echo "📍 Sistema: Linux ($DISTRO)"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "📍 Sistema: macOS"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    echo "📍 Sistema: Windows"
else
    echo "❌ Sistema operacional não suportado"
    exit 1
fi

# Instalar Docker (Linux)
install_docker_linux() {
    if ! command -v docker &> /dev/null; then
        echo "🐳 Instalando Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        rm get-docker.sh
        echo "✅ Docker instalado"
    else
        echo "✅ Docker já está instalado"
    fi
}

# Instalar Docker Compose
install_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        echo "🔧 Instalando Docker Compose..."
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        echo "✅ Docker Compose instalado"
    else
        echo "✅ Docker Compose já está instalado"
    fi
}

# Instalar dependências baseado no sistema
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    install_docker_linux
    install_docker_compose
elif [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v docker &> /dev/null; then
        echo "🐳 Instale Docker Desktop para macOS: https://docs.docker.com/docker-for-mac/install/"
        exit 1
    fi
fi

# Verificar Node.js (para desenvolvimento local)
if ! command -v node &> /dev/null; then
    echo "⚠️ Node.js não encontrado. Instale: https://nodejs.org/"
    echo "   Ou use nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
fi

# Verificar Python (para desenvolvimento local)
if ! command -v python3 &> /dev/null; then
    echo "⚠️ Python 3 não encontrado. Instale: https://www.python.org/downloads/"
fi

# Criar arquivo .env se não existir
if [ ! -f .env ]; then
    echo "📝 Criando arquivo .env..."
    cp .env.example .env
    echo "⚠️ Configure as variáveis em .env antes de continuar"
fi

# Criar diretórios necessários
echo "📁 Criando diretórios..."
mkdir -p backend/uploads backend/static/pdfs backend/static/images
mkdir -p nginx/ssl
mkdir -p backup
mkdir -p logs

# Gerar certificados SSL auto-assinados para desenvolvimento
if [ ! -f nginx/ssl/cert.pem ]; then
    echo "🔐 Gerando certificados SSL para desenvolvimento..."
    openssl req -x509 -newkey rsa:4096 -keyout nginx/ssl/key.pem -out nginx/ssl/cert.pem -days 365 -nodes -subj "/C=BR/ST=SP/L=São Paulo/O=LogPets/CN=localhost"
    echo "✅ Certificados SSL gerados"
fi

# Configurar permissões
echo "🔒 Configurando permissões..."
chmod +x scripts/*.sh
chmod 600 nginx/ssl/*.pem

echo "🎉 Setup concluído!"
echo ""
echo "📋 Próximos passos:"
echo "1. Configure as variáveis no arquivo .env"
echo "2. Execute: ./scripts/deploy.sh"
echo "3. Acesse: http://localhost:3000"
echo ""
echo "📚 Documentação:"
echo "   - API: http://localhost:8000/docs"
echo "   - Logs: docker-compose logs -f"
echo "   - Backup: ./scripts/backup.sh"
```

## Makefile
```makefile
# LogPets PRO - Makefile

.PHONY: help install build up down logs clean test backup

help: ## Mostrar ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install: ## Instalar dependências
	@echo "🔧 Instalando dependências..."
	cd backend && pip install -r requirements.txt
	cd frontend && npm install
	cd mobile && flutter pub get

build: ## Construir imagens Docker
	@echo "🔨 Construindo imagens..."
	docker-compose build

up: ## Iniciar aplicação
	@echo "🚀 Iniciando aplicação..."
	docker-compose up -d

down: ## Parar aplicação
	@echo "🛑 Parando aplicação..."
	docker-compose down

logs: ## Mostrar logs
	docker-compose logs -f

clean: ## Limpar containers e volumes
	@echo "🧹 Limpando containers e volumes..."
	docker-compose down -v
	docker system prune -f

test: ## Executar testes
	@echo "🧪 Executando testes..."
	cd backend && pytest tests/ -v
	cd frontend && npm test

backup: ## Fazer backup
	@echo "🗄️ Fazendo backup..."
	./scripts/backup.sh

deploy: ## Deploy completo
	@echo "🚀 Fazendo deploy..."
	./scripts/deploy.sh

dev-backend: ## Executar backend em modo desenvolvimento
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Executar frontend em modo desenvolvimento
	cd frontend && npm run dev

dev-mobile: ## Executar app mobile
	cd mobile && flutter run

format: ## Formatar código
	cd backend && black . && isort .
	cd frontend && npm run format
	cd mobile && dart format .

lint: ## Verificar código
	cd backend && flake8 .
	cd frontend && npm run lint
	cd mobile && dart analyze .
```