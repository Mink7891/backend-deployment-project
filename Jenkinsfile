// Машина 1 — Jenkins: проверка кода, сборка, сканирование, публикация образа, JMeter.
// Машина 2 — DEPLOY_HOST: скачивает образ из реестра и запускает docker compose.
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 45, unit: 'MINUTES')
    }

    parameters {
        string(name: 'DEPLOY_HOST', defaultValue: '', description: 'IP или DNS-имя машины деплоя')
        string(name: 'DEPLOY_USER', defaultValue: 'deploy', description: 'SSH-пользователь с доступом к Docker')
        string(name: 'DEPLOY_PATH', defaultValue: '/opt/game-radar', description: 'Каталог проекта на машине деплоя')
        string(name: 'IMAGE_NAME', defaultValue: 'ghcr.io/mink7891/game-radar', description: 'Образ в реестре (без тега)')
        string(name: 'DEPLOY_TAG', defaultValue: '', description: 'Откат: SHA коммита уже опубликованного образа. Пусто — собрать текущий коммит')
        choice(name: 'PRICE_SOURCE', choices: ['mock', 'cheapshark'], description: 'Источник цен; нагрузочный тест выполняется только с mock')
        string(name: 'LOAD_THREADS', defaultValue: '5', description: 'Пользователей на ступень нагрузки (3 ступени)')
        string(name: 'LOAD_HOLD', defaultValue: '60', description: 'Длительность ступени нагрузки, секунд')
        string(name: 'P95_MS', defaultValue: '1000', description: 'Порог 95-го перцентиля времени ответа, мс')
    }

    environment {
        SSH_OPTS = '-o BatchMode=yes -o StrictHostKeyChecking=accept-new'
    }

    stages {
        stage('Prepare') {
            steps {
                script {
                    env.IMAGE_TAG = params.DEPLOY_TAG ?: env.GIT_COMMIT
                    env.IS_ROLLBACK = params.DEPLOY_TAG ? 'true' : 'false'
                }
                sh 'rm -rf reports && mkdir -p reports'
                echo "Образ для деплоя: ${params.IMAGE_NAME}:${env.IMAGE_TAG}"
            }
        }

        stage('Lint & tests') {
            when { expression { env.IS_ROLLBACK == 'false' } }
            steps {
                sh '''
                    set -eu
                    python3 -m venv .venv-ci
                    .venv-ci/bin/pip install --quiet -r requirements-dev.txt
                    .venv-ci/bin/ruff check .
                    .venv-ci/bin/ruff format --check .
                    .venv-ci/bin/python -m pytest --junitxml=reports/tests.xml
                '''
            }
        }

        stage('Build') {
            when { expression { env.IS_ROLLBACK == 'false' } }
            steps {
                sh 'docker build --pull -t "$IMAGE_NAME:$IMAGE_TAG" .'
            }
        }

        stage('Trivy') {
            when { expression { env.IS_ROLLBACK == 'false' } }
            steps {
                sh '''
                    set -eu
                    status=0
                    docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        -v "$WORKSPACE/reports:/reports" \
                        aquasec/trivy:latest image --no-progress \
                        --severity CRITICAL --exit-code 1 \
                        --output /reports/trivy.txt \
                        "$IMAGE_NAME:$IMAGE_TAG" || status=$?
                    cat reports/trivy.txt
                    exit "$status"
                '''
            }
        }

        stage('Push') {
            when { expression { env.IS_ROLLBACK == 'false' } }
            steps {
                withCredentials([usernamePassword(credentialsId: 'registry-credentials', usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_TOKEN')]) {
                    sh '''
                        set +x
                        set -eu
                        printf '%s' "$REGISTRY_TOKEN" | docker login "${IMAGE_NAME%%/*}" -u "$REGISTRY_USER" --password-stdin
                        docker push "$IMAGE_NAME:$IMAGE_TAG"
                        docker logout "${IMAGE_NAME%%/*}"
                    '''
                }
            }
        }

        stage('Deploy') {
            steps {
                withCredentials([
                    sshUserPrivateKey(credentialsId: 'deploy-ssh', keyFileVariable: 'SSH_KEY'),
                    usernamePassword(credentialsId: 'registry-credentials', usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_TOKEN'),
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
                        scp -i "$SSH_KEY" $SSH_OPTS -r docker-compose.yml monitoring scripts "$TARGET:$DEPLOY_PATH/"

                        # Секреты из Jenkins Credentials попадают только в .env на машине деплоя.
                        {
                            echo "IMAGE_NAME=$IMAGE_NAME"
                            echo "IMAGE_TAG=$IMAGE_TAG"
                            echo "POSTGRES_USER=game_radar"
                            echo "POSTGRES_DB=game_radar"
                            echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD"
                            echo "API_KEY=$API_KEY"
                            echo "GRAFANA_PASSWORD=$GRAFANA_PASSWORD"
                            echo "PRICE_SOURCE=$PRICE_SOURCE"
                        } | ssh -i "$SSH_KEY" $SSH_OPTS "$TARGET" "umask 077 && cat > '$DEPLOY_PATH/.env'"

                        # Машина деплоя не собирает образ, а скачивает его из реестра.
                        printf '%s' "$REGISTRY_TOKEN" | ssh -i "$SSH_KEY" $SSH_OPTS "$TARGET" \
                            "docker login '${IMAGE_NAME%%/*}' -u '$REGISTRY_USER' --password-stdin"
                        ssh -i "$SSH_KEY" $SSH_OPTS "$TARGET" \
                            "cd '$DEPLOY_PATH' && docker compose pull app worker && docker compose up -d --no-build --remove-orphans --wait"
                    '''
                }
            }
        }

        stage('Smoke') {
            steps {
                sh '''
                    set -eu
                    curl -fsS --retry 10 --retry-delay 3 --retry-all-errors \
                        "http://$DEPLOY_HOST:8000/health" | tee reports/health.json
                    grep -q '"status":"ok"' reports/health.json
                '''
            }
        }

        stage('Load test') {
            // Сторонний API не нагружаем: тест только против заглушки PRICE_SOURCE=mock.
            when { expression { env.IS_ROLLBACK == 'false' && params.PRICE_SOURCE == 'mock' } }
            steps {
                withCredentials([string(credentialsId: 'api-key', variable: 'API_KEY')]) {
                    sh '''
                        set +x
                        set -eu
                        umask 077
                        printf 'api_key=%s\\n' "$API_KEY" > reports/secret.properties
                        jmeter -n -t load-tests/game-radar.jmx \
                            -q reports/secret.properties \
                            -Jhost="$DEPLOY_HOST" -Jport=8000 \
                            -Jthreads="$LOAD_THREADS" -Jhold="$LOAD_HOLD" -Jramp=10 \
                            -Jjmeter.save.saveservice.output_format=csv \
                            -l reports/load.jtl -j reports/jmeter.log \
                            -e -o reports/jmeter-html
                        rm -f reports/secret.properties
                        python3 load-tests/check_results.py reports/load.jtl \
                            --max-error-rate 0.01 --p95-ms "$P95_MS"
                    '''
                }
            }
        }
    }

    post {
        always {
            junit testResults: 'reports/tests.xml', allowEmptyResults: true
            archiveArtifacts artifacts: 'reports/trivy.txt,reports/load.jtl,reports/jmeter-html/**', allowEmptyArchive: true
            sh 'rm -rf .venv-ci reports/secret.properties'
        }
    }
}
