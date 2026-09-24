# blueprint-ep3-prompt2

**来源**：AI验证选题训练营 · episode-01-ai-research-blueprint
**集数**：第3集
**名称**：提示词2 - 辅助提示词：检索式优化建议
**序号**：blueprint-ep3-prompt2

**用途说明**：当您根据AI生成的检索式进行初次搜索后，如果对结果不满意（太多、太少或不相关），可以使用这个提示词让AI帮您进行优化。

---

## 提示词模板

请你根据我的检索目的、检索式、和检索结果，来给我的检索式提出调整建议以提高查准率或查全率。你的每一条建议下面都必须详细说明理由。请你的建议主要聚焦在关键词的修改、删减、增加或逻辑关系调整。

---

**[在这里开始粘贴您的输入信息]**

**检索目标：**

[在此处填写您本次检索想要达成的具体目标，从提示词1的输出中获取]

**示例：** 寻找用于构建边缘计算节点网络仿真环境的可复用代码、配置文件或详细协议，特别是基于机场拓扑的Gym自定义环境。

**检索式：**

[在此处粘贴您使用的、需要优化的检索式，从提示词1的输出中获取]

**示例：**
```
( ( TITLE-ABS-KEY ( "Gym" OR "Python" OR "edge computing" OR "network topology" ) ) AND ( TITLE-ABS-KEY ( "airport graph" OR "spatial-temporal graph" OR "airport network" OR "topology" ) ) ) AND ( TITLE-ABS-KEY ( "github" OR "open source" ) )
```

**检索结果：**

[在此处粘贴检索结果的前20个，包含标题摘要等信息。可以直接复制scopus页面里面的信息，注意需要展开摘要]