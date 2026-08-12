# PyLua

一个使用 Python 实现的 Lua 5.1 风格解释器/虚拟机实验项目，包含源码解析、代码生成、字节码读写和运行时执行。

## 功能概览

- 读取 Lua 字节码（.luac）并解析 Header/Proto
- 虚拟机执行 Lua 5.1 指令模型
- 词法分析与语法分析（parser/）
- AST 与简单代码生成（codegen/）
- 函数、闭包、upvalue、变参、多返回值、table 和元表
- 基础运行时与内建函数（如 `print`、`pcall`、`pairs`、`select` 等）
- 命令行工具支持（pylua 和 pyluac）

## 目录结构

```text
.
├─ binary/            # 字节码读取相关
│  ├─ header.py
│  ├─ io.py
│  └─ reader.py
├─ codegen/           # 代码生成相关
│  ├─ func.py
│  └─ inst.py
├─ parser/            # 词法/语法分析
│  ├─ block.py
│  ├─ expr.py
│  ├─ lexer.py
│  ├─ serialize.py
│  └─ stat.py
├─ structs/           # 数据结构
│  ├─ function.py
│  ├─ instruction.py
│  ├─ table.py
│  └─ value.py
├─ vm/                # 虚拟机实现
│  ├─ builtins.py
│  ├─ operator.py
│  ├─ protocols.py
│  └─ state.py
├─ cli.py             # 命令行接口
├─ pylua.py           # 解释器入口
├─ pyluac.py          # 编译器入口
└─ README.md          # 项目文档
```

## 环境要求

- Python 3.12+

## 快速开始

安装后可直接使用 `pylua` 和 `pyluac`：

```bash
python -m pip install -e .
```

### 使用解释器（pylua）

1) 准备 Lua 源文件（示例：`test.lua`）
2) 运行：
   - `pylua test.lua first-arg second-arg`

脚本参数通过全局 `arg` table 读取；`arg[0]` 是脚本路径。直接运行 `pylua` 会进入 REPL，REPL 中的全局变量会跨输入行保留。

### 使用编译器（pyluac）

1) 准备 Lua 源文件（示例：`test.lua`）
2) 编译为字节码：
   - `pyluac -o test.luac test.lua`
3) 运行编译后的字节码：
   - `pylua test.luac`

使用 `pyluac -s` 可以递归移除调试记录。目前不支持把多个源文件合并成一个 chunk，也尚未实现模块加载，因此 `pylua -l/--require` 会明确报错。

## 代码格式化与静态检查

Python 生态里常用下面两类工具：

- `ruff format`：自动格式化（类似 `clang-format`）
- `ruff check` + `mypy`：静态检查（类似 `clang-tidy`）

安装开发依赖：

- `pip install -e ".[dev]"`

常用命令：

- 格式化代码：`ruff format .`
- 检查并自动修复部分问题：`ruff check . --fix`
- 进行类型检查：`mypy .`
- 运行测试：`python -m unittest -q`

启用 `pre-commit`（推荐）：

- 安装开发依赖：`pip install -e ".[dev]"`
- 安装 git hooks：`pre-commit install`
- 首次全量执行：`pre-commit run --all-files`

安装后每次 `git commit` 都会自动运行格式化和检查。

## 使用示例

### 解析字节码

- 参考 [cli.py](cli.py) 中的 `PyLua` 类：读取 `.luac` 并得到主函数原型（Proto）。

### 解析 Lua 源码并生成指令信息

- 参考 [cli.py](cli.py) 中的使用方式：
  - 词法分析：`Lexer.from_file(...)`
  - 语法解析：`Parser.from_lexer(lexer)`
  - 代码生成：`parser.to_info()`

## 已知限制

- 项目为实验性质，标准库、协程、userdata 和模块系统尚不完整
- 字节码仅支持 Lua 5.1、32 位指令/整数、4/8 字节 `size_t` 和 double 数值布局
- `.luac` 与具体 Lua 构建的平台布局有关；读取外部 chunk 时会校验 header，不保证兼容其他 Lua 版本
- REPL 当前按单行编译，不支持跨行输入一个未完成的代码块

## Roadmap

- 扩展 VM 指令集与运行时内建函数
- 完善语法解析与代码生成
- 扩展标准库、模块系统和协程支持
- 增加与官方 Lua 5.1 的差分测试和模糊测试
- 优化性能与错误处理
