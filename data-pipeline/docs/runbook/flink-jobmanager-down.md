# Runbook: FlinkJobManagerDown

## 告警描述
Flink JobManager 实例不可用，所有 Flink 流处理任务将中断。

## 影响范围
- realtime-stats：PV/UV/转化率计算停止
- anomaly-detect：异常检测停止
- data-enrich：RAG 文档增强停止

## 排查步骤

### 1. 确认 JobManager 状态
```bash
docker ps -a | grep flink-jobmanager
docker logs rdp-flink-jobmanager --tail=50
```

### 2. 检查是否 OOM
```bash
docker inspect rdp-flink-jobmanager | grep -A5 OOMKilled
```

### 3. 检查 TaskManager 状态
```bash
docker ps | grep flink-taskmanager
```

## 修复方案

### 场景 1：容器崩溃重启
```bash
docker restart rdp-flink-jobmanager
# 等待 30 秒后重新提交任务
make submit-realtime
make submit-anomaly
make submit-enrich
```

### 场景 2：OOM Killed
修改 docker-compose.yml 增加内存限制，重启服务。

### 场景 3：持久故障
```bash
make down && make up
# 等待所有服务就绪
make smoke
# 重新提交所有 Flink 任务
make build-jobs && make submit-realtime && make submit-anomaly && make submit-enrich
```

## 升级路径
- 如果 15 分钟内无法恢复，通知团队负责人
- 如果影响核心业务，启动应急响应流程
