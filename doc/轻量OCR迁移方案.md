# 轻量 OCR 迁移方案

目标：在不影响现有 API 行为的前提下，移除对 PaddleOCR / PaddlePaddle 的依赖，切换到更轻量的 OCR 解决方案以减小镜像体积、降低启动时依赖冲突风险，并提供可回退的迁移路径。

要点摘要：
- 提供候选替代方案及权衡；
- 给出代码修改清单（最小化改动）；
- 更新 `Dockerfile` / `requirements.txt` 与文档；
- 给出验证、性能与回滚流程。

1. 候选方案与推荐
   - 方案 A（推荐） — `pytesseract` (Tesseract OCR)
     - 优点：Python 端依赖轻量（`pytesseract`），OCR 引擎为系统二进制 `tesseract-ocr`（小巧、广泛可用），镜像体积和 Python 依赖显著减小；安装与维护简单；运行在 CPU 上表现稳定。
     - 缺点：对复杂/手写/低质量扫描的识别精度通常不如 PaddleOCR；需在镜像中安装系统包 `tesseract-ocr`。

   - 方案 B（备选） — `EasyOCR`
     - 优点：比 PaddleOCR 更易上手，支持多语言；Python 包可直接 `pip` 安装并较容易集成。
     - 缺点：依赖 `torch`（较重），会显著增加镜像体积和安装时间；不适合追求极小镜像的场景。

   - 方案 C（仅作调研） — 轻量云 OCR（外部 API）
     - 优点：不在镜像内打包任何模型，启动轻、维护简单；适合非离线场景。
     - 缺点：增加网络延迟与成本，依赖外部服务与敏感数据传输合规性风险。

   推荐：方案 A `pytesseract`，因为它在“轻量”和“可控性”之间达到最优平衡；若对识别质量有更高要求，再评估 EasyOCR 或云 OCR。

2. 变更概览（代码与配置）
   - 核心修改点：
     1. `app/pipeline/ocr_engine.py`：实现或恢复一个 `tesseract` 后端（使用 `pytesseract.image_to_data`），并将默认引擎改为 `tesseract`（或通过 `.env` 可切换）。
     2. `requirements.txt`：加入 `pytesseract`，移除 `paddleocr` 与 `paddlepaddle`（若决定永久迁移）。
     3. `Dockerfile`：在 `apt-get install` 中加入 `tesseract-ocr` 系统包；移除安装 Paddle 相关依赖（无直接系统包，但可通过 requirements 控制）。
     4. `app/config.py`：将 `OCR_ENGINE` 的默认值或注释更新为 `tesseract`（可选）。
     5. 文档更新：`README.md`、`doc/开发文档.md`、迁移说明文档（本文件）。

3. 详细修改步骤（最小侵入）
   - 代码变更（示例步骤）：
     1. 在 `app/pipeline/ocr_engine.py` 中提供两个后端分支：
        - `paddleocr`：保留現有实现（可在短期内保留以便回退）；
        - `tesseract`：实现 `pytesseract` 版本；抽象方法 `recognize(images, embedded_text=None)` 不变，返回 `OcrResult`。
     2. 在 `__init__` 中根据 `engine_type` 初始化相应后端；如果 `paddleocr` 未安装，抛出友好错误；但默认可以把 `OCR_ENGINE` 设为 `tesseract`。

   - 依赖与容器：
     1. `requirements.txt`：添加一行 `pytesseract>=0.3` 并保留 `paddleocr`/`paddlepaddle` 直到验证完成（灰度切换）。
     2. `Dockerfile`：在 `apt-get install` 列表中加入 `tesseract-ocr`，并在 `pip install` 阶段确保 `setuptools`/`wheel` 可用：

        RUN apt-get update && apt-get install -y --no-install-recommends \
            poppler-utils \
            tesseract-ocr \
            libgl1 \
            libglib2.0-0 \
            libgomp1 \
            && rm -rf /var/lib/apt/lists/*

        RUN pip install --no-cache-dir --upgrade pip \
            && pip install --no-cache-dir setuptools wheel \
            && pip install --no-cache-dir -r requirements.txt

   - 配置：在 `.env.example` 中把 `OCR_ENGINE=tesseract` 作为示例（并写明可切换回 `paddleocr` 用于回退）。

4. 验证与测试流程
   - 单元/集成测试：运行 `pytest tests/ -q`，确保现有测试通过。测试关注点：
     - `/health` 端点返回 `ocr_engine` 字段与 `.env` 保持一致；
     - 对 `/ocr` 的基本错误返回（无文件、无效 mime）应保持不变。
   - 手工验证：使用 `Example/` 中的样本文件，调用 `POST /ocr` 并比对输出结构与关键字段（格式与字段名保持与以前一致）。
   - 性能回归：记录 `ocr_time` 与总体 `total_time`，与 PaddleOCR 版本对比，评估是否可接受。

5. 分阶段发布与回滚策略
   - 阶段 0（准备）：在分支上实现 `tesseract` 后端，保留 `paddleocr` 作为可选分支；更新 `requirements.txt`（新增 `pytesseract`），更新 `Dockerfile`（添加系统包）。
   - 阶段 1（内测/CI）：在 CI 上构建镜像并运行现有测试。若 CI 通过，部署到开发环境并开启灰度（用 `OCR_ENGINE` 环境变量切换）。
   - 阶段 2（灰度）：把一小部分流量或单个实例切换到 `tesseract`。密切监控输出准确率与错误率。若发现明显回退，立即将环境变量切回 `paddleocr`。
   - 回滚：回退只需把 `OCR_ENGINE` 环境变量改回 `paddleocr` 并重启服务；如果已经完全移除 `paddle` 相关包，回滚则需要重新部署包含 `paddleocr` 的镜像（因此建议先按阶段保留 paddle 直到验证完成）。

6. 风险与注意事项
   - 识别精度：Tesseract 在复杂布局或低质量扫描上可能退化，需用样本集评估精度。
   - 依赖冲突：`pytesseract` 需要系统 `tesseract-ocr`，但不需 `setuptools` 问题；若保留 Paddle 在同一镜像可能会再次触发 `paddle` 对 `setuptools` 等依赖的安装/导入问题。
   - 镜像体积：若改为 EasyOCR（带 torch），镜像增大显著；若目标是“轻量”，不要选 EasyOCR + torch。

7. 估算工作量与时间线（建议）
   - 评估与设计：0.5 天（选择方案、准备样本集）
   - 开发（实现 tesseract 后端并调整配置）：0.5–1 天
   - CI 与本地验证：0.5 天
   - 灰度与观察：1–3 天（取决于流量与监控策略）

8. 变更清单提交建议（PR 内容）
   - 代码：`app/pipeline/ocr_engine.py`（新增/切换后端）；`app/config.py`（注释或默认值更新）。
   - 依赖：`requirements.txt`（新增 `pytesseract`）；保留 `paddle*` 直到验证通过并在最终 PR 中移除。
   - 容器：`Dockerfile`（安装 `tesseract-ocr`）；`docker-compose.yml`（可在开发阶段通过环境变量设置 `OCR_ENGINE`）。
   - 文档：更新 `README.md` 与 `doc/开发文档.md`，并包含本迁移方案文件作为迁移记录。

附：快速测试命令

```bash
# 构建并运行（开发）
docker-compose build --no-cache
docker-compose up -d --build

# 健康检查
curl http://localhost:8000/health

# 用示例文件测试 OCR
curl -X POST http://localhost:8000/ocr -F "file=@Example/referral_letter.pdf"
```

结束。
