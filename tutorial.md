# 命令行翻译器使用教程

本项目提供基于 OpenRouter 的命令行翻译器和笔记翻译 API。程序从 `.env` 读取 API Key，通过 OpenAI 兼容接口调用模型，并返回经过校验的 JSON 翻译结果。命令行入口仍兼容直接翻译文本。

## 1. 工作流程

程序的执行流程如下：

1. `load_dotenv()` 从项目根目录的 `.env` 文件加载环境变量。
2. `main()` 使用 `argparse` 读取命令行参数。
3. `llm_generate(prompt)` 检查 API Key，并创建 OpenRouter 客户端。
4. 客户端向模型发送 system prompt 和 user prompt。
5. 程序读取 assistant message 的 `content`，解析并校验 `title` 和 `content` 两个字符串字段。

```text
命令行输入
    |
    v
main() 读取 prompt
    |
    v
llm_generate(prompt)
    |
    +--> 读取 OPEN_ROUTER_KEY
    +--> 创建 OpenRouter 客户端
    +--> 请求 Qwen 模型
    +--> 解析 JSON 并校验 title/content
    |
    v
终端输出正文翻译或 API JSON
```

## 2. 安装依赖

建议使用项目中的虚拟环境：

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell 的激活命令为：

```powershell
venv\Scripts\Activate.ps1
```

主要依赖包括：

- `openai`：提供 OpenAI 兼容的 Python 客户端。
- `python-dotenv`：读取 `.env` 文件。

## 3. 配置 API Key

在项目根目录创建 `.env`：

```dotenv
OPEN_ROUTER_KEY=your_openrouter_api_key
```

不要把真实 API Key 写进 Python 源代码、README、教程或 Git 仓库。项目的 `.gitignore` 已经忽略 `.env` 文件。

如果 API Key 缺失，程序会抛出以下错误：

```text
OPEN_ROUTER_KEY is not set in .env or the environment
```

## 4. 运行程序

将要翻译的文字作为命令行参数传入：

```bash
python translator.py "How are you?"
```

也可以传入多个不带引号的单词，程序会用空格将它们重新拼接：

```bash
python translator.py How are you?
```

通常建议使用引号包围完整句子，尤其是包含标点、多个空格或特殊字符时。

成功运行后，终端会输出 JSON，例如：

```json
{"title":"","content":"你好吗？"}
```

CLI 默认翻译为中文，也可以指定语言：

```bash
python translator.py --source-language auto --target-language English "你好"
```

## 5. `llm_generate()` 函数

核心函数定义如下：

```python
def llm_generate(prompt: str) -> str:
```

它接收一个字符串参数并返回翻译后的字符串。函数内部首先读取 API Key：

```python
api_key = os.getenv("OPEN_ROUTER_KEY")
```

然后创建 OpenRouter 客户端：

```python
client = OpenAI(
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1",
)
```

OpenRouter 提供与 OpenAI 客户端兼容的接口，因此可以继续使用：

```python
client.chat.completions.create(...)
```

## 6. 文本翻译 API

通用文本翻译接口不会保存或修改笔记：

```http
POST /api/translate
Content-Type: application/json
```

请求体：

```json
{
    "text": "Hello, world",
    "source_language": "auto",
    "target_language": "Chinese"
}
```

响应中的 `translation` 是翻译后的纯文本。缺少 `text` 或 `target_language` 时返回 HTTP 400，上游 OpenRouter 调用失败时返回 HTTP 502。

## 7. 笔记翻译 API

提示词保存在项目根目录的 `prompts/translate_prompt.md`。保存后的笔记可以通过以下接口翻译，结果只作为预览返回，不会修改原笔记：

```http
POST /api/notes/<id>/translate
Content-Type: application/json
```

请求体：

```json
{
    "source_language": "auto",
    "target_language": "English"
}
```

成功响应：

```json
{
    "note_id": 1,
    "source_language": "auto",
    "target_language": "English",
    "translation": {
        "title": "Translated title",
        "content": "Translated content"
    }
}
```

模型返回的内容必须是包含 `title` 和 `content` 字符串字段的 JSON 对象。非法 JSON、字段缺失或上游服务失败时，API 返回 JSON 错误对象和 HTTP 502；缺少 `target_language` 时返回 HTTP 400。

## 8. System Prompt 和 User Prompt

请求中的 messages 包含两条消息：

```python
messages=[
    {
        "role": "system",
        "content": "You are a professional translator...",
    },
    {"role": "user", "content": prompt},
]
```

- `system` 消息要求模型遵守翻译任务和 JSON 输出格式。
- `user` 消息包含文件化 prompt、源语言、目标语言、标题和正文。
- 目标语言由 API 请求中的 `target_language` 字段决定。

## 9. 默认模型和模型覆盖

当前默认模型是：

```python
DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"
```

请求时会优先读取 `OPENROUTER_MODEL` 环境变量；如果没有设置，就使用默认模型：

```python
model=os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
```

临时切换模型时，可以直接设置环境变量：

Linux/macOS：

```bash
OPENROUTER_MODEL="another/model" python translator.py "Good morning"
```

Windows PowerShell：

```powershell
$env:OPENROUTER_MODEL="another/model"
python translator.py "Good morning"
```

也可以把它写进 `.env`：

```dotenv
OPENROUTER_MODEL=another/model
```

## 10. Provider Fallback

代码包含以下 OpenRouter 配置：

```python
extra_body={"provider": {"allow_fallbacks": True}}
```

当当前模型的某个上游 provider 暂时不可用或被限流时，OpenRouter 可以尝试其他 provider。它不能保证所有限流都能解决。如果整个免费模型池都达到额度，仍可能收到 HTTP `429` 错误，此时可以稍后重试、配置自己的 provider key，或切换到其他模型。

## 11. 错误处理

`main()` 会捕获运行期间的异常，并通过 `argparse` 输出错误信息：

```python
try:
    print(llm_generate(" ".join(args.prompt)))
except Exception as error:
    parser.error(str(error))
```

常见问题：

### API Key 未找到

确认 `.env` 在项目根目录，并且变量名完全是 `OPEN_ROUTER_KEY`：

```dotenv
OPEN_ROUTER_KEY=your_openrouter_api_key
```

### HTTP 429

这通常表示模型或 provider 被限流。等待后重试，或设置 `OPENROUTER_MODEL` 使用其他模型。

### 模块找不到

确认已激活虚拟环境，并安装依赖：

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 模型返回空内容

程序会检查 assistant message 的 `content`。如果为空，会抛出：

```text
The model returned an empty translation
```

## 10. 直接在 Python 中调用

除了命令行入口，也可以从其他 Python 文件中调用：

```python
from translator import llm_generate

result = llm_generate("This is a test sentence.")
print(result)
```

导入模块时会执行 `load_dotenv()`，因此只要 `.env` 位于项目根目录，就可以自动读取 API Key。

## 11. 安全建议

- 不要提交 `.env` 文件。
- 不要在日志或错误信息中打印 API Key。
- 如果 API Key 曾经公开显示，应立即在 OpenRouter 控制台撤销并重新生成。
- 生产环境中建议通过部署平台的 secret/environment variable 功能提供 API Key。
