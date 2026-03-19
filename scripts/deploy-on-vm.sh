#!/bin/bash
# Deploy Qwen Code API and LMS Backend on VM
# Usage: ./deploy-on-vm.sh

set -e

VM_HOST="10.93.26.7"
VM_USER="root"

echo "=== Lab 6 VM Setup Script ==="
echo "Target: $VM_USER@$VM_HOST"
echo ""

# Check if QWEN_CODE_API_KEY is set
if [ -z "$QWEN_CODE_API_KEY" ]; then
    echo "Error: QWEN_CODE_API_KEY environment variable is not set"
    echo "Get your key from https://qwen.ai or https://dashscope.aliyun.com"
    echo ""
    echo "Usage: QWEN_CODE_API_KEY=your-key-here ./deploy-on-vm.sh"
    exit 1
fi

echo "Step 1: Clone qwen-code-api repository..."
ssh $VM_USER@$VM_HOST "cd ~ && git clone https://github.com/inno-se-toolkit/qwen-code-api.git 2>/dev/null || echo 'Repo already exists'"

echo "Step 2: Pull latest changes..."
ssh $VM_USER@$VM_HOST "cd ~/qwen-code-api && git pull"

echo "Step 3: Create .env.secret for Qwen Code API..."
ssh $VM_USER@$VM_HOST "cd ~/qwen-code-api && cat > .env.secret << EOF
QWEN_CODE_API_KEY=$QWEN_CODE_API_KEY
QWEN_CODE_API_PORT=8080
EOF"

echo "Step 4: Start Qwen Code API..."
ssh $VM_USER@$VM_HOST "cd ~/qwen-code-api && docker compose --env-file .env.secret up -d --build"

echo "Step 5: Wait for Qwen Code API to start..."
sleep 10

echo "Step 6: Check Qwen Code API status..."
ssh $VM_USER@$VM_HOST "cd ~/qwen-code-api && docker compose ps"

echo ""
echo "Step 7: Copy .env.docker.secret to VM for LMS Backend..."
scp /root/se-toolkit-lab-6/.env.docker.secret $VM_USER@$VM_HOST:~/se-toolkit-lab-6/.env.docker.secret

echo "Step 8: Clone LMS Backend on VM..."
ssh $VM_USER@$VM_HOST "cd ~ && git clone https://github.com/inno-se-toolkit/se-toolkit-lab-6-backend.git 2>/dev/null || echo 'Backend repo already exists'"

echo "Step 9: Start LMS Backend..."
ssh $VM_USER@$VM_HOST "cd ~/se-toolkit-lab-6-backend && docker compose --env-file ../se-toolkit-lab-6/.env.docker.secret up -d"

echo "Step 10: Wait for backend to start..."
sleep 15

echo "Step 11: Check all services..."
ssh $VM_USER@$VM_HOST "docker ps"

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Update your .env.agent.secret:"
echo "  LLM_API_BASE_URL=http://$VM_HOST:8080"
echo "  AGENT_API_BASE_URL=http://$VM_HOST:42002"
echo ""
echo "Test the API:"
echo "  curl http://$VM_HOST:8080/v1/models"
echo "  curl http://$VM_HOST:42002/items/"
echo ""
