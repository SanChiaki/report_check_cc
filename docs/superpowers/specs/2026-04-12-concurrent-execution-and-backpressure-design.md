# 报告检查并发执行与背压控制设计

## 1. 概述

### 1.1 背景

当前系统只有单个后台 worker，任务串行执行，单任务内规则也串行执行。这样的实现简单，但在当前业务场景下会直接拉长单任务完成时间。

当前业务约束如下：

- 服务仍保持单进程部署
- 任务总量通常不高
- 每个任务通常包含约 5 条规则
- 用户更关注单个任务尽快完成，而不是大量任务下的绝对公平性
- 大模型接口存在总并发上限，需要超额等待，不能无上限并发打满
- 当等待队列积压超过阈值时，希望直接拒绝新增任务并返回 `429`

### 1.2 目标

- 支持单进程内多个任务并发执行
- 支持单任务内规则默认并发执行
- 对大模型调用施加全局并发上限，超额自动等待
- 对等待中的任务数设置上限，超额直接返回 `429`
- 保证结果顺序、进度展示、artifact 记录和错误处理在并发下仍然可用
- 优化单任务完成时间，而不是优先追求任务间绝对公平

### 1.3 非目标

- 不在本次设计中引入多进程或分布式队列
- 不在本次设计中引入 Redis、Celery、Kafka 等外部调度基础设施
- 不追求严格的全局公平调度

## 2. 备选方案

### 2.1 方案 A：所有任务、所有规则直接无上限 `gather`

做法：

- 每个任务进入 worker 后，所有规则直接并发
- 多个任务之间也完全并发
- 不额外增加模型并发门闩

优点：

- 实现最简单
- 在极小负载下可能看起来很快

缺点：

- 极易打爆模型接口和外部 API
- 单任务中的一条重规则可能展开为多次模型调用，真实并发数远高于“规则条数”
- 失败重试会叠加尖峰流量
- progress、熔断、日志顺序都会失真

结论：

- 不采用

### 2.2 方案 B：公平优先的多任务调度

做法：

- 多个任务并发执行
- 每个任务只分配很少的规则并发槽位
- 优先保证不同任务之间等待时间稳定

优点：

- 小任务不容易被大任务压住
- 在任务量大时 tail latency 更稳

缺点：

- 当前业务里任务量不高，这会人为拖慢单任务完成时间
- 不符合“每个任务尽快跑完”的核心目标

结论：

- 不作为当前场景的首选

### 2.3 方案 C：单任务优先的分层并发与背压

做法：

- 任务级并发：多个 worker 消费任务
- 规则级并发：同一任务内规则默认可并发执行
- 资源级并发：模型调用、外部 API 调用分别有全局并发门闩
- 队列级背压：等待队列满时，提交接口直接返回 `429`

优点：

- 最符合当前业务目标
- 单任务能尽快占用可用资源完成检查
- 又不会因为底层资源门闩缺失而失控

缺点：

- 实现复杂度高于串行方案
- 需要重写 progress、结果收集、共享缓存与异常隔离逻辑

结论：

- 推荐采用

## 3. 推荐设计

### 3.1 总体策略

执行模型拆成四层：

1. 提交层：控制等待队列长度，超限直接拒绝
2. 任务层：允许多个任务并发执行
3. 规则层：同一任务内规则默认并发执行
4. 资源层：模型调用和外部 API 调用分别限流

核心原则是“上层尽量并发，下层严格限流”：

- 任务和规则调度尽量放开，缩短单任务完成时间
- 真正昂贵的资源统一在底层门闩处收口

### 3.2 配置项

新增或扩展以下配置：

`config/app.yaml`

```yaml
execution:
  worker_concurrency: 2
  max_waiting_tasks: 10
  per_task_rule_concurrency: 5
  progress_update_interval_ms: 250

external_api_limits:
  default_max_concurrency: 2
  by_endpoint:
    inventory-api: 1
```

`config/models.yaml`

