# PyLua

一个使用 Python 实现的 Lua 解释器/虚拟机实验项目，包含 Lua 字节码读取、AST/解析器、简单代码生成以及运行时执行等模块。

## 功能概览

- 读取 Lua 字节码（.luac）并解析 Header/Proto
- 虚拟机执行部分指令集
- 词法分析与语法分析（parser/）
- AST 与简单代码生成（codegen/）
- 基础运行时与内建函数（如 `print`、`getmetatable`、`setmetatable` 等）

## 目录结构

```text
.
├─ codegen/           # 代码生成相关
│  ├─ func.py
│  └─ inst.py
├─ parser/            # 词法/语法分析
│  ├─ lua_ast_util.py
│  ├─ lua_block.py
│  ├─ lua_expr.py
│  ├─ lua_lexer.py
│  └─ lua_stat.py
├─ structs/           # 数据结构
│  └─ instruction.py
├─ lua_*.py           # 运行时、值系统、字节码读取、内建函数等
└─ main.py            # 入口示例
```

## 环境要求

- Python 3.10+（建议）

## 快速开始

当前入口为 [main.py](main.py)。示例代码中会读取 `test2.lua` 和对应的 `test2.luac`，请自行准备这两个文件。

1) 准备 Lua 源文件（示例：`test2.lua`）
2) 使用 Lua 编译器生成字节码：
   - `luac -o test2.luac test2.lua`
3) 运行：
   - `python main.py`

## 使用示例

### 解析字节码

- 参考 [main.py](main.py) 中的 `PyLua`：读取 `.luac` 并得到主函数原型（Proto）。

### 解析 Lua 源码并生成指令信息

- 参考 [main.py](main.py) 中的 `Lexer` 与 `Chunk` 使用方式：
  - 词法分析：`Lexer.from_file(...)`
  - 语法解析：`Chunk.parse(...)`
  - 代码生成：`Chunk.to_info()`

## 已知限制

- 项目为实验性质，指令集、语法覆盖与标准库支持均不完整
- 暂无命令行工具与测试用例
- 运行示例依赖本地 Lua 编译器生成 `.luac`

## Roadmap

- 扩展 VM 指令集与运行时内建函数
- 完善语法解析与代码生成
- 增加测试与示例
