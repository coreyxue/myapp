# ComicForge

本地可运行的漫画**分镜与排版**工具。把剧本（Fountain 格式）+ 角色卡作为输入，产出带气泡的页面 SVG / PNG / PDF / CBZ；图像生成与人物一致性留给你自己（占位框直接显示分镜注释，方便后续重绘）。

默认按**日漫 RTL** 阅读方向工作，可切 LTR。

---

## 设计思路：分镜与排版协同

传统做法是"先想分镜，再排版"——分两段。本工具把它当成**带语义的几何匹配 + 协同搜索**：

```
Script → Beat[] → Page<Beat[]>      (LLM 切镜 + 分页)
                ↓
       ┌─ 模板打分（slot/aspect/emphasis/pacing/cliffhanger）
       │
单页 ──┤  匹配 beat → slot → 放气泡
       │
       └─ 阅读流校验（行聚类 + RTL/LTR 排序）✗ → 换模板
                ↓ 都不过
            BSP 兜底（按 emphasis 比例切矩形）
                ↓
              SVG 输出
```

**关键**：每个 beat 携带 `emphasis(1–5)`、`pacing(quick/normal/sustained/silent)`、`scene_kind`、`aspect_hint`。每个模板 slot 携带 `aspect_pref`、`emphasis_weight`、`reading_index`。这两组语义向量做匹配，让排版决策始终被分镜节奏驱动。

详见 `comicforge/pipeline.py:_design_page` 与 `comicforge/layout/scorer.py`。

---

## 快速开始

### Windows 11

双击 `run.bat`。脚本会自建 venv、装依赖、起服务、开浏览器。

要用本地 LLM 的话先装 [Ollama for Windows](https://ollama.com/download/windows)：

```powershell
ollama pull qwen2.5:7b-instruct
```

### macOS / Linux

```bash
./run.sh
```

或手动：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn comicforge.server:app --port 8765
# 浏览器打开 http://localhost:8765
```

可选：装原生 Cairo 后 `pip install -e ".[cairo]"` 切到 cairosvg 渲染器（栅格更锐）。**Windows 不需要装 Cairo**，svglib 兜底就够了。

---

## 写剧本

`examples/yuki.fountain`：

```fountain
Title: 雪の手紙
Reading: rtl

INT. ATTIC ROOM - NIGHT

YUKI kneels in front of an old wooden chest.

YUKI
姐姐留下的箱子……五年了。

She lifts the lid. A bundle of letters tied with red string.
```

支持的 Fountain 元素：title page、scene heading（`INT./EXT.`）、action 段、CHARACTER + dialogue、parenthetical。其余 LLM 会自己消化。

---

## LLM 后端

环境变量切换；都有启发式 fallback，断网/未装也能跑出占位页面：

| 变量 | 取值 | 说明 |
|---|---|---|
| `COMICFORGE_LLM` | `ollama`（默认） / `openai` / `mock` | 后端 |
| `COMICFORGE_MODEL` | 模型名 | 默认 `qwen2.5:7b-instruct` |
| `COMICFORGE_LLM_URL` | `http://localhost:11434` | Ollama 或 OpenAI 兼容端点 |
| `COMICFORGE_LLM_KEY` | API key | OpenAI 兼容时用 |

---

## 输出

| 格式 | 说明 |
|---|---|
| **SVG** | 矢量、可继续编辑（拖进 Inkscape / Illustrator / Affinity） |
| **PNG** | 单页栅格 |
| **PDF** | 多页，cairo 在则栅格、否则 svglib 矢量直出 |
| **CBZ** | PNG 打 zip，漫画阅读器通用 |
| **project.json** | 完整 Pydantic 序列化，可手改后重跑 pipeline |

---

## 项目结构

```
comicforge/
  models.py          # Pydantic：Script/Beat/Page/Panel/Template/Slot
  fountain.py        # Fountain 解析
  llm.py             # Ollama / OpenAI / mock 客户端
  beats.py           # beat 抽取 + 分页（含启发式 fallback）
  templates.py       # 19 个 RTL 模板，自动镜像到 LTR
  layout/
    scorer.py        # LayoutScorer + greedy slot↔beat 匹配
    bsp.py           # BSP 兜底布局
    validator.py     # ReadingOrderValidator（行聚类 + 眼动模拟）
  render/
    bubble.py        # 气泡放置（RTL 角起栈）
    svg.py           # SVG 渲染
    raster.py        # cairo / svglib 二选一
  pipeline.py        # 协同设计循环
  project.py         # 存读 / 导出
  server.py          # FastAPI
web/                 # 极简编辑器
examples/            # 示例剧本
tests/               # 离线 smoke 测试（mock LLM）
```

---

## 测试

```bash
pytest -q
```

跑离线（mock 后端），覆盖：模板库完整性、Fountain 解析、端到端 pipeline、阅读流校验、SVG 渲染、project 往返。

---

## 后续可加（按需）

- 拖拽改 panel 边界 / 模板的前端编辑器
- LLM 反馈环：validator 的报错回灌给 LLM 让它改写 beat
- 双页跨页（spread）渲染
- 气泡尾巴自动指向说话者位置（约束求解）
- `Panel.image_path` 的 UI 上传通路（数据模型已就位）
