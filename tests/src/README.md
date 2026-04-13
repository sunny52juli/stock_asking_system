# Core 模块测试套件

本目录包含 `core` 模块的完整测试套件，覆盖 backtest、screening 和 agent 三个子模块。

## 目录结构

```
tests/core/
├── __init__.py
├── run_tests.py                    # 测试运行脚本
├── README.md                       # 本文档
├── backtest/                       # 回测模块测试
│   ├── __init__.py
│   ├── test_returns.py            # 收益计算器测试 (204行)
│   ├── test_utils.py              # 工具函数测试 (166行)
│   └── test_report.py             # 报告生成器测试 (177行)
├── screening/                      # 筛选模块测试
│   ├── __init__.py
│   ├── test_result_display.py     # 结果显示测试 (130行)
│   └── test_script_saver.py       # 脚本保存测试 (168行)
└── agent/                          # Agent模块测试
    ├── __init__.py
    ├── test_config.py             # 配置模型测试 (178行)
    └── test_agent_phases.py       # 执行阶段测试 (290行)
```

## 测试覆盖

### Backtest 模块 (547行测试代码)

#### test_returns.py - 收益计算器
- ✅ 空候选列表处理
- ✅ 单只股票收益计算
- ✅ 投资组合统计（均值、标准差、胜率）
- ✅ 股票信息获取
- ✅ 边界情况：零价格、NaN价格、负价格
- ✅ 超出数据范围的持有期

#### test_utils.py - 工具函数
- ✅ 收益率格式化（正/负/零/小/大）
- ✅ 胜率计算（全盈/全亏/混合/空）
- ✅ 平均收益率计算
- ✅ 夏普比率计算（正常/空/单值/零标准差）
- ✅ 持有期结束日期计算

#### test_report.py - 报告生成器
- ✅ 空报告打印
- ✅ 失败策略报告
- ✅ 成功策略报告
- ✅ 股票表格打印
- ✅ 摘要格式化

### Screening 模块 (298行测试代码)

#### test_result_display.py - 结果显示
- ✅ 空结果显示
- ✅ 带消息的结果显示
- ✅ 股票代码提取（正则匹配）
- ✅ 无股票代码提示
- ✅ 大量股票代码限制（最多20个）
- ✅ 长内容截断（800字符）
- ✅ 异常消息对象处理

#### test_script_saver.py - 脚本保存
- ✅ 自动保存模式
- ✅ 手动保存模式（用户交互）
- ✅ 各种用户输入（y/n/是/否/无效）
- ✅ 键盘中断处理
- ✅ 保存成功/失败场景
- ✅ 无筛选逻辑时不保存

### Agent 模块 (468行测试代码)

#### test_config.py - 配置模型
- ✅ AgentConfig 默认值和自定义值
- ✅ HookConfig 必需字段验证
- ✅ HookMatcherConfig 配置
- ✅ HooksConfig 三阶段hooks
- ✅ AgentConfigModel 完整配置
- ✅ 嵌套配置修改
- ✅ Pydantic 验证错误

#### test_agent_phases.py - 执行阶段
- ✅ 重试查询构建（无建议/有建议/多个建议）
- ✅ 第一次迭代成功
- ✅ 重试后成功
- ✅ 达到最大迭代次数
- ✅ 执行错误处理
- ✅ Reflection规则加载
- ✅ 建议日志记录
- ✅ Invoke参数验证

## 运行测试

### 方式1：使用运行脚本
```bash
python tests/src/run_tests.py
```

### 方式2：使用pytest直接运行
```bash
# 运行所有core测试
pytest tests/src/ -v

# 运行特定模块测试
pytest tests/src/backtest/ -v
pytest tests/src/screening/ -v
pytest tests/src/agent/ -v

# 运行单个测试文件
pytest tests/src/backtest/test_returns.py -v

# 运行特定测试类
pytest tests/src/backtest/test_returns.py::TestReturnsCalculator -v

# 运行特定测试方法
pytest tests/src/backtest/test_returns.py::TestReturnsCalculator::test_calculate_returns_empty_candidates -v
```

### 方式3：带覆盖率报告
```bash
pytest tests/src/ --cov=src --cov-report=html
```

## 测试特点

1. **模块化组织**：按功能模块分目录存放，便于维护
2. **全面覆盖**：包含正常流程、边界情况、异常处理
3. **Mock隔离**：使用unittest.mock隔离外部依赖
4. **Fixture复用**：使用pytest fixture减少重复代码
5. **清晰命名**：测试方法名清晰描述测试场景
6. **中文注释**：所有测试都有中文文档字符串

## 测试统计

- **测试文件数**：7个
- **测试类数**：17个
- **测试方法数**：80+个
- **总代码行数**：1,313行
- **覆盖率目标**：核心函数100%覆盖

## 添加新测试

1. 在对应模块目录下创建 `test_<模块名>.py`
2. 导入被测模块
3. 创建测试类（以Test开头）
4. 编写测试方法（以test_开头）
5. 使用fixture共享 setup 代码
6. 添加中文文档字符串说明测试目的

## 注意事项

- 所有测试不应依赖外部数据源（使用Mock）
- 测试应该独立运行，不依赖执行顺序
- 避免在测试中使用print，使用capsys捕获输出
- 对于随机性结果，设置随机种子或使用范围断言