```yaml
default_provider: openai

providers:
  openai:
    max_concurrency: 3
    text_max_concurrency: 2
    multimodal_max_concurrency: 1
    text_model: qwen/qwen3-vl-32b-instruct
    text_api_key: ${OPENAI_API_KEY}
    text_base_url: ${OPENAI_API_BASE_URL}
    multimodal_model: qwen/qwen3-vl-32b-instruct
    multimodal_api_key: ${VISION_API_KEY}
    multimodal_base_url: ${VISION_API_BASE_URL}
```

默认值建议：

- `worker_concurrency = 2`
- `max_waiting_tasks = 10`
- `per_task_rule_concurrency = 5`
- `provider.max_concurrency = 3`
- `provider.text_max_concurrency = 2`
- `provider.multimodal_max_concurrency = 1`

这些默认值更偏“单任务快完成”，同时保留安全护栏。

## 4. 组件设计

### 4.1 有界等待队列与提交拦截

当前 `TaskQueue` 只是 `asyncio.Queue()` 的简单包装，没有容量限制。

修改后：

- `TaskQueue` 改为使用 `asyncio.Queue(maxsize=max_waiting_tasks)`
- 新增 `try_enqueue(task_id: str) -> bool`
- `try_enqueue` 内部使用 `put_nowait`
- 当队列已满时捕获 `asyncio.QueueFull` 并返回 `False`

为什么不先 `qsize()` 再决定：

- `qsize()` + `enqueue()` 不是原子操作
- 在并发提交下会出现竞态，多个请求同时看到“还有空位”

为什么 `put_nowait` 足够：

- 本系统仍是单进程
- `asyncio.Queue(maxsize=...)` 在单进程事件循环内已足够保证队列容量约束

提交接口处理逻辑改为：

1. 校验上传文件和规则
2. 保存上传文件
3. 写入数据库任务记录
4. 调用 `task_queue.try_enqueue(task_id)`
5. 若返回 `False`：
   - 删除刚创建的任务记录
   - 清理该任务的上传文件
   - 返回 `429 Too Many Requests`
   - 响应体明确说明“等待队列已满”
   - 响应头带 `Retry-After`

队列容量语义：

- `queue_size` 只表示等待中的任务数
- 已经被 worker 取走、正在执行的任务不计入等待队列容量

这与“限制等待任务数目”的业务要求一致。

### 4.2 多 worker 任务执行

当前 `BackgroundWorker` 只启动一个 `_run_loop()`。

修改后：

- `BackgroundWorker` 增加 `worker_concurrency`
- `start()` 时创建多个 consumer task
- 每个 consumer 都从同一个 `TaskQueue` 拉取任务
- `stop()` 时统一取消并等待所有 consumer

建议结构：

```python
self._workers: list[asyncio.Task] = []

for index in range(self.worker_concurrency):
    self._workers.append(asyncio.create_task(self._run_loop(index)))
```

这样系统在单进程内即可获得任务级并发。

### 4.3 单任务内规则并发执行

当前 `worker._process_task()` 中规则是串行 `for` 循环执行。

修改后：

- 规则默认并发调度
- 为任务内部增加 `per_task_rule_concurrency` 限制
- 默认配置下，单任务约 5 条规则可全部并发
- 结果按原规则顺序写回，不因完成顺序变化

推荐实现方式：

- 预先创建固定长度的 `results: list[dict | None]`
- 每条规则携带其原始 `index`
- 使用 wrapper coroutine 执行规则并在完成后写入 `results[index]`
- 使用 `asyncio.Semaphore(per_task_rule_concurrency)` 控制任务内规则并发
- 使用 `asyncio.gather(..., return_exceptions=False)` 或 `TaskGroup` 配合 wrapper

关键点：

- 不直接让 rule coroutine 的异常冒出到任务级
- 每条规则内部异常应转换成该规则自己的 `error` 结果
- 任务整体只在解析阶段、配置阶段或系统级异常时失败

原因：

