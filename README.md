# PyLua

一个使用 Python 实现的 Lua 解释器/虚拟机实验项目，包含 Lua 字节码读取、AST/解析器、简单代码生成以及运行时执行等模块。

## 功能概览

- 读取 Lua 字节码（.luac）并解析 Header/Proto
- 虚拟机执行部分指令集
- 词法分析与语法分析（parser/）
- AST 与简单代码生成（codegen/）
- 基础运行时与内建函数（如 `print`、`getmetatable`、`setmetatable` 等）
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
│  ├─ lua_ast_util.py
│  └─ stat.py
├─ structs/           # 数据结构
│  ├─ function.py
│  ├─ instruction.py
│  ├─ table.py
│  └─ value.py
├─ vm/                # 虚拟机实现
│  ├─ builtins.py
│  ├─ lua_vm.py
│  ├─ operator.py
│  ├─ protocols.py
│  └─ state.py
├─ cli.py             # 命令行接口
├─ pylua.py           # 解释器入口
├─ pyluac.py          # 编译器入口
└─ README.md          # 项目文档
```

## 环境要求

- Python 3.10+（建议）

## 快速开始

### 使用解释器（pylua）

1) 准备 Lua 源文件（示例：`test.lua`）
2) 运行：
   - `python pylua.py test.lua`

### 使用编译器（pyluac）

1) 准备 Lua 源文件（示例：`test.lua`）
2) 编译为字节码：
   - `python pyluac.py -o test.luac test.lua`
3) 运行编译后的字节码：
   - `python pylua.py test.luac`

## 使用示例

### 解析字节码

- 参考 [cli.py](cli.py) 中的 `PyLua` 类：读取 `.luac` 并得到主函数原型（Proto）。

### 解析 Lua 源码并生成指令信息

- 参考 [cli.py](cli.py) 中的使用方式：
  - 词法分析：`Lexer.from_file(...)`
  - 语法解析：`Parser.from_lexer(lexer)`
  - 代码生成：`parser.to_info()`

## 已知限制

- 项目为实验性质，指令集、语法覆盖与标准库支持均不完整
- 字节码序列化功能正在开发中
- 运行示例依赖本地 Lua 编译器生成 `.luac`

## Roadmap

- 扩展 VM 指令集与运行时内建函数
- 完善语法解析与代码生成
- 实现完整的字节码序列化功能
- 增加测试与示例
- 优化性能与错误处理
