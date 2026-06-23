#!/bin/bash

# A 股量化投研平台一键启动脚本
# 该脚本会自动使用项目本地的虚拟环境，并同时启动后端 API 和前端开发服务器。

# 定义颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}🚀 正在启动 A 股量化投研平台...${NC}"
echo -e "${BLUE}=======================================${NC}"

# 获取项目根目录的绝对路径
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 检查虚拟环境是否存在
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
    echo "❌ 错误: 未找到虚拟环境 (.venv)"
    echo "请先创建虚拟环境并安装依赖。"
    exit 1
fi

# ==========================================
# 1. 启动后端 API 服务器
# ==========================================
echo -e "${GREEN}👉 [1/2] 正在启动后端 API 服务器...${NC}"
cd "$PROJECT_ROOT/backend"

# 允许 MLflow 使用本地文件系统存储
export MLFLOW_ALLOW_FILE_STORE=true

# 在后台启动 API，使用项目的 python 环境
"$PROJECT_ROOT/.venv/bin/python" -m api.server &
API_PID=$!

# ==========================================
# 2. 启动前端看版
# ==========================================
echo -e "${GREEN}👉 [2/2] 正在启动前端看板 (Vite)...${NC}"
cd "$PROJECT_ROOT/frontend"

# 如果没有 node_modules，自动安装依赖
if [ ! -d "node_modules" ]; then
    echo "检测到初次运行，正在安装前端依赖..."
    npm install
fi

# 在后台启动前端
npm run dev &
FRONTEND_PID=$!

echo -e "${GREEN}✅ 启动成功！${NC}"
echo -e "---------------------------------------"
echo -e "👉 前端看板: ${BLUE}http://localhost:28457${NC}"
echo -e "👉 后端 API: ${BLUE}http://localhost:28456${NC}"
echo -e "---------------------------------------"
echo "按 Ctrl+C 停止所有服务..."

# 捕获 Ctrl+C 信号，优雅退出
trap "echo -e '\n🛑 正在停止所有服务...'; kill $API_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

# 保持主进程运行并等待后台进程
wait $API_PID $FRONTEND_PID
