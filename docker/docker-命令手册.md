# Docker 命令手册(本场景:给 agent 做沙箱)

只讲"给 AI agent 做沙箱"会实际用到的命令。

## 心智模型:镜像 vs 容器

```
Dockerfile  ──build──>  镜像(image)  ──run──>  容器(container)
  (配方)                 (装好的环境模板)        (跑起来的实例)
```
- **镜像**:只读模板,建一次,所有 agent 共用一份(所以不占多份磁盘)。
- **容器**:从镜像跑起来的实例,可起很多个。**沙箱边界在 run 这一步用参数定。**

## 第一步:建镜像(只做一次)

`Dockerfile.agent`:
```dockerfile
FROM node:20-bookworm
RUN apt-get update && apt-get install -y python3 python3-pip git make
RUN npm install -g @anthropic-ai/claude-code
WORKDIR /work
```
```bash
docker build -f Dockerfile.agent -t agent-sandbox .
```
| 部分 | 含义 |
|---|---|
| `build` | 按 Dockerfile 装环境进镜像 |
| `-f Dockerfile.agent` | 指定配方文件 |
| `-t agent-sandbox` | 给镜像起名 |
| `.` | 构建上下文(当前目录) |

改了 Dockerfile 才需重跑。

## 第二步:docker run —— 硬边界全在这条命令的参数里 ★

```bash
docker run --rm -it \
  --memory=1g --memory-swap=1.5g \
  -v "$PWD/packages/backend":/work/backend \
  -v "$PWD/packages/contracts":/work/contracts:ro \
  -w /work \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  agent-sandbox \
  claude
```

| 参数 | 作用 | 为什么关键 |
|---|---|---|
| `--rm` | 退出就自动删容器 | **8G 必加**,否则垃圾容器堆满磁盘 |
| `-it` | 交互式 + 终端 | 要在里面跟 claude 对话 |
| `--memory=1g` | 内存硬上限 | **防一个 agent OOM 拖垮全机** |
| `--memory-swap=1.5g` | 含 swap 总上限 | 超了变慢而非崩机 |
| `-v 主机:容器` | 挂载目录 | **硬边界本体**:只挂的目录才看得见 |
| `:ro` | 该挂载只读 | 能看不能改的物理保证 |
| `-w /work` | 容器内工作目录 | |
| `-e KEY=val` | 注入环境变量 | 传 API key(别写进镜像) |
| `agent-sandbox` | 用哪个镜像 | |
| `claude` | 启动后跑什么 | 直接进 Claude Code |

**精髓:没 `-v` 挂进去的目录,容器里压根不存在。frontend/、.env 不挂 → 任何手段读不到。**

## 第三步:多 agent —— 复制改挂载

```bash
# auth agent
docker run --rm -it --memory=1g \
  -v "$PWD/packages/backend/auth":/work \
  -v "$PWD/packages/contracts":/work/contracts:ro \
  agent-sandbox claude

# grading agent(另开终端)
docker run --rm -it --memory=1g \
  -v "$PWD/packages/backend/grading":/work \
  -v "$PWD/packages/contracts":/work/contracts:ro \
  agent-sandbox claude
```
各看各的子包,共享只读 contracts,互相失明。

## 第四步:管理 + 清理(8G 必会)

| 命令 | 用途 |
|---|---|
| `docker ps` | 看正在跑的容器 |
| `docker ps -a` | 看所有容器(含已停) |
| `docker images` | 看占磁盘的镜像 |
| `docker stop <id>` | 停一个容器 |
| `docker rm <id>` | 删停掉的容器(用了 --rm 无需手动) |
| `docker rmi agent-sandbox` | 删镜像 |
| `docker system df` | 看 Docker 总共占多少磁盘 |
| `docker system prune` | 一键清垃圾(停掉的容器、悬空镜像、缓存) |
| `docker logs <id>` | 看某容器输出 |
| `docker exec -it <id> bash` | 钻进正在跑的容器开 shell(调试) |

> 8G 习惯:不用时 `docker system prune`,构建缓存很吃磁盘。

## 生命周期总览

```
docker build -t agent-sandbox .     # 建模板(偶尔)
docker run --rm -it -v ... claude   # 起沙箱(天天用)★核心
   (在里面让 claude 干活,边界由 -v 决定)
   退出 → --rm 自动清理
docker system df / prune            # 定期看占用、清垃圾
```

**天天敲的就一条:`docker run` 带那串 `-v` 和 `--memory`。** 建议存成 `run-agent.sh <子包名>` 脚本,一句话起一个沙箱 agent。