- 如果用默认 `TaskGroup` 语义，任意一条规则抛异常会取消所有兄弟规则
- 这与当前系统“单条规则失败不等于整个任务失败”的语义不一致

### 4.4 模型调用并发上限

当前 `ModelManager` 只有 retry，没有并发上限。

修改后：

- `ModelManager` 或 `OpenAIAdapter` 持有 semaphore
- 优先在 `ModelManager` 统一收口
- 支持 provider 级和调用类型级两层门闩

推荐门闩顺序：

1. 先获取 provider 级 `max_concurrency`
2. 再获取 `text_max_concurrency` 或 `multimodal_max_concurrency`
3. 发起实际请求
4. 请求结束立即释放

重试策略要求：

- semaphore 只包裹单次实际请求 attempt
- 不把整个 retry 生命周期包裹在 semaphore 里
- 失败后先释放并发槽位，再执行 backoff

原因：

- 如果把失败后的 sleep 也占住 semaphore，会显著降低吞吐
- 并发限制的本意是限制“在飞请求数”，不是限制“正在等待重试的协程数”

### 4.5 外部 API 并发上限

并发规则不仅会放大模型调用，也会放大外部 HTTP API 请求。

当前 `api` 和 `external_data` 规则直接新建 `httpx.AsyncClient` 请求，没有任何并发控制。

修改后：

- 引入 `ExternalApiLimiter`
- 默认对所有外部 API 共享一个 `default_max_concurrency`
- 可按 endpoint 名称或 host 覆盖并发上限

推荐 key：

- 优先使用 DSL 中显式配置的 API 名称
- 若未提供，则回退到 URL host

这样可以避免单任务内多条 `api` 规则同时压爆同一个下游。

### 4.6 解析与重计算的线程/缓存处理

当前有两类并发下会放大的隐藏成本：

1. 解析函数多数是同步阻塞函数
2. 某些重规则会重复渲染同一份报告

#### 4.6.1 解析线程化

`ExcelParser.parse()`、`PDFParser.parse()`、`MSGParser.parse()` 仍是同步函数。

修改后：

- 在 worker 中通过 `asyncio.to_thread(parser.parse, file_path)` 调用
- extra files 的解析也走同样路径

这样可以避免大文件解析直接卡死事件循环，影响同进程内其他任务和规则。

#### 4.6.2 任务级共享缓存

新增 `TaskExecutionContext`，在单个任务内共享以下缓存：

- `rendered_pages_cache`
- `locate_content_cache`
- 可选的 `image_requirement_cache`

首批必须落地的缓存：

- `rendered_pages_cache`

原因：

- `MultimodalChecker`
- `SignatureChecker`
- `ImageConsistencyChecker`

这几类规则都可能重复渲染同一份报告页面。任务内规则并发后，这种重复会更明显，直接拖慢单任务完成时间。

设计方式：

- `TaskExecutionContext` 由 worker 在开始处理任务时创建
- 通过 `CheckerFactory.create(..., execution_context=...)` 传入 checker
- checker 渲染报告前先查缓存，未命中时再渲染并写回

## 5. 进度、结果与可观测性

### 5.1 进度计算

当前 progress 基于串行规则索引：

- 第 `i` 条规则开始前写入 `20 + i / total * 70`

这在并发执行时不成立。

修改后：

- 使用 `completed_rule_count`
- 每完成一条规则后更新一次任务进度
- 公式改为：

```text
progress = 20 + int(completed_rule_count / total_rules * 70)
```

注意事项：

- 进度只能单调递增
- 数据库写入应做节流，避免高频 update
- 可使用 `progress_update_interval_ms` 进行最小写入间隔控制

### 5.2 结果顺序

虽然规则并发执行，但最终结果顺序仍应和 DSL 中的规则顺序一致。

原因：

- 便于前端展示
- 便于用户按配置顺序理解结果
- 便于 artifact 与规则定义一一对应

### 5.3 监控与健康检查

`/health` 响应建议扩展：

