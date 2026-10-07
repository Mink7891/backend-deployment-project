pipeline {
    // Machine 1: a Linux Jenkins agent with Docker, uv, Python 3.12, Trivy and JMeter.
    agent { label 'linux-ci' }
    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '15'))
    }
    parameters {
        string(name: 'REGISTRY', defaultValue: 'ghcr.io', description: 'Container registry hostname')
        string(name: 'IMAGE_REPOSITORY', defaultValue: 'ghcr.io/your-account/game-radar', description: 'Set your own lowercase image repository')
        string(name: 'DEPLOY_HOST', defaultValue: '', description: 'Machine 2 DNS name or IPv4, reachable from this CI agent')
        string(name: 'DEPLOY_USER', defaultValue: 'deploy', description: 'SSH deployment user with Docker access')
        string(name: 'DEPLOY_PATH', defaultValue: '/opt/game-radar', description: 'Writable application directory on machine 2')
        string(name: 'PROD_PORT', defaultValue: '8000', description: 'Production API port on machine 2')
        string(name: 'LOAD_PORT', defaultValue: '8001', description: 'Separate mock API port on machine 2')
        string(name: 'P95_THRESHOLD_MS', defaultValue: '1000', description: 'Fail if p95 >1000ms; one-second interactive-response target, tune only with a documented reason')
        string(name: 'LOAD_THREADS', defaultValue: '5', description: 'Threads added at each load step')
        string(name: 'LOAD_STEPS', defaultValue: '3', description: 'Default load increases to 5, 10, 15 users')
        string(name: 'LOAD_RAMP_SECONDS', defaultValue: '10', description: 'Ramp inside each step')
        string(name: 'LOAD_HOLD_SECONDS', defaultValue: '40', description: 'Seconds between load steps')
    }
    environment {
        UV_NO_PROGRESS = '1'
        DOCKER_BUILDKIT = '1'
        LOAD_STARTED = 'no'
    }
    stages {
        stage('Configuration') {
            steps {
                checkout scm
                sh 'python3 scripts/check_ci_config.py'
                script {
                    env.IMAGE_TAG = sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
                }
                sh '''
                    set -eu
                    test ! -L reports
                    rm -rf -- reports
                    mkdir reports
                '''
            }
        }
        stage('Lint and tests') {
            steps {
                sh '''
                    set -eu
                    uv sync --locked --group dev --python 3.12
                    uv run --no-sync python scripts/generate_schemas.py --check
                    uv run --no-sync ruff check .
                    uv run --no-sync ruff format --check .
                    uv run --no-sync pytest --junitxml=reports/unit-tests.xml
                '''
            }
        }
        stage('Build Docker image') {
            steps {
                sh '''
                    set -eu
                    docker build --pull --no-cache --target runtime \
                      --label "org.opencontainers.image.revision=$IMAGE_TAG" \
                      --tag "$IMAGE_REPOSITORY:$IMAGE_TAG" .
                '''
            }
        }
        stage('Trivy CRITICAL gate') {
            steps {
                sh '''
                    set -eu
                    trivy image --exit-code 1 --severity CRITICAL \
                      --format json --output reports/trivy.json \
                      "$IMAGE_REPOSITORY:$IMAGE_TAG"
                '''
            }
        }
        stage('Push commit image') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'registry-auth', usernameVariable: 'REGISTRY_USERNAME', passwordVariable: 'REGISTRY_PASSWORD')]) {
                    sh '''
                        set +x
                        set -eu
                        auth_directory=$(mktemp -d)
                        trap 'rm -rf "$auth_directory"' EXIT
                        export DOCKER_CONFIG="$auth_directory"
                        printf '%s' "$REGISTRY_PASSWORD" | docker login "$REGISTRY" \
                          --username "$REGISTRY_USERNAME" --password-stdin >/dev/null
                        docker push "$IMAGE_REPOSITORY:$IMAGE_TAG"
                    '''
                }
            }
        }
        stage('Deploy to machine 2') {
            steps {
                withCredentials([
                    sshUserPrivateKey(credentialsId: 'deploy-ssh', keyFileVariable: 'SSH_KEY'),
                    file(credentialsId: 'deploy-known-hosts', variable: 'KNOWN_HOSTS'),
                    usernamePassword(credentialsId: 'registry-auth', usernameVariable: 'REGISTRY_USERNAME', passwordVariable: 'REGISTRY_PASSWORD'),
                    string(credentialsId: 'radar-api-key', variable: 'API_KEY'),
                    string(credentialsId: 'postgres-password', variable: 'POSTGRES_PASSWORD'),
                    string(credentialsId: 'grafana-password', variable: 'GRAFANA_PASSWORD')
                ]) {
                    sh '''
                        set +x
                        set -eu
                        trap 'rm -f .deploy.env .deploy.load.env deploy-bundle.tgz' EXIT
                        python3 scripts/write_deploy_env.py
                        tar -czf deploy-bundle.tgz docker-compose.deploy.yml docker-compose.load.yml infrastructure scripts
                        ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=yes \
                          -o UserKnownHostsFile="$KNOWN_HOSTS" "$DEPLOY_USER@$DEPLOY_HOST" \
                          "mkdir -p '$DEPLOY_PATH'"
                        scp -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=yes \
                          -o UserKnownHostsFile="$KNOWN_HOSTS" deploy-bundle.tgz \
                          "$DEPLOY_USER@$DEPLOY_HOST:$DEPLOY_PATH/deploy-bundle.tgz"
                        scp -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=yes \
                          -o UserKnownHostsFile="$KNOWN_HOSTS" .deploy.env \
                          "$DEPLOY_USER@$DEPLOY_HOST:$DEPLOY_PATH/.env"
                        scp -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=yes \
                          -o UserKnownHostsFile="$KNOWN_HOSTS" .deploy.load.env \
                          "$DEPLOY_USER@$DEPLOY_HOST:$DEPLOY_PATH/.env.load"
                        ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=yes \
                          -o UserKnownHostsFile="$KNOWN_HOSTS" "$DEPLOY_USER@$DEPLOY_HOST" \
                          "cd '$DEPLOY_PATH' && chmod 600 .env .env.load && tar -xzf deploy-bundle.tgz"
                        printf '%s' "$REGISTRY_PASSWORD" | ssh -i "$SSH_KEY" -o BatchMode=yes \
                          -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$KNOWN_HOSTS" \
                          "$DEPLOY_USER@$DEPLOY_HOST" \
                          "cd '$DEPLOY_PATH' && bash scripts/deploy.sh '$IMAGE_TAG' production '$REGISTRY' '$REGISTRY_USERNAME'"
                    '''
                }
            }
        }
        stage('Production smoke') {
            steps {
                sh 'python3 scripts/smoke.py "http://$DEPLOY_HOST:$PROD_PORT" --expected-source cheapshark'
            }
        }
        stage('Isolated mock load environment') {
            steps {
                script { env.LOAD_STARTED = 'yes' }
                withCredentials([
                    sshUserPrivateKey(credentialsId: 'deploy-ssh', keyFileVariable: 'SSH_KEY'),
                    file(credentialsId: 'deploy-known-hosts', variable: 'KNOWN_HOSTS'),
                    usernamePassword(credentialsId: 'registry-auth', usernameVariable: 'REGISTRY_USERNAME', passwordVariable: 'REGISTRY_PASSWORD')
                ]) {
                    sh '''
                        set +x
                        set -eu
                        printf '%s' "$REGISTRY_PASSWORD" | ssh -i "$SSH_KEY" -o BatchMode=yes \
                          -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$KNOWN_HOSTS" \
                          "$DEPLOY_USER@$DEPLOY_HOST" \
                          "cd '$DEPLOY_PATH' && bash scripts/deploy.sh '$IMAGE_TAG' load '$REGISTRY' '$REGISTRY_USERNAME'"
                        python3 scripts/smoke.py "http://$DEPLOY_HOST:$LOAD_PORT" --expected-source mock
                    '''
                }
            }
        }
        stage('JMeter and performance gate') {
            steps {
                withCredentials([string(credentialsId: 'radar-api-key', variable: 'API_KEY')]) {
                    sh '''
                        set +x
                        set -eu
                        umask 077
                        secret_properties=$(mktemp)
                        trap 'rm -f "$secret_properties"' EXIT
                        printf 'api_key=%s\n' "$API_KEY" > "$secret_properties"
                        duration=$((LOAD_STEPS * LOAD_HOLD_SECONDS + LOAD_RAMP_SECONDS))
                        jmeter -n -t load-tests/game-radar.jmx -q "$secret_properties" \
                          -Jhost="$DEPLOY_HOST" -Jport="$LOAD_PORT" -Jprotocol=http \
                          -Jthreads="$LOAD_THREADS" -Jsteps="$LOAD_STEPS" \
                          -Jramp="$LOAD_RAMP_SECONDS" -Jhold_seconds="$LOAD_HOLD_SECONDS" \
                          -Jduration="$duration" \
                          -Jjmeter.save.saveservice.output_format=csv \
                          -Jjmeter.save.saveservice.timestamp_format=ms \
                          -Jjmeter.save.saveservice.requestHeaders=false \
                          -Jjmeter.save.saveservice.responseHeaders=false \
                          -Jjmeter.save.saveservice.samplerData=false \
                          -l reports/jmeter-results.jtl -j reports/jmeter.log \
                          -e -o reports/jmeter-html
                        gate_status=0
                        python3 load-tests/check_results.py reports/jmeter-results.jtl \
                          --max-error-rate 0.01 --p95-ms "$P95_THRESHOLD_MS" \
                          > reports/load-summary.json || gate_status=$?
                        cat reports/load-summary.json
                        exit "$gate_status"
                    '''
                }
            }
        }
    }
    post {
        always {
            junit testResults: 'reports/unit-tests.xml', allowEmptyResults: true
            script {
                if (env.LOAD_STARTED == 'yes') {
                    withCredentials([
                        sshUserPrivateKey(credentialsId: 'deploy-ssh', keyFileVariable: 'SSH_KEY'),
                        file(credentialsId: 'deploy-known-hosts', variable: 'KNOWN_HOSTS')
                    ]) {
                        sh '''
                            set +x
                            ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=yes \
                              -o UserKnownHostsFile="$KNOWN_HOSTS" "$DEPLOY_USER@$DEPLOY_HOST" \
                              "cd '$DEPLOY_PATH' && docker compose --env-file .env.load -p game-radar-load -f docker-compose.deploy.yml -f docker-compose.load.yml --profile monitoring exec -T app python - --prometheus http://prometheus:9090 < scripts/export_metrics.py" \
                              > reports/load-monitoring.json || echo 'Could not export sandbox monitoring; check its readiness.'
                            ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=yes \
                              -o UserKnownHostsFile="$KNOWN_HOSTS" "$DEPLOY_USER@$DEPLOY_HOST" \
                              "cd '$DEPLOY_PATH' && docker compose --env-file .env.load -p game-radar-load -f docker-compose.deploy.yml -f docker-compose.load.yml --profile monitoring down --volumes" || true
                        '''
                    }
                }
            }
            archiveArtifacts artifacts: 'reports/trivy.json,reports/jmeter-results.jtl,reports/load-summary.json,reports/load-monitoring.json,reports/jmeter-html/**/*', allowEmptyArchive: true
            sh 'rm -f .deploy.env .deploy.load.env deploy-bundle.tgz'
        }
    }
}
