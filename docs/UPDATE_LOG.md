# 文档更新记录

## 更新日期
2026-04-14

## 更新原因
项目代码进行了大幅修改，需要核查并更新 docs 目录下的文档以确保与实际代码结构一致。

## 修改文件清单

### 1. docs/README.md ✅
**修改内容：**
- 更新了目录结构，补充了缺失的模块：
  - `src/agent/models/` - 数据模型
  - `src/agent/security/` - 安全管理
  - `src/agent/services/` - 服务层（包含 stock_pool_service.py）
  - `src/agent/execution/` - 执行层
  - `src/agent/initialization/` - 初始化模块
  - `src/agent/generators/` - 代码生成器
- 完善了 `src/screening/` 目录结构，增加了所有实际存在的文件
- 完善了 `src/backtest/` 目录结构，增加了 report.py 和 utils.py
- 添加了 `app/` 目录说明
- 修正了 `.stock_asking/` 的路径格式
- 在"工作流程"部分明确了 StockPoolService 的位置

### 2. docs/screening_engine.md ✅
**修改内容：**
- **目录结构完全重写**：
  - 移除了不存在的 `utils/screening/` 目录
  - 补充了所有实际存在的文件：
    - batch_calculator.py
    - prefilter.py
    - result_display.py
    - tool_implementations.py
- **组件名称统一**：
  - `StockScreener` → `ScreeningExecutor`
  - 方法名 `run_screening()` → `execute_screening()`
- **新增组件说明**：
  - 添加了 PreFilterEngine（预筛选引擎）的说明
- **使用示例更新**：
  - 所有示例代码中的类名和方法名已更新为实际使用的名称

### 3. docs/agent_system.md ✅
**修改内容：**
- 补充了缺失的目录：
  - `models/` - 数据模型（screening_logic.py）
  - `security/` - 安全管理
  - `services/` - 服务层（stock_pool_service.py）

### 4. docs/backtest_engine.md ✅
**修改内容：**
- 补充了缺失的文件：
  - `utils.py` - 工具函数

### 5. docs/mcp_server.md ✅
**修改内容：**
- 更新了 executors 目录的实际文件列表：
  - 移除了不存在的 data_tools.py、indicator_tools.py、strategy_tools.py
  - 添加了实际存在的文件：
    - math_tools.py
    - other_tools.py
    - technical_tools.py
    - time_series_tools.py

### 6. docs/datahub.md ✅
**状态：** 无需修改，目录结构与实际情况一致

### 7. docs/infrastructure.md ✅
**状态：** 无需修改，目录结构与实际情况一致

## 主要改进点

### 1. 准确性提升
- 所有目录结构现在与实际代码完全一致
- 组件名称统一使用实际代码中的命名

### 2. 完整性提升
- 补充了之前遗漏的重要模块（models、security、services等）
- 每个文件都添加了清晰的注释说明其职责

### 3. 一致性提升
- 统一了标点符号使用（中文冒号、括号等）
- 统一了组件命名规范

## 验证建议

建议用户在实际使用时：
1. 按照更新后的文档结构查找对应模块
2. 参考更新后的使用示例编写代码
3. 如发现任何不一致之处，及时反馈

## 后续维护建议

1. **代码变更时同步更新文档**：每次重大重构后，应及时更新相关文档
2. **自动化检查**：可以考虑添加 CI/CD 检查，验证文档中的路径是否真实存在
3. **版本管理**：在文档头部添加版本号或最后更新时间

---

**更新人：** AI Assistant  
**审核状态：** 待用户确认