- `queue_size`: 等待中的任务数
- `running_tasks`: 正在执行的任务数
- `worker_concurrency`
- `model_inflight`
- `model_text_inflight`
- `model_multimodal_inflight`

并新增日志指标：

- 提交被 `429` 拒绝次数
- 平均等待入队时长
- 平均任务完成时长
- 规则级平均耗时

## 6. 错误处理

### 6.1 提交阶段

- 队列已满：返回 `429`
- 返回统一错误码，如 `queue_full`
- 响应消息明确区分“频率限流”和“容量限流”

### 6.2 规则执行阶段

- 单条规则失败，生成 `status=error` 结果
- 不影响同任务其他规则继续执行

### 6.3 任务执行阶段

任务仅在以下阶段失败为 `failed`：

- 文件解析失败
- 规则解析/变量替换阶段发生不可恢复错误
- 任务级系统异常

### 6.4 熔断逻辑调整

当前 `api_failure_counts` 是串行假设下的任务内临时计数，并发后语义会失真。

首期实现建议：

- 暂时移除“任务内连续失败 3 次后跳过后续 API 规则”的串行逻辑
- 使用外部 API 并发门闩替代其保护作用

后续如需要熔断，再单独实现：

- endpoint 级共享状态
- 锁保护的连续失败计数
- 带冷却时间的 circuit breaker

## 7. 数据流

### 7.1 提交流程

```text
submit request
  -> validate files/rules
  -> save uploads
  -> create task in DB
  -> try_enqueue(task_id)
     -> success: return pending
     -> queue full:
          -> delete task record
          -> cleanup uploads
          -> return 429
```

### 7.2 任务执行流程

```text
worker dequeue task
  -> mark task processing
  -> parse primary and extra files (to_thread)
  -> resolve rules
  -> create task execution context
  -> schedule rule coroutines concurrently
       -> rule local work
       -> model call waits on model semaphore
       -> external API waits on api limiter
       -> completion updates shared progress
  -> gather ordered results
  -> persist results
  -> mark completed
```

## 8. 测试策略

至少补充以下测试：

### 8.1 队列与提交

- 队列未满时提交成功
- 队列满时提交返回 `429`
- 返回 `429` 时数据库和上传文件被正确清理

### 8.2 worker 并发

- `worker_concurrency=2` 时两个任务可并发处理
- 同一任务内 5 条规则可并发执行
- 结果顺序仍与规则顺序一致

### 8.3 模型限流

- 文本模型调用在并发超过阈值时等待
- 多模态调用在并发超过阈值时等待
- retry 不会长期占用 semaphore

### 8.4 进度与错误

- progress 单调递增
- 单条规则异常不会导致整个任务失败
- 解析阶段异常仍会使任务进入 `failed`

### 8.5 缓存与重计算

- 多条页面类规则命中同一个渲染缓存
- 并发规则下不会重复渲染相同报告页面

## 9. 风险与缓解

### 9.1 风险：规则并发放大底层资源压力

缓解：

- 模型 semaphore
- 外部 API semaphore
- 任务级缓存

### 9.2 风险：同步解析阻塞事件循环

缓解：

- `asyncio.to_thread`

### 9.3 风险：artifact 与日志顺序不再等同于规则顺序

缓解：

- 最终结果列表按规则 index 回填
- AI call 文件名只表示记录顺序，不表示规则顺序

### 9.4 风险：单任务过度吃满系统资源

缓解：

- 控制 `worker_concurrency`
- 保留 `per_task_rule_concurrency`
- 对模型和外部 API 做底层并发门闩

## 10. 实施建议

建议按以下顺序实现：

1. 有界队列与 `429`
2. 多 worker 任务并发
3. 模型 semaphore
4. 单任务内规则并发与 progress 重构
5. 解析 `to_thread`
6. 任务级渲染缓存
7. 外部 API limiter

这样可以先建立系统边界，再放开更多并发，不会在中途出现资源失控。
