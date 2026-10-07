// Машина 1 — Jenkins: проверка кода и сборка образа.
// Машина 2 — DEPLOY_HOST: запуск всех контейнеров через docker compose.
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
    }

    parameters {
        string(name: 'DEPLOY_HOST', defaultValue: '', description: 'IP или DNS-имя машины деплоя')
        string(name: 'DEPLOY_USER', defaultValue: 'deploy', description: 'SSH-пользователь с доступом к Docker')
        string(name: 'DEPLOY_PATH', defaultValue: '/opt/game-radar', description: 'Каталог проекта на машине деплоя')
        choice(name: 'PRICE_SOURCE', choices: ['mock', 'cheapshark'], description: 'Источник цен')
    }

    environment {
        SSH_OPTS = '-o BatchMode=yes -o StrictHostKeyChecking=accept-new'
    }

    stages {
        stage('Lint & tests') {
            steps {
                sh '''
                    set -eu
                    python3 -m venv .venv-ci
                    .venv-ci/bin/pip install --quiet -r requirements-dev.txt
                    .venv-ci/bin/ruff check .
                    .venv-ci/bin/ruff format --check .
                    mkdir -p reports
                    .venv-ci/bin/python -m pytest --junitxml=reports/tests.xml
                '''
            }
        }

        stage('Build') {
            steps {
                sh 'docker build --pull -t game-radar:latest -t "game-radar:$GIT_COMMIT" .'
            }
        }

        stage('Deploy') {
            steps {
                withCredentials([
                    sshUserPrivateKey(credentialsId: 'deploy-ssh', keyFileVariable: 'SSH_KEY'),
                    string(credentialsId: 'postgres-password', variable: 'POSTGRES_PASSWORD'),
                    string(credentialsId: 'api-key', variable: 'API_KEY'),
                    string(credentialsId: 'grafana-password', variable: 'GRAFANA_PASSWORD')
                ]) {
                    sh '''
                        set +x
                        set -eu
                        test -n "$DEPLOY_HOST" || { echo "Укажите параметр DEPLOY_HOST"; exit 1; }
                        TARGET="$DEPLOY_USER@$DEPLOY_HOST"

                        ssh -i "$SSH_KEY" $SSH_OPTS "$TARGET" "mkdir -p '$DEPLOY_PATH'"
                        scp -i "$SSH_KEY" $SSH_OPTS -r docker-compose.yml monitoring "$TARGET:$DEPLOY_PATH/"

                        # Секреты из Jenkins Credentials попадают только в .env на машине деплоя.
                        printf 'POSTGRES_USER=game_radar\\nPOSTGRES_DB=game_radar\\nPOSTGRES_PASSWORD=%s\\nAPI_KEY=%s\\nGRAFANA_PASSWORD=%s\\nPRICE_SOURCE=%s\\n' \
                            "$POSTGRES_PASSWORD" "$API_KEY" "$GRAFANA_PASSWORD" "$PRICE_SOURCE" \
                            | ssh -i "$SSH_KEY" $SSH_OPTS "$TARGET" "umask 077 && cat > '$DEPLOY_PATH/.env'"

                        # Образ собран на машине 1 и переносится без реестра.
                        docker save game-radar:latest | gzip \
                            | ssh -i "$SSH_KEY" $SSH_OPTS "$TARGET" "gunzip | docker load"

                        ssh -i "$SSH_KEY" $SSH_OPTS "$TARGET" \
                            "cd '$DEPLOY_PATH' && docker compose up -d --no-build --remove-orphans --wait"
                    '''
                }
            }
        }

        stage('Smoke') {
            steps {
                sh '''
                    set -eu
                    curl -fsS --retry 10 --retry-delay 3 --retry-all-errors \
                        "http://$DEPLOY_HOST:8000/health" | tee health.json
                    grep -q '"status":"ok"' health.json
                '''
            }
        }
    }

    post {
        always {
            junit testResults: 'reports/tests.xml', allowEmptyResults: true
            sh 'rm -rf .venv-ci health.json'
        }
    }
}
